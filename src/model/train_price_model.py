import sys
sys.path.insert(0, "src")

import json
from datetime import datetime, timezone
import os
import joblib
import pandas as pd
from google.cloud import bigquery, storage
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

PROJECT_ID = "edikte-analytics-2026"
DATASET = os.environ.get("BQ_DATASET_OVERRIDE", "edikte_analytics_dbt")
BUCKET_NAME = "edikte-analytics-raw-docs"  # reusing the existing bucket, models/ prefix
MODEL_BLOB_PATH = os.environ.get("MODEL_BLOB_PATH_OVERRIDE", "models/price_ratio_model_latest.joblib")

MIN_TRAINING_ROWS = 20  # below this, any model is fitting noise, not signal


def load_training_data() -> pd.DataFrame:
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT
            kategorie,
            plz,
            total_objektgroesse_m2,
            is_bundled,
            unit_count,
            schaetzwert,
            geringstes_gebot,
            meistbot_to_schaetzwert_ratio
        FROM `{PROJECT_ID}.{DATASET}.mart_price_history`
        WHERE meistbot_to_schaetzwert_ratio IS NOT NULL
          AND schaetzwert IS NOT NULL
    """
    return client.query(query).to_dataframe()


def build_pipeline() -> Pipeline:
    # PLZ's first digit is a rough regional signal without the sparsity of
    # using full PLZ or Ort as a categorical (too many distinct values for
    # this data volume to support meaningfully).
    categorical_features = ["kategorie"]
    numeric_features = ["total_objektgroesse_m2", "unit_count", "schaetzwert", "geringstes_gebot"]
    boolean_features = ["is_bundled"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ],
        remainder="passthrough",  # numeric + boolean pass through unchanged
    )

    model = GradientBoostingRegressor(
        n_estimators=50,      # deliberately modest, small data doesn't support a large ensemble
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
    )

    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def train_and_evaluate(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["plz_region"] = df["plz"].astype(str).str[0]  # first digit only, coarse region signal
    df["total_objektgroesse_m2"] = df["total_objektgroesse_m2"].fillna(df["total_objektgroesse_m2"].median())

    feature_cols = ["kategorie", "plz_region", "total_objektgroesse_m2", "unit_count", "schaetzwert", "geringstes_gebot", "is_bundled"]
    X = df[feature_cols]
    y = df["meistbot_to_schaetzwert_ratio"]

    pipeline = build_pipeline()

    n_folds = max(2, min(5, len(df)))
    cv = KFold(n_splits=n_folds, shuffle=True, random_state=42)

    mae_scores = -cross_val_score(pipeline, X, y, cv=cv, scoring="neg_mean_absolute_error")
    r2_scores = cross_val_score(pipeline, X, y, cv=cv, scoring="r2")

    pipeline.fit(X, y)  # final fit on all available data, for actual deployment

    return {
        "pipeline": pipeline,
        "n_rows": len(df),
        "n_folds": n_folds,
        "mae_mean": float(mae_scores.mean()),
        "mae_std": float(mae_scores.std()),
        "r2_mean": float(r2_scores.mean()),
        "r2_std": float(r2_scores.std()),
    }


def save_model(pipeline) -> str:
    local_path = "/tmp/price_ratio_model.joblib"
    joblib.dump(pipeline, local_path)

    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(MODEL_BLOB_PATH)
    blob.upload_from_filename(local_path)

    return f"gs://{BUCKET_NAME}/{MODEL_BLOB_PATH}"


def log_training_run(metrics: dict, model_path: str, skipped: bool = False, reason: str | None = None):
    client = bigquery.Client(project=PROJECT_ID)
    table_id = f"{PROJECT_ID}.{DATASET}.model_training_runs"

    row = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "skipped": skipped,
        "skip_reason": reason,
        "n_rows": metrics.get("n_rows"),
        "n_folds": metrics.get("n_folds"),
        "mae_mean": metrics.get("mae_mean"),
        "mae_std": metrics.get("mae_std"),
        "r2_mean": metrics.get("r2_mean"),
        "r2_std": metrics.get("r2_std"),
        "model_path": model_path,
    }

    errors = client.insert_rows_json(table_id, [row])
    if errors:
        print(f"Warning: failed to log training run: {errors}")


def main():
    df = load_training_data()
    print(f"Loaded {len(df)} training rows from mart_price_history.")

    if len(df) < MIN_TRAINING_ROWS:
        reason = f"Only {len(df)} rows available, need at least {MIN_TRAINING_ROWS} to train meaningfully."
        print(f"Skipping training: {reason}")
        log_training_run({"n_rows": len(df)}, model_path="", skipped=True, reason=reason)
        return

    metrics = train_and_evaluate(df)
    print(f"Trained on {metrics['n_rows']} rows, {metrics['n_folds']}-fold CV: "
          f"MAE={metrics['mae_mean']:.4f} (+/-{metrics['mae_std']:.4f}), "
          f"R2={metrics['r2_mean']:.4f} (+/-{metrics['r2_std']:.4f})")

    model_path = save_model(metrics["pipeline"])
    print(f"Model saved to {model_path}")

    log_training_run(metrics, model_path, skipped=False)
    print("Training run logged.")


if __name__ == "__main__":
    main()