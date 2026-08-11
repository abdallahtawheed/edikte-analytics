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
    source_url            TEXT,      -- the real page this snapshot was scraped from;
                                     -- the true per-object uniqueness key, since one
                                     -- aktenzeichen can cover many distinct objects

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

    raw_html_path         TEXT,      -- pointer to Cloud Storage object (not yet populated)

    extra                 JSONB,     -- fields not yet promoted to real columns: Schätzwert,
                                     -- Meistbot, Vadium (non-parcel cases), Betreibende/
                                     -- Verpflichtete Partei, rental info, changelog text, etc.

    CONSTRAINT fk_snapshot_status CHECK (status_title IS NOT NULL)
);

CREATE INDEX idx_snapshots_aktenzeichen ON listing_snapshots (aktenzeichen);
CREATE INDEX idx_snapshots_scraped_at ON listing_snapshots (scraped_at);
CREATE INDEX idx_snapshots_source_url ON listing_snapshots (source_url);
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
-- Parcels: one row per object-snapshot (EZ + BLNr identify the
-- real purchasable unit; snapshot_id ties this row back to the
-- exact page/scrape it came from)
-- ============================================================
CREATE TABLE listing_parcels (
    parcel_id             BIGSERIAL PRIMARY KEY,
    aktenzeichen           TEXT NOT NULL,
    snapshot_id             BIGINT REFERENCES listing_snapshots(snapshot_id),
    ez                    TEXT NOT NULL,
    grundstuecksnr         TEXT[],    -- e.g. {'2487','2883','2884','5746/14'}
    blnr                  TEXT,       -- the real per-object identifier within an EZ,
                                     -- confirmed via real listings to carry its own
                                     -- independent valuation (Schätzwert/Vadium/Gebot)

    vadium                 NUMERIC,
    objektgroesse_m2        NUMERIC,   -- 0 is valid (e.g. undeveloped land)
    grundstuecksgroesse_m2  NUMERIC
);

CREATE INDEX idx_parcels_aktenzeichen ON listing_parcels (aktenzeichen);
CREATE INDEX idx_parcels_snapshot_id ON listing_parcels (snapshot_id);
CREATE INDEX idx_parcels_ez ON listing_parcels (ez);

-- ============================================================
-- Documents: one row per file (photo, floor plan, report, etc.)
-- ============================================================
CREATE TABLE listing_documents (
    document_id            BIGSERIAL PRIMARY KEY,
    aktenzeichen            TEXT NOT NULL,
    doc_type                TEXT NOT NULL,  -- Foto / Lageplan / Grundriss / Kurzgutachten / Langgutachten
    storage_path             TEXT NOT NULL,  -- full source URL (or Cloud Storage path once mirrored)
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
-- Geocoded coordinates, one row per real object (source_url),
-- deliberately NOT versioned like listing_snapshots: an address's
-- coordinates don't change when price/status fields change, so
-- coupling lat/long to the append-only snapshot log caused every
-- new snapshot to "forget" previously-resolved coordinates.
-- ============================================================
CREATE TABLE listing_coordinates (
    source_url    TEXT PRIMARY KEY,
    latitude       NUMERIC NOT NULL,
    longitude      NUMERIC NOT NULL,
    geocoded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- View: latest known state per listing (aktenzeichen-level),
-- joins snapshot + status. Note: for multi-object aktenzeichens,
-- this collapses to one row per case, not one per object. Use
-- listing_snapshots + listing_parcels directly for object-level
-- queries (e.g. mapping every individual parking space/unit).
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

-- ============================================================
-- View: latest known state per OBJECT (source_url-level), the
-- correct granularity for browsing/mapping, unlike listings_
-- current which collapses multi-object aktenzeichens to one row.
-- Joins in coordinates directly since that's the primary reason
-- this view exists (feeding the Streamlit map).
-- ============================================================
CREATE VIEW objects_current AS
SELECT DISTINCT ON (s.source_url)
    s.*,
    e.status,
    e.observed_at AS status_observed_at,
    e.transition_valid,
    c.latitude,
    c.longitude
FROM listing_snapshots s
LEFT JOIN listing_status_events e ON e.aktenzeichen = s.aktenzeichen
LEFT JOIN listing_coordinates c ON c.source_url = s.source_url
WHERE s.source_url IS NOT NULL
ORDER BY s.source_url, s.scraped_at DESC, e.observed_at DESC;