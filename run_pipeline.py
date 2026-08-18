import sys
sys.path.insert(0, "src")

from run_scrape import main as run_scrape_main
from scraper.run_geocoding import main as run_geocoding_main
from scraper.sync_to_bigquery import main as run_sync_main
import subprocess

def main():
    print("=== SCRAPE ===")
    run_scrape_main()

    print("=== GEOCODE ===")
    run_geocoding_main()

    print("=== SYNC TO BIGQUERY ===")
    run_sync_main()

    print("=== DBT RUN ===")
    result = subprocess.run(
        ["dbt", "run", "--project-dir", "dbt/edikte_dbt", "--profiles-dir", "dbt/edikte_dbt"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise Exception("dbt run failed")
    
    print("=== PRICE MODEL TRAINING ===")
    sys.path.insert(0, "src")
    from model.train_price_model import main as train_model_main
    train_model_main()

if __name__ == "__main__":
    main()