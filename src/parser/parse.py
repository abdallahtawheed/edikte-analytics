from unittest import result

from bs4 import BeautifulSoup
import hashlib
from urllib.parse import urljoin
import json
import re

BASE_URL = "https://edikte.justiz.gv.at"

DOCUMENT_LABELS = {"Kurzgutachten", "Langgutachten", "Lageplan", "Grundriss(e)", "Foto(s)"}



def parse_de_number(value: str | None) -> float | None:
    """Convert German-formatted numbers like '101.000,00 EUR' or '55,26 m²' to float."""
    if not value:
        return None
    # Strip everything except digits, comma, period, minus sign
    cleaned = re.sub(r"[^\d,.\-]", "", value)
    if not cleaned:
        return None
    # German format: '.' = thousands separator, ',' = decimal separator
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_listing(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "source_url": source_url,
        "status_title": None,   # e.g. "Versteigerung - Wohnung top Nr. 4"
        "raw_fields": {},        # label -> value, goes into extra JSONB for now
        "documents": [],         # list of {doc_type, url}
        "berichtigte_fassung": False,  # boolean indicating if it's a corrected version
    }

    headline_el = soup.select_one(".page-header h1 small")
    if headline_el:
        result["status_title"] = headline_el.get_text(strip=True)


    # in parse_listing, after finding headline_el:
    berichtigte_fassung = "Berichtigte Fassung" in soup.get_text()
    result["berichtigte_fassung"] = berichtigte_fassung

    for row in soup.select("div.row"):
        label_el = row.select_one("span.col-sm-3")
        value_el = row.select_one("p.col-sm-9")
        if not label_el or not value_el:
            continue

        label = label_el.get_text(strip=True).rstrip(":")

        if label in DOCUMENT_LABELS:
            links = value_el.select("a")
            for link in links:
                if link.get("href"):
                    result["documents"].append({
                        "doc_type": label,
                        "url": urljoin(BASE_URL, link["href"]),
                    })
            continue

        result["raw_fields"][label] = value_el.get_text(separator=" ", strip=True)

    hashable_content = json.dumps(
    {
        "status_title": result["status_title"],
        "raw_fields": result["raw_fields"],
        "documents": result["documents"],
        "berichtigte_fassung": result["berichtigte_fassung"],
    },
    sort_keys=True,  # critical: ensures identical data always produces identical string
    )
    result["content_hash"] = hashlib.sha256(hashable_content.encode("utf-8")).hexdigest()

    return result