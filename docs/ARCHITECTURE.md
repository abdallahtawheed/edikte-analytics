markdown
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
[Streamlit dashboard] -- reads from Postgres directly (objects_current view)


## Orchestration

Airflow (Docker Compose, LocalExecutor) runs the pipeline daily:
`scrape_listings >> geocode_new_listings >> sync_to_bigquery >> dbt_run`

Each stage is idempotent: change detection via content_hash means unchanged 
listings are skipped on rescrape; geocoding only processes objects with no 
existing row in listing_coordinates; BigQuery sync does a full refresh 
(WRITE_TRUNCATE) each run given current data volume.

## Data model, two layers

**Transactional (Postgres/Cloud SQL)**: source of truth, append-only history, 
real-time writes from the scraper. See docs/SCHEMA.md for full table details.

**Analytical (BigQuery/dbt)**: derived from the transactional layer via a 
one-way sync + transformation pipeline, not written to directly. Staging models 
mirror the raw tables with light cleanup; marts (currently: mart_current_objects) 
join and aggregate for analysis. See ADR-004 for the reasoning behind this split.

## Key architectural decisions, quick index

- ADR-001: Batch, not streaming, ingestion
- ADR-002: GCP over AWS
- ADR-003: No Spark/distributed compute at current scale
- ADR-004: Postgres (OLTP) + BigQuery (OLAP) split
- ADR-005: ADC for local dev auth, service account for Airflow
- ADR-007: source_url (not aktenzeichen) as the per-object identity/change-detection key
- ADR-010: Object-level status derived from status_title, not the case-level state machine
- ADR-011: Evidence-based flag keyword selection
- ADR-012: LocalExecutor over CeleryExecutor (Windows/Docker Desktop compatibility)