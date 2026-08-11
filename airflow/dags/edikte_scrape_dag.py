from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "abdallah",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def run_scrape():
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from scraper.discovery import discover_listings
    from scraper.fetch import fetch_listing
    from parser.parse import parse_listing
    from scraper.persist import insert_snapshot, get_latest_content_hash, insert_parcel
    from scraper.state_machine import insert_status_event
    import time

    urls = discover_listings("01.01.2020")
    for url in urls:
        try:
            html = fetch_listing(url)
            data = parse_listing(html, url)
            existing_hash = get_latest_content_hash(data["source_url"])
            if existing_hash == data["content_hash"]:
                continue
            fields_snapshot = dict(data["raw_fields"])
            snapshot_id, aktenzeichen = insert_snapshot(data)
            insert_status_event(aktenzeichen, data["status_title"])
            insert_parcel(aktenzeichen, snapshot_id, fields_snapshot)
        except Exception as e:
            print(f"Error on {url}: {e}")
        time.sleep(1.0)


def run_geocoding():
    import sys
    sys.path.insert(0, "/opt/airflow/src")
    from scraper.run_geocoding import main
    main()


with DAG(
    dag_id="edikte_daily_scrape",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2026, 8, 11),
    catchup=False,
) as dag:

    scrape_task = PythonOperator(
        task_id="scrape_listings",
        python_callable=run_scrape,
    )

    geocode_task = PythonOperator(
        task_id="geocode_new_listings",
        python_callable=run_geocoding,
    )

    scrape_task >> geocode_task