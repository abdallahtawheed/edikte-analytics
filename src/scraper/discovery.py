import re
import requests

BASE_URL = "https://edikte.justiz.gv.at"
SEARCH_URL = f"{BASE_URL}/edikte/ex/exedi3.nsf/submitSuche"

DEFAULT_HEADERS = {
    "User-Agent": "edikte-analytics-scraper/0.1 (personal portfolio project)"
}

LISTING_LINK_PATTERN = re.compile(r'alldoc/[a-f0-9]+!OpenDocument')


def discover_listings(since_date: str) -> list[str]:
    """
    Query the Einfache Suche results page and return full listing URLs.
    since_date format: 'DD.MM.YYYY'.
    """
    params = {
        "OpenAgent": "",
        "subf": "eex",
        "scope": "edi",
        "Anw": "EX",
        "SearchOrder": "4",
        "SearchMax": "4999",
        "datum": since_date,
    }

    response = requests.get(SEARCH_URL, params=params, headers=DEFAULT_HEADERS, timeout=30)
    response.raise_for_status()

    relative_links = set(LISTING_LINK_PATTERN.findall(response.text))
    full_urls = [f"{BASE_URL}/edikte/ex/exedi3.nsf/{link}" for link in relative_links]
    return full_urls