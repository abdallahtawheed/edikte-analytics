import requests

DEFAULT_HEADERS = {
    "User-Agent": "edikte-analytics-scraper/0.1 (personal portfolio project)"
}

def fetch_listing(url: str, timeout: int = 15) -> str:
    """Fetch raw HTML for a single Ediktsdatei listing page."""
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text