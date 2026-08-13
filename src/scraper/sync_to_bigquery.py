import sys
sys.path.insert(0, "src")

from google.cloud import bigquery
from sqlalchemy import text
from scraper.persist import engine
from datetime import date, datetime
from decimal import Decimal


PROJECT_ID = "edikte-analytics-2026"
DATASET_ID = "edikte_analytics"

TABLES_TO_SYNC = [
    "listing_snapshots",
    "listing_status_events",
    "listing_parcels",
    "listing_documents",
    "listing_flags",
    "listing_coordinates",
]


import json
from datetime import date, datetime
from decimal import Decimal

def make_json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)  # serialize extra as a string, don't let it flatten
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)  # same for any array/JSON-list columns
    return value

def sync_table(bq_client: bigquery.Client, table_name: str):
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table_name}"))
        rows = [
            {k: make_json_safe(v) for k, v in row._mapping.items()}
            for row in result
        ]
    if not rows:
        print(f"{table_name}: no rows, skipping")
        return

    table_id = f"{PROJECT_ID}.{DATASET_ID}.raw_{table_name}"
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",  # full refresh each run, simplest correct approach at this scale
        autodetect=True,
    )

    job = bq_client.load_table_from_json(rows, table_id, job_config=job_config)
    job.result()
    print(f"{table_name}: synced {len(rows)} rows -> {table_id}")


def main():
    bq_client = bigquery.Client(project=PROJECT_ID)
    for table in TABLES_TO_SYNC:
        sync_table(bq_client, table)


if __name__ == "__main__":
    main()