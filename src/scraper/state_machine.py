from sqlalchemy import text
from scraper.persist import engine

CANONICAL_STATUSES = [
    "Zuschlag ohne Überbot",
    "Zuschlag mit Überbot",
    "Zuschlag nach Überbot",
    "Entfall des Termins",
    "Verschiebung",
    "Meistbotsverteilung",
    "Versteigerung",
]

VALID_TRANSITIONS = {
    None: set(CANONICAL_STATUSES),
    "Versteigerung": {"Verschiebung", "Entfall des Termins", "Zuschlag ohne Überbot",
                       "Zuschlag mit Überbot", "Zuschlag nach Überbot"},
    "Verschiebung": {"Versteigerung", "Verschiebung", "Entfall des Termins",
                      "Zuschlag ohne Überbot", "Zuschlag mit Überbot", "Zuschlag nach Überbot"},
    "Entfall des Termins": set(),
    "Zuschlag ohne Überbot": {"Meistbotsverteilung"},
    "Zuschlag mit Überbot": {"Meistbotsverteilung"},
    "Zuschlag nach Überbot": {"Meistbotsverteilung"},
    "Meistbotsverteilung": set(),
}


def classify_status(status_title: str | None) -> str | None:
    if not status_title:
        return None
    for status in CANONICAL_STATUSES:
        if status_title.startswith(status):
            return status
    return None


def get_previous_status(aktenzeichen: str) -> str | None:
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT status FROM listing_status_events
                WHERE aktenzeichen = :aktenzeichen
                ORDER BY observed_at DESC
                LIMIT 1
            """),
            {"aktenzeichen": aktenzeichen},
        )
        row = result.fetchone()
        return row[0] if row else None


def insert_status_event(aktenzeichen: str, status_title: str | None) -> int:
    status = classify_status(status_title)
    previous_status = get_previous_status(aktenzeichen)

    if status is None:
        transition_valid = False
        anomaly_note = f"Unrecognized status headline: {status_title!r}"
    else:
        allowed_next = VALID_TRANSITIONS.get(previous_status, set())
        transition_valid = status in allowed_next
        anomaly_note = (
            None if transition_valid
            else f"Unexpected transition: {previous_status!r} -> {status!r}"
        )

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO listing_status_events (
                    aktenzeichen, status, previous_status, transition_valid, anomaly_note
                ) VALUES (
                    :aktenzeichen, :status, :previous_status, :transition_valid, :anomaly_note
                )
                RETURNING status_event_id
            """),
            {
                "aktenzeichen": aktenzeichen,
                "status": status or status_title,
                "previous_status": previous_status,
                "transition_valid": transition_valid,
                "anomaly_note": anomaly_note,
            },
        )
        status_event_id = result.scalar()

    return status_event_id