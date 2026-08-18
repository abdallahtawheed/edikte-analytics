# Architecture

## Pipeline overview

Ediktsdatei (source)
|
v
[discover_listings] -- scrapes search results, returns listing URLs
|
v
[fetch_listing] -- raw HTML per listing
|
v
[parse_listing] -- extracts fields, computes content_hash, scans for flags
|
v
[Postgres / Cloud SQL] -- append-only event log (listing_snapshots),
| state machine (listing_status_events),
| parcels, documents, flags, coordinates
v
[run_geocoding] -- Nominatim, populates listing_coordinates
|
v
[sync_to_bigquery] -- raw_* tables in BigQuery
|
v
[dbt run] -- staging models -> marts (analytical layer)
|
v
[Streamlit dashboard] -- reads from Postgres directly (objects_current view),
  multi-page: Listings/Map, Analytics (embedded Looker Studio), Case Browser

## Deployment topology

**Cloud (primary):**
- Cloud SQL (Postgres), BigQuery, GCS
- Streamlit dashboard on Cloud Run (public, streamlit-runner service account,
  Cloud SQL Client role only)
- Pipeline (scrape -> geocode -> sync -> dbt) as a single Cloud Run Job
  (pipeline-runner service account: Cloud SQL Client, BigQuery Data Editor,
  BigQuery Job User), triggered daily by Cloud Scheduler (02:00 UTC)
- Cloud Monitoring alert policy on pipeline-job execution failure, email 
  notification via a dedicated notification channel
- Dataplex lake (edikte-analytics-lake), raw + curated zones, cataloging 
  both BigQuery datasets with auto-discovery enabled
- Looker Studio report reading directly from BigQuery marts

**Local (fallback):**
- Local Postgres, schema-identical copy, switched via DB_MODE=local
  (persist.py, default DB_MODE=cloud)
- Local Airflow (Docker Compose, CeleryExecutor) orchestrating the same
  pipeline against Cloud SQL, for development/manual runs

Both environments share the same codebase; DB_MODE is the only runtime
switch between them. See ADR-009 for a related but distinct constraint
(engine.begin() vs engine.connect()+.commit(), for cross-SQLAlchemy-version
compatibility between local dev and Airflow's environment).

## Orchestration

**Local Airflow** (Docker Compose, CeleryExecutor, see ADR-012) runs:
`scrape_listings >> geocode_new_listings >> sync_to_bigquery >> dbt_run`

**Cloud Run Job** (pipeline-job) runs the same four stages as one sequential
script (run_pipeline.py) rather than four separately-scheduled jobs, avoiding
race conditions between stages. Triggered daily via Cloud Scheduler.

Each stage is idempotent: change detection via content_hash means unchanged
listings are skipped on rescrape; geocoding only processes objects with no
existing row in listing_coordinates; BigQuery sync does a full refresh
(WRITE_TRUNCATE) each run given current data volume.

## Data model, two layers

**Transactional (Postgres/Cloud SQL)**: source of truth, append-only history,
real-time writes from the scraper. See docs/SCHEMA.md for full table details.

**Analytical (BigQuery/dbt)**: derived from the transactional layer via a
one-way sync + transformation pipeline, not written to directly. Staging
models mirror the raw tables with light cleanup; six marts (mart_current_objects,
mart_price_history, mart_market_by_region, mart_flag_summary,
mart_lifecycle_funnel, mart_document_availability) join and aggregate for
analysis. See ADR-004 for the reasoning behind this split.

## Known, deliberately accepted limitation

BLNr is the true legally purchasable unit but is not usable as a universal
schema key: the source site never publishes per-unit pricing for bundled
sales, and BLNr's meaning varies by listing category (unique per-unit
identifier for Wohnungseigentum; a shared ownership-group reference, not
unique, for land sold "nach Gruppen"). source_url remains the primary
per-object key throughout the schema. See the BLNr open item in
DECISIONS.md for the full investigation.

## Key architectural decisions, quick index

- ADR-001: Batch, not streaming, ingestion
- ADR-002: GCP over AWS
- ADR-003: No Spark/distributed compute at current scale
- ADR-004: Postgres (OLTP) + BigQuery (OLAP) split
- ADR-005: ADC for local dev auth, service account for Airflow/Cloud Run
- ADR-007: source_url (not aktenzeichen) as the per-object identity/change-detection key
- ADR-009: engine.begin() required for cross-SQLAlchemy-version compatibility
- ADR-010: Object-level status derived from status_title, not the case-level state machine
- ADR-011: Evidence-based flag keyword selection
- ADR-012: CeleryExecutor (restored after identifying the real root cause, a
  click library regression, not a platform issue)
- ADR-013: listing_status_events rekeyed to source_url (object-level)