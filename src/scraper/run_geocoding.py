import sys
sys.path.insert(0, "src")

from sqlalchemy import text
from scraper.persist import engine
from scraper.geocoding import geocode_address


def get_ungeocoded_listings() -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT DISTINCT ON (s.source_url)
                    s.source_url, s.aktenzeichen,
                    s.extra->>'Liegenschaftsadresse' as adresse, s.plz, s.ort
                FROM listing_snapshots s
                LEFT JOIN listing_coordinates c ON c.source_url = s.source_url
                WHERE c.source_url IS NULL AND s.source_url IS NOT NULL
                ORDER BY s.source_url, s.scraped_at DESC
            """)
        )
        return [dict(row._mapping) for row in result]


def insert_coordinates(source_url: str, lat: float, lon: float):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO listing_coordinates (source_url, latitude, longitude)
                VALUES (:source_url, :lat, :lon)
                ON CONFLICT (source_url) DO UPDATE SET
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    geocoded_at = now()
            """),
            {"source_url": source_url, "lat": lat, "lon": lon},
        )


def main():
    listings = get_ungeocoded_listings()
    print(f"Found {len(listings)} listings needing geocoding.\n")

    geocoded, failed = 0, 0

    for i, listing in enumerate(listings, 1):
        coords = geocode_address(listing["adresse"], listing["plz"], listing["ort"])
        if coords:
            insert_coordinates(listing["source_url"], coords[0], coords[1])
            geocoded += 1
            status = f"OK ({coords[0]:.4f}, {coords[1]:.4f})"
        else:
            failed += 1
            status = "not found"

        print(f"[{i}/{len(listings)}] {listing['aktenzeichen']} -> {status}")

    print(f"\nDone. Geocoded: {geocoded}, Failed: {failed}")


if __name__ == "__main__":
    main()