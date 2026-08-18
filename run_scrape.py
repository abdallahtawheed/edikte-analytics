import sys
import time
sys.path.insert(0, "src")

from scraper.discovery import discover_listings
from scraper.fetch import fetch_listing
from parser.parse import parse_listing
from scraper.persist import insert_snapshot, get_latest_content_hash, insert_parcel
from scraper.state_machine import insert_status_event
from parser.flags import scan_for_flags
from scraper.persist import insert_snapshot, get_latest_content_hash, insert_parcel, insert_flags

from logging_utils import log_event

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
        insert_status_event(aktenzeichen, data["source_url"], data["status_title"])
        insert_parcel(aktenzeichen, snapshot_id, fields_snapshot)

        beschreibung = fields_snapshot.get("Beschreibung (WE)", "")
        sonstige = fields_snapshot.get("Sonstige Hinweise", "")
        raw_flags = scan_for_flags(beschreibung) + scan_for_flags(sonstige)
        seen = set()
        flags = []
        for f in raw_flags:
            key = (f["flag_type"], f["matched_keyword"])
            if key not in seen:
                seen.add(key)
                flags.append(f)
        insert_flags(aktenzeichen, snapshot_id, flags)

        return f"inserted (snapshot_id={snapshot_id}, docs={len(data['documents'])}, flags={len(flags)})"

    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"    


def main():
    print(f"Discovering listings since {SINCE_DATE}...")
    urls = discover_listings(SINCE_DATE)
    print(f"Found {len(urls)} listings.\n")

    results = {"inserted": 0, "unchanged": 0, "skipped": 0, "error": 0}

    for i, url in enumerate(urls, 1):
        status = process_listing(url)

        log_event("listing_processed",
            index=i, total=len(urls),
            url_id=url.split('/')[-1][:20],
            status=status)

        if status.startswith("inserted"):
            results["inserted"] += 1
        elif status == "unchanged":
            results["unchanged"] += 1
        elif status.startswith("SKIPPED"):
            results["skipped"] += 1
        elif status.startswith("ERROR"):
            results["error"] += 1

        time.sleep(DELAY_SECONDS)

    log_event("scrape_run_complete", **results)


if __name__ == "__main__":
    main()