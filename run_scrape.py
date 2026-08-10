import sys
import time
sys.path.insert(0, "src")

from scraper.discovery import discover_listings
from scraper.fetch import fetch_listing
from parser.parse import parse_listing
from scraper.persist import insert_snapshot, get_latest_content_hash, insert_parcel
from scraper.state_machine import insert_status_event

SINCE_DATE = "01.01.2020"  # effectively "everything available", per our plateau test
DELAY_SECONDS = 1.0  # be a polite scraper against a government server, not just fast

def process_listing(url: str) -> str:
    try:
        html = fetch_listing(url)
        data = parse_listing(html, url)

        aktenzeichen_preview = data["raw_fields"].get("Aktenzeichen")
        if not aktenzeichen_preview:
            return "SKIPPED (no Aktenzeichen found)"

        existing_hash = get_latest_content_hash(data["source_url"])
        if existing_hash == data["content_hash"]:
            return "unchanged"

        fields_snapshot = dict(data["raw_fields"])
        snapshot_id, aktenzeichen = insert_snapshot(data)
        insert_status_event(aktenzeichen, data["status_title"])
        insert_parcel(aktenzeichen, snapshot_id, fields_snapshot)

        return f"inserted (snapshot_id={snapshot_id}, docs={len(data['documents'])})"

    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"    


def main():
    print(f"Discovering listings since {SINCE_DATE}...")
    urls = discover_listings(SINCE_DATE)
    print(f"Found {len(urls)} listings.\n")

    results = {"inserted": 0, "unchanged": 0, "skipped": 0, "error": 0}

    for i, url in enumerate(urls, 1):
        status = process_listing(url)
        print(f"[{i}/{len(urls)}] {url.split('/')[-1][:20]}... -> {status}")

        if status.startswith("inserted"):
            results["inserted"] += 1
        elif status == "unchanged":
            results["unchanged"] += 1
        elif status.startswith("SKIPPED"):
            results["skipped"] += 1
        elif status.startswith("ERROR"):
            results["error"] += 1

        time.sleep(DELAY_SECONDS)

    print(f"\nDone. Inserted: {results['inserted']}, Unchanged: {results['unchanged']}, "
          f"Skipped: {results['skipped']}, Errors: {results['error']}")


if __name__ == "__main__":
    main()