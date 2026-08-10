import time
import requests
import re


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_HEADERS = {
    "User-Agent": "edikte-analytics-scraper/0.1 (personal portfolio project, contact: <your email>)"
}
RATE_LIMIT_SECONDS = 1.0  # Nominatim's usage policy requires max 1 req/sec

def clean_address_for_geocoding(address: str | None) -> str | None:
    """
    Building addresses sometimes list multiple street entrances combined,
    e.g. 'Felberstraße 64, Huglgasse 2' or 'Wiener Str. 207 und 209'.
    Nominatim can't parse a combined address; use just the first segment.
    """
    if not address:
        return None
    # split on comma, slash, or ' und ' (German "and"), take the first piece
    first_segment = re.split(r",|/| und ", address)[0].strip()
    return first_segment or None


def geocode_address(address: str, plz: str | None, ort: str | None) -> tuple[float, float] | None:
    """
    Geocode an address to (latitude, longitude). Returns None if not found.
    Builds the most complete query string available from what we have.
    """

    address = clean_address_for_geocoding(address)
    query_parts = [p for p in [address, plz, ort, "Austria"] if p]
    query = ", ".join(query_parts)

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "at",  # restrict to Austria, avoids false matches elsewhere
    }

    response = requests.get(NOMINATIM_URL, params=params, headers=DEFAULT_HEADERS, timeout=15)
    response.raise_for_status()
    results = response.json()

    time.sleep(RATE_LIMIT_SECONDS)  # respect rate limit regardless of success/failure

    if not results:
        return None

    lat = float(results[0]["lat"])
    lon = float(results[0]["lon"])
    return lat, lon