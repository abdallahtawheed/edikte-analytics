import re
from datetime import datetime
from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector
import os
from dotenv import load_dotenv
from parser.parse import parse_de_number

load_dotenv()

DB_PASSWORD = os.environ["DB_PASSWORD"]
INSTANCE_CONNECTION_NAME = "edikte-analytics-2026:europe-west3:edikte-analytics-db"
DB_USER = "edikte_app"
DB_NAME = "edikte_analytics"

connector = Connector()


def get_connection():
    return connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pg8000",
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
    )


engine = create_engine("postgresql+pg8000://", creator=get_connection)


def parse_de_date(value: str) -> str | None:
    """Convert 'DD.MM.YYYY' to ISO format, or None if unparseable."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").date().isoformat()
    except ValueError:
        return None


def get_latest_content_hash(source_url: str) -> str | None:
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT content_hash FROM listing_snapshots
                WHERE source_url = :source_url
                ORDER BY scraped_at DESC
                LIMIT 1
            """),
            {"source_url": source_url},
        )
        row = result.fetchone()
        return row[0] if row else None


def split_plz_ort(value: str) -> tuple[str | None, str | None]:
    """'8020 Graz' -> ('8020', 'Graz')."""
    if not value:
        return None, None
    match = re.match(r"(\d{4})\s+(.+)", value.strip())
    if match:
        return match.group(1), match.group(2)
    return None, value.strip()

def insert_flags(aktenzeichen: str, snapshot_id: int, flags: list[dict]) -> int:
    if not flags:
        return 0

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT count(*) FROM listing_flags WHERE snapshot_id = :sid"),
            {"sid": snapshot_id},
        ).scalar()

        if existing > 0:
            return 0

        for flag in flags:
            conn.execute(
                text("""
                    INSERT INTO listing_flags (aktenzeichen, snapshot_id, category, flag_type, matched_keyword, source_excerpt)
                    VALUES (:aktenzeichen, :snapshot_id, :category, :flag_type, :matched_keyword, :source_excerpt)
                """),
                {
                    "aktenzeichen": aktenzeichen,
                    "snapshot_id": snapshot_id,
                    "category": flag["category"],
                    "flag_type": flag["flag_type"],
                    "matched_keyword": flag["matched_keyword"],
                    "source_excerpt": flag["source_excerpt"],
                },
            )
    return len(flags)

def insert_snapshot(parsed: dict) -> tuple[int, str]:
    """Insert one row into listing_snapshots. Returns (snapshot_id, aktenzeichen)."""
    fields = parsed["raw_fields"]

    aktenzeichen = fields.pop("Aktenzeichen", None)
    dienststelle = fields.pop("Dienststelle", None)
    aktenzeichen_wegen = fields.pop("wegen", None)
    grundbuch = fields.pop("Grundbuch", None)
    kategorie = fields.pop("Kategorie(n)", None)
    bekannt_gemacht_am = parse_de_date(fields.pop("Bekannt gemacht am", None))
    plz, ort = split_plz_ort(fields.pop("PLZ/Ort", ""))
    schaetzwert = fields.pop("Schätzwert", None)
    geringstes_gebot = fields.pop("Geringstes Gebot", None)
    meistbot = fields.pop("Meistbot", None)

    if not aktenzeichen:
        raise ValueError("No Aktenzeichen found, refusing to insert an untrackable row")

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO listing_snapshots (
                    aktenzeichen, content_hash, source_url, dienststelle, aktenzeichen_wegen,
                    grundbuch, ort, plz, kategorie, bekannt_gemacht_am,
                    status_title, berichtigte_fassung, schaetzwert, geringstes_gebot, meistbot, extra
                ) VALUES (
                    :aktenzeichen, :content_hash, :source_url, :dienststelle, :aktenzeichen_wegen,
                    :grundbuch, :ort, :plz, :kategorie, :bekannt_gemacht_am,
                    :status_title, :berichtigte_fassung, :schaetzwert, :geringstes_gebot, :meistbot, :extra
                )
                RETURNING snapshot_id
            """),
            {
                "aktenzeichen": aktenzeichen,
                "content_hash": parsed["content_hash"],
                "source_url": parsed["source_url"],
                "dienststelle": dienststelle,
                "aktenzeichen_wegen": aktenzeichen_wegen,
                "grundbuch": grundbuch,
                "ort": ort,
                "plz": plz,
                "kategorie": kategorie,
                "bekannt_gemacht_am": bekannt_gemacht_am,
                "status_title": parsed["status_title"],
                "berichtigte_fassung": parsed.get("berichtigte_fassung", False),
                "schaetzwert": parse_de_number(schaetzwert),
                "geringstes_gebot": parse_de_number(geringstes_gebot),
                "meistbot": parse_de_number(meistbot),
                "extra": __import__("json").dumps(fields),
            },
        )
        snapshot_id = result.scalar()

    for doc in parsed["documents"]:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO listing_documents (aktenzeichen, doc_type, storage_path)
                    VALUES (:aktenzeichen, :doc_type, :storage_path)
                """),
                {"aktenzeichen": aktenzeichen, "doc_type": doc["doc_type"], "storage_path": doc["url"]},
            )

    return snapshot_id, aktenzeichen


def insert_parcel(aktenzeichen: str, snapshot_id: int, fields: dict) -> int:
    ez = fields.get("EZ") or fields.get("Einlagezahl")
    grundstuecksnr_raw = (
        fields.get("Grundstücksnr.")
        or fields.get("Grundstücksnr")
        or fields.get("Grundstücksnummer")
    )
    grundstuecksnr = (
        [p.strip() for p in re.split(r"[,\s]+", grundstuecksnr_raw.strip())]
        if grundstuecksnr_raw else None
    )
    blnr = fields.get("BLNr")
    vadium = parse_de_number(fields.get("Vadium"))
    objektgroesse = parse_de_number(fields.get("Objektgröße"))
    grundstuecksgroesse = parse_de_number(fields.get("Grundstücksgröße"))

    if not ez:
        return None

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO listing_parcels (
                    aktenzeichen, snapshot_id, ez, grundstuecksnr, blnr,
                    vadium, objektgroesse_m2, grundstuecksgroesse_m2
                ) VALUES (
                    :aktenzeichen, :snapshot_id, :ez, :grundstuecksnr, :blnr,
                    :vadium, :objektgroesse, :grundstuecksgroesse
                )
                RETURNING parcel_id
            """),
            {
                "aktenzeichen": aktenzeichen,
                "snapshot_id": snapshot_id,
                "ez": ez,
                "grundstuecksnr": grundstuecksnr,
                "blnr": blnr,
                "vadium": vadium,
                "objektgroesse": objektgroesse,
                "grundstuecksgroesse": grundstuecksgroesse,
            },
        )
        parcel_id = result.scalar()

    return parcel_id