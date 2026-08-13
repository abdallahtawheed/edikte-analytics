import sys
sys.path.insert(0, "src")

from sqlalchemy import text
from scraper.persist import engine, insert_flags
from parser.flags import scan_for_flags

def dedupe_flags(flags: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for f in flags:
        key = (f["flag_type"], f["matched_keyword"])
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    return deduped


def main():
    with engine.begin() as conn:
        print("Clearing existing flags (rescanning with new categorized patterns)...")
        conn.execute(text("DELETE FROM listing_flags"))

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT snapshot_id, aktenzeichen,
                   extra->>'Beschreibung (WE)' as beschreibung,
                   extra->>'Sonstige Hinweise' as sonstige
            FROM listing_snapshots
        """)).fetchall()

    total = len(rows)
    print(f"Scanning {total} snapshots for flags...\n")

    total_flags = 0
    flagged_snapshots = 0

    for i, row in enumerate(rows, 1):
        raw_flags = scan_for_flags(row.beschreibung or "") + scan_for_flags(row.sonstige or "")
        flags = dedupe_flags(raw_flags)
        if flags:
            insert_flags(row.aktenzeichen, row.snapshot_id, flags)
            total_flags += len(flags)
            flagged_snapshots += 1

        if i % 25 == 0 or i == total:
            print(f"[{i}/{total}] scanned, {flagged_snapshots} flagged so far, {total_flags} total flags")

    print(f"\nDone. Inserted {total_flags} flags across {flagged_snapshots} of {total} snapshots.")

if __name__ == "__main__":
    main()