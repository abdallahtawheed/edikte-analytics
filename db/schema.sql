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
    source_url            TEXT,
    dienststelle          TEXT,
    aktenzeichen_wegen    TEXT,
    grundbuch            TEXT,
    ort                  TEXT,
    plz                  TEXT,
    kategorie             TEXT,
    letzte_aenderung      TIMESTAMPTZ,
    bekannt_gemacht_am    DATE,
    berichtigte_fassung   BOOLEAN DEFAULT FALSE,
    status_title          TEXT,
    schaetzwert            NUMERIC,
    geringstes_gebot        NUMERIC,
    meistbot               NUMERIC,
    raw_html_path         TEXT,
    extra                 JSONB,
    CONSTRAINT fk_snapshot_status CHECK (status_title IS NOT NULL)
);
CREATE INDEX idx_snapshots_aktenzeichen ON listing_snapshots (aktenzeichen);
CREATE INDEX idx_snapshots_scraped_at ON listing_snapshots (scraped_at);
CREATE INDEX idx_snapshots_source_url ON listing_snapshots (source_url);
CREATE INDEX idx_snapshots_extra ON listing_snapshots USING GIN (extra);

-- ============================================================
-- State machine layer
-- Tracked per OBJECT (source_url), not per Aktenzeichen. A single
-- case can bundle multiple distinct objects (e.g. an apartment
-- plus several parking spaces, or several land parcels), each with
-- its own independent lifecycle. Originally keyed only by
-- aktenzeichen, which interleaved unrelated objects' status
-- histories into one misleading shared timeline (confirmed via
-- real data, see ADR-013). aktenzeichen is retained on each row
-- for case-level queries, but previous_status/transition_valid are
-- computed per source_url.
-- ============================================================
CREATE TABLE listing_status_events (
    status_event_id      BIGSERIAL PRIMARY KEY,
    aktenzeichen          TEXT NOT NULL,
    source_url            TEXT,
    status                TEXT NOT NULL,
    observed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    previous_status       TEXT,
    transition_valid      BOOLEAN NOT NULL,
    anomaly_note          TEXT
);
CREATE INDEX idx_status_events_aktenzeichen ON listing_status_events (aktenzeichen);
CREATE INDEX idx_status_events_source_url ON listing_status_events (source_url);
CREATE INDEX idx_status_events_status ON listing_status_events (status);

-- ============================================================
-- Parcels
-- ============================================================
CREATE TABLE listing_parcels (
    parcel_id             BIGSERIAL PRIMARY KEY,
    aktenzeichen           TEXT NOT NULL,
    snapshot_id             BIGINT REFERENCES listing_snapshots(snapshot_id),
    ez                    TEXT NOT NULL,
    grundstuecksnr         TEXT[],
    blnr                  TEXT,
    vadium                 NUMERIC,
    objektgroesse_m2        NUMERIC,
    grundstuecksgroesse_m2  NUMERIC
);
CREATE INDEX idx_parcels_aktenzeichen ON listing_parcels (aktenzeichen);
CREATE INDEX idx_parcels_snapshot_id ON listing_parcels (snapshot_id);
CREATE INDEX idx_parcels_ez ON listing_parcels (ez);

-- ============================================================
-- Documents
-- ============================================================
CREATE TABLE listing_documents (
    document_id            BIGSERIAL PRIMARY KEY,
    aktenzeichen            TEXT NOT NULL,
    doc_type                TEXT NOT NULL,
    storage_path             TEXT NOT NULL,
    size_kb                  NUMERIC
);
CREATE INDEX idx_documents_aktenzeichen ON listing_documents (aktenzeichen);

-- ============================================================
-- Case links
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
-- Flags
-- ============================================================
CREATE TABLE listing_flags (
    flag_id                 BIGSERIAL PRIMARY KEY,
    aktenzeichen              TEXT NOT NULL,
    snapshot_id               BIGINT REFERENCES listing_snapshots(snapshot_id),
    category                  TEXT,
    flag_type                 TEXT NOT NULL,
    matched_keyword            TEXT,
    source_excerpt             TEXT
);
CREATE INDEX idx_flags_aktenzeichen ON listing_flags (aktenzeichen);
CREATE INDEX idx_flags_type ON listing_flags (flag_type);

-- ============================================================
-- Geocoded coordinates
-- ============================================================
CREATE TABLE listing_coordinates (
    source_url    TEXT PRIMARY KEY,
    latitude       NUMERIC NOT NULL,
    longitude      NUMERIC NOT NULL,
    geocoded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- View: latest known state per listing (aktenzeichen-level)
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
-- View: latest known state per OBJECT (source_url-level), used
-- by Streamlit. A single case can have multiple objects at different
-- lifecycle stages simultaneously (some auctioned, some not), so
-- joining case-level status here produced wrong/stale results for
-- individual objects. Use status_title (already per-object,
-- correct) classified via classify_status() for object-level
-- status instead. listing_status_events remains valid for
-- case-level anomaly detection (see ADR-010).
-- ============================================================
CREATE VIEW objects_current AS
SELECT DISTINCT ON (s.source_url)
    s.*,
    c.latitude,
    c.longitude,
    p.objektgroesse_m2,
    p.grundstuecksgroesse_m2,
    p.blnr
FROM listing_snapshots s
LEFT JOIN listing_coordinates c ON c.source_url = s.source_url
LEFT JOIN listing_parcels p ON p.snapshot_id = s.snapshot_id
WHERE s.source_url IS NOT NULL
ORDER BY s.source_url, s.scraped_at DESC;