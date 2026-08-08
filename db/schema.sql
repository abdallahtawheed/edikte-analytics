-- edikte-analytics database schema
-- Postgres (Cloud SQL). See docs/SCHEMA.md for design reasoning.

-- ============================================================
-- Core append-only event log
-- ============================================================
CREATE TABLE listing_snapshots (
    snapshot_id         BIGSERIAL PRIMARY KEY,
    aktenzeichen         TEXT NOT NULL,
    scraped_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_hash         TEXT NOT NULL,

    dienststelle          TEXT,
    aktenzeichen_wegen    TEXT,      -- "Zwangsversteigerung einer Liegenschaft" / "...von Wohnungseigentum"
    grundbuch            TEXT,
    ort                  TEXT,
    plz                  TEXT,
    kategorie             TEXT,

    letzte_aenderung      TIMESTAMPTZ,
    bekannt_gemacht_am    DATE,
    berichtigte_fassung   BOOLEAN DEFAULT FALSE,

    status_title          TEXT,      -- raw page headline, e.g. "Zuschlag mit Überbot", not yet validated

    latitude              NUMERIC,   -- derived via geocoding, not scraped
    longitude             NUMERIC,

    raw_html_path         TEXT,      -- pointer to Cloud Storage object

    extra                 JSONB,     -- fields not yet promoted to real columns: Schätzwert,
                                     -- Meistbot, Vadium (non-parcel cases), Betreibende/
                                     -- Verpflichtete Partei, rental info, changelog text, etc.

    CONSTRAINT fk_snapshot_status CHECK (status_title IS NOT NULL)
);

CREATE INDEX idx_snapshots_aktenzeichen ON listing_snapshots (aktenzeichen);
CREATE INDEX idx_snapshots_scraped_at ON listing_snapshots (scraped_at);
CREATE INDEX idx_snapshots_extra ON listing_snapshots USING GIN (extra);

-- ============================================================
-- State machine layer
-- ============================================================
CREATE TABLE listing_status_events (
    status_event_id      BIGSERIAL PRIMARY KEY,
    aktenzeichen          TEXT NOT NULL,
    status                TEXT NOT NULL,
    observed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    previous_status       TEXT,
    transition_valid      BOOLEAN NOT NULL,
    anomaly_note          TEXT
);

CREATE INDEX idx_status_events_aktenzeichen ON listing_status_events (aktenzeichen);
CREATE INDEX idx_status_events_status ON listing_status_events (status);

-- ============================================================
-- Parcels: one row per EZ, the actual purchasable unit
-- ============================================================
CREATE TABLE listing_parcels (
    parcel_id             BIGSERIAL PRIMARY KEY,
    aktenzeichen           TEXT NOT NULL,
    ez                    TEXT NOT NULL,
    grundstuecksnr         TEXT[],    -- e.g. {'2487','2883','2884','5746/14'}
    blnr                  TEXT,

    vadium                 NUMERIC,
    objektgroesse_m2        NUMERIC,   -- 0 is valid (e.g. undeveloped land)
    grundstuecksgroesse_m2  NUMERIC
);

CREATE INDEX idx_parcels_aktenzeichen ON listing_parcels (aktenzeichen);
CREATE INDEX idx_parcels_ez ON listing_parcels (ez);

-- ============================================================
-- Documents: one row per file (photo, floor plan, report, etc.)
-- ============================================================
CREATE TABLE listing_documents (
    document_id            BIGSERIAL PRIMARY KEY,
    aktenzeichen            TEXT NOT NULL,
    doc_type                TEXT NOT NULL,  -- Foto / Lageplan / Grundriss / Kurzgutachten / Langgutachten
    storage_path             TEXT NOT NULL,  -- Cloud Storage object path
    size_kb                  NUMERIC
);

CREATE INDEX idx_documents_aktenzeichen ON listing_documents (aktenzeichen);

-- ============================================================
-- Case links: legally bundled listings ("Alle Edikte zum Fall")
-- ============================================================
CREATE TABLE case_links (
    link_id                 BIGSERIAL PRIMARY KEY,
    aktenzeichen_a           TEXT NOT NULL,
    aktenzeichen_b           TEXT NOT NULL,
    relation_note             TEXT
);

CREATE INDEX idx_case_links_a ON case_links (aktenzeichen_a);
CREATE INDEX idx_case_links_b ON case_links (aktenzeichen_b);

-- ============================================================
-- Flags: keyword-based defect/condition signals from free text
-- (interim step before RAG extension; see DECISIONS.md)
-- ============================================================
CREATE TABLE listing_flags (
    flag_id                 BIGSERIAL PRIMARY KEY,
    aktenzeichen              TEXT NOT NULL,
    snapshot_id               BIGINT REFERENCES listing_snapshots(snapshot_id),
    flag_type                 TEXT NOT NULL,  -- e.g. 'moisture_damage', 'incomplete_construction', 'access_dispute'
    matched_keyword            TEXT,
    source_excerpt             TEXT           -- short surrounding text, for human review, not full reproduction
);

CREATE INDEX idx_flags_aktenzeichen ON listing_flags (aktenzeichen);
CREATE INDEX idx_flags_type ON listing_flags (flag_type);

-- ============================================================
-- View: latest known state per listing, joins snapshot + status
-- ============================================================
CREATE VIEW listings_current AS
SELECT DISTINCT ON (s.aktenzeichen)
    s.*,
    e.status,
    e.observed_at AS status_observed_at,
    e.transition_valid
FROM listing_snapshots s
LEFT JOIN listing_status_events e ON e.aktenzeichen = s.aktenzeichen
ORDER BY s.aktenzeichen, s.scraped_at DESC, e.observed_at DESC;