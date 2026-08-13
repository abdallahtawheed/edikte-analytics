
from bs4 import BeautifulSoup
import hashlib
from urllib.parse import urljoin
import json
import re

MEISTBOT_PATTERN = re.compile(r"um das Meistbot von\s*([\d.,]+)\s*EUR\s*zugeschlagen")

# in parser/parse.py, alongside MEISTBOT_PATTERN
LIEGENSCHAFT_BLOCK_PATTERN = re.compile(
    r"Die Liegenschaft\(en\) Grundbuch\s*"
    r"(\d{5}\s+[^\n]+?)\s*"          # Grundbuch code + name
    r"EZ\s+(\d+)\s*"                 # EZ
    r"Grundstücksnr\.\s*([^\n;]+?);\s*BLNr\.\s*(\d+)\s*"  # Grundstücksnr + BLNr
    r"(\d{4})\s+([^\n,]+),?\s*(.*)",  # PLZ, Ort, and remaining address
    re.IGNORECASE
)

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

    # Zuschlag-type pages: sale price is in prose, not a div.row field
    page_text = soup.get_text()
    meistbot_match = MEISTBOT_PATTERN.search(page_text)
    if meistbot_match:
        result["raw_fields"]["Meistbot"] = meistbot_match.group(1) + " EUR"


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

    if not result["raw_fields"].get("Grundbuch"):
        match = LIEGENSCHAFT_BLOCK_PATTERN.search(page_text)
        if match:
            grundbuch, ez, grundstuecksnr, blnr, plz, ort, rest_address = match.groups()
            result["raw_fields"].setdefault("Grundbuch", grundbuch.strip())
            result["raw_fields"].setdefault("EZ", ez.strip())
            result["raw_fields"].setdefault("Grundstücksnr.", grundstuecksnr.strip())
            result["raw_fields"].setdefault("BLNr", blnr.strip())
            result["raw_fields"].setdefault("PLZ/Ort", f"{plz.strip()} {ort.strip()}")
            if rest_address.strip():
                result["raw_fields"].setdefault("Liegenschaftsadresse", rest_address.strip())

        # in parse_listing, as an additional fallback after the LIEGENSCHAFT_BLOCK_PATTERN attempt
    if not result["raw_fields"].get("EZ"):
        for row in soup.select("div.row"):
            label_el = row.select_one("span.col-sm-3")
            value_el = row.select_one("p.col-sm-9")
            if value_el and (not label_el or not label_el.get_text(strip=True)):
                value_text = value_el.get_text(separator=" ", strip=True)

                ez_match = re.search(r"EZ\s+(\d+)", value_text)
                grundbuch_match = re.match(r"([\d]{5})\s+([^\d]+?)\s+EZ", value_text)
                grundstuecksnr_match = re.search(r"Grundstücksnr\.\s*([^;]+);\s*BLNr\.\s*([\d]+(?:,\s*\d+)*)", value_text)
                blnr_only_match = re.search(r"BLNr\.\s*([\d]+(?:,\s*\d+)*)", value_text)

                if ez_match:
                    result["raw_fields"].setdefault("EZ", ez_match.group(1))
                if grundbuch_match:
                    result["raw_fields"].setdefault("Grundbuch", f"{grundbuch_match.group(1)} {grundbuch_match.group(2)}")

                if grundstuecksnr_match:
                    result["raw_fields"].setdefault("Grundstücksnr.", grundstuecksnr_match.group(1).strip())
                    result["raw_fields"].setdefault("BLNr", grundstuecksnr_match.group(2).strip())
                elif blnr_only_match:
                    result["raw_fields"].setdefault("BLNr", blnr_only_match.group(1).strip())
    
    hashable_content = json.dumps(
    {
        "source_url": result["source_url"],
        "status_title": result["status_title"],
        "raw_fields": result["raw_fields"],
        "documents": result["documents"],
        "berichtigte_fassung": result["berichtigte_fassung"],
    },
    sort_keys=True,
    )
    result["content_hash"] = hashlib.sha256(hashable_content.encode("utf-8")).hexdigest()

    return result

