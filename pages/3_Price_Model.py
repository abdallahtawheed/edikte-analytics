import sys
sys.path.insert(0, "src")
import io
import os
import streamlit as st
import pandas as pd
from google.cloud import bigquery, storage
import joblib

st.set_page_config(layout="wide")
st.title("Price Estimation Model")

PROJECT_ID = "edikte-analytics-2026"
DATASET = os.environ.get("BQ_DATASET_OVERRIDE", "edikte_analytics_dbt")
BUCKET_NAME = "edikte-analytics-raw-docs"
MODEL_BLOB_PATH = os.environ.get("MODEL_BLOB_PATH_OVERRIDE", "models/price_ratio_model_latest.joblib")
MIN_TRAINING_ROWS = 20


@st.cache_data(ttl=3600)
def load_training_history():
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT trained_at, skipped, skip_reason, n_rows, n_folds,
               mae_mean, mae_std, r2_mean, r2_std, model_path
        FROM `{PROJECT_ID}.{DATASET}.model_training_runs`
        ORDER BY trained_at DESC
    """
    return client.query(query).to_dataframe()


@st.cache_resource(ttl=3600)
def load_latest_model():
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(MODEL_BLOB_PATH)
    if not blob.exists():
        return None
    buffer = io.BytesIO()
    blob.download_to_file(buffer)
    buffer.seek(0)
    return joblib.load(buffer)


history = load_training_history()

if history.empty:
    st.info("No training runs recorded yet. The model trains automatically as part of the daily pipeline.")
else:
    latest = history.iloc[0]

    st.subheader("Model Status")

    if latest["skipped"]:
        current_rows = int(latest["n_rows"]) if pd.notna(latest["n_rows"]) else 0
        st.warning(
            f"Not enough data to train yet. {latest['skip_reason']}"
        )
        st.progress(min(current_rows / MIN_TRAINING_ROWS, 1.0),
                    text=f"{current_rows} / {MIN_TRAINING_ROWS} required training examples")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Training rows", int(latest["n_rows"]))
        col2.metric("Mean Absolute Error", f"{latest['mae_mean']:.4f}", 
                    delta=f"±{latest['mae_std']:.4f}", delta_color="off")
        col3.metric("R² Score", f"{latest['r2_mean']:.4f}",
                    delta=f"±{latest['r2_std']:.4f}", delta_color="off")
        st.caption(f"Last trained: {latest['trained_at']}")

    st.subheader("Training History")
    trained_history = history[~history["skipped"]]
    if not trained_history.empty:
        chart_data = trained_history[["trained_at", "n_rows", "mae_mean", "r2_mean"]].sort_values("trained_at")
        st.line_chart(chart_data.set_index("trained_at")[["mae_mean", "r2_mean"]])
        st.line_chart(chart_data.set_index("trained_at")[["n_rows"]])
    else:
        st.caption("No completed training runs yet, only skips (insufficient data) so far.")

    with st.expander("Full training run log"):
        st.dataframe(history, use_container_width=True)

st.divider()
st.subheader("Estimate a Price")

model = load_latest_model()

if model is None:
    st.error(f"No trained model available yet. Needs at least {MIN_TRAINING_ROWS} real auction outcomes "
              "with both a pre-auction estimate and a resolved sale price. Check back as more auctions resolve.")
else:
    col1, col2 = st.columns(2)
    with col1:
        kategorie = st.selectbox("Category", [
            "Eigentumswohnung", "Einfamilienhaus", "Wohnungseigentumsobjekt",
            "Reihenhaus", "Mehrfamilienhaus", "Sonstiges",
            "land- und forstwirtschaftlich genutzte Liegenschaft",
        ])
        plz_region = st.selectbox("Region (first PLZ digit)", ["1", "2", "3", "4", "5", "6", "7", "8", "9"])
        size_m2 = st.number_input("Size (m²)", min_value=0.0, value=70.0, step=1.0)
        unit_count = st.number_input("Number of bundled units", min_value=1, value=1, step=1)
    with col2:
        schaetzwert = st.number_input("Schätzwert (EUR)", min_value=0.0, value=100000.0, step=1000.0)
        geringstes_gebot = st.number_input("Geringstes Gebot (EUR)", min_value=0.0, value=50000.0, step=1000.0)
        is_bundled = unit_count > 1

    if st.button("Estimate final price"):
        input_df = pd.DataFrame([{
            "kategorie": kategorie,
            "plz_region": plz_region,
            "total_objektgroesse_m2": size_m2,
            "unit_count": unit_count,
            "schaetzwert": schaetzwert,
            "geringstes_gebot": geringstes_gebot,
            "is_bundled": is_bundled,
        }])
        predicted_ratio = model.predict(input_df)[0]
        estimated_price = predicted_ratio * schaetzwert

        st.success(f"Estimated final price: €{estimated_price:,.0f}")
        st.caption(f"Predicted meistbot/schätzwert ratio: {predicted_ratio:.3f} "
                    f"({'above' if predicted_ratio > 1 else 'below'} the appraised estimate)")
        st.caption("This estimate is based on a small, growing training set. Treat it as directional, "
                    "not a guarantee, especially while the model is trained on relatively few real outcomes.")