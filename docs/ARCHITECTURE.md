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
| state machine (listing_status_events, tracked per-object via source_url,
| see ADR-013), parcels, documents, flags, coordinates
v
[run_geocoding] -- Nominatim, populates listing_coordinates
|
v
[sync_to_bigquery] -- raw_* tables in BigQuery
|
v
[dbt run] -- staging models -> 6 marts (analytical layer)
|
v
[train_price_model] -- retrains price-ratio model when mart_price_history
| has >= 20 rows; otherwise skips and logs the reason
| (model_training_runs table)
v
[Streamlit dashboard] -- reads from Postgres directly (objects_current view),
  multi-page: Listings/Map, Analytics (embedded Looker Studio), Case Browser

All five pipeline stages run as one sequential script (run_pipeline.py) in
both deployment targets.

## Deployment topology

**Cloud (primary):**
- Cloud SQL (Postgres), BigQuery, GCS
- Streamlit dashboard on Cloud Run (public, streamlit-runner service account,
  Cloud SQL Client role only), instrumented with GA4
- Pipeline (scrape -> geocode -> sync -> dbt -> price model) as a single
  Cloud Run Job (pipeline-runner service account: Cloud SQL Client, BigQuery
  Data Editor, BigQuery Job User, Storage Object Admin for model artifacts),
  triggered daily by Cloud Scheduler (02:00 UTC)
- Cloud Monitoring: alert policy on pipeline-job execution failure; separate
  uptime check + alert policy on the dashboard's public URL (5-minute
  interval); both tested end-to-end with real triggered failures, not just
  configured
- Automated Cloud SQL backups (daily, 7-day retention) with point-in-time
  recovery enabled
- Dataplex lake (edikte-analytics-lake), raw + curated zones, cataloging
  both BigQuery datasets with auto-discovery enabled
- Looker Studio report reading directly from BigQuery marts, embedded in
  the Streamlit Analytics page
- Secret Manager for all credentials (DB password, service account keys
  where unavoidable); no secrets committed or passed as raw CLI arguments

**Local (fallback):**
- Local Postgres, schema-identical copy, switched via DB_MODE=local
  (persist.py, default DB_MODE=cloud); a point-in-time copy, not
  continuously synced, requires a manual pipeline run with DB_MODE=local
  to update
- Local Airflow (Docker Compose, CeleryExecutor, see ADR-012) orchestrating
  the same pipeline against Cloud SQL, for development/manual runs

**Infrastructure as code:**
- Core resources (Cloud SQL, BigQuery datasets, GCS) and organically-grown
  resources (all 4 service accounts, Cloud Run service + job, Cloud
  Scheduler, Secret Manager, all Cloud Monitoring resources, Dataplex
  lake/zones/assets) are fully covered in Terraform (infra/), imported and
  verified against live GCP state (terraform plan reports no drift).
  Ephemeral resources (job executions, container image tags, Cloud Run
  revisions, SQL backups) are deliberately NOT Terraform-managed, they are
  auto-generated side effects, not infrastructure to own.

**CI:**
- GitHub Actions runs on every push/PR to main: pytest (parser logic) and
  dbt schema tests (not_null/unique on key transactional columns), using a
  dedicated github-actions-deployer service account (least-privilege: Cloud
  Run Admin, Service Account User, Storage Admin, BigQuery Job User/Data
  Viewer). Deliberately does not include auto-deploy-on-merge; deploys
  remain a manual, verified step given this project's solo-developer scale.

Both environments share the same codebase; DB_MODE is the only runtime
switch between them. See ADR-009 for a related but distinct constraint
(engine.begin() vs engine.connect()+.commit(), for cross-SQLAlchemy-version
compatibility between local dev and Airflow's environment).

Authentication varies deliberately by environment: local dev uses personal
ADC, Airflow uses a mounted service account key, Cloud Run uses ambient
identity via the metadata server, GitHub Actions uses an explicit key
injected as a secret. Each dbt profile (profiles.yml locally,
profiles_docker.yml, profiles_cloudrun.yml, profiles_ci.yml) matches its
environment's actual available auth mechanism, not a one-size-fits-all
config.

## Orchestration

**Local Airflow** runs:
`scrape_listings >> geocode_new_listings >> sync_to_bigquery >> dbt_run`

**Cloud Run Job** (pipeline-job) runs the same stages plus price model
training as one sequential script (run_pipeline.py), avoiding race
conditions between stages that separately-scheduled jobs would risk.

Each stage is idempotent: change detection via content_hash means unchanged
listings are skipped on rescrape; geocoding only processes objects with no
existing row in listing_coordinates; BigQuery sync does a full refresh
(WRITE_TRUNCATE) each run given current data volume; price model training
skips (and logs why) below a minimum sample size rather than training on
insufficient data.

## Data model, two layers

**Transactional (Postgres/Cloud SQL)**: source of truth, append-only history,
real-time writes from the scraper. See docs/SCHEMA.md for full table details.

**Analytical (BigQuery/dbt)**: derived from the transactional layer via a
one-way sync + transformation pipeline, not written to directly. Staging
models mirror the raw tables with light cleanup, now covered by real dbt
schema tests. Six marts (mart_current_objects, mart_price_history,
mart_market_by_region, mart_flag_summary, mart_lifecycle_funnel,
mart_document_availability) join and aggregate for analysis. See ADR-004
for the reasoning behind this split.

## Price estimation

train_price_model.py predicts meistbot_to_schaetzwert_ratio (not raw price,
for better generalization across property types/sizes) via a
GradientBoostingRegressor, using kategorie, size, bundling status, and
estimate fields as features. Retrains automatically as part of the daily
pipeline; skips training below 20 rows rather than overfitting to a tiny
sample. Every run, including skips, is logged to model_training_runs with
its reasoning and (when trained) cross-validated MAE/R2. Model artifacts
are versioned in Cloud Storage.

## Known, deliberately accepted limitations

- **BLNr** is the true legally purchasable unit but is not usable as a
  universal schema key: the source site never publishes per-unit pricing
  for bundled sales (14% of parcels), and BLNr's meaning varies by listing
  category (unique per-unit identifier for Wohnungseigentum; a shared
  ownership-group reference, not unique, for land sold "nach Gruppen").
  source_url remains the primary per-object key throughout the schema.
  Investigated and resolved via mart_price_history's is_bundled/unit_count
  features rather than a schema rework; full investigation in the BLNr
  open item in DECISIONS.md.
- **Cross-lifecycle object tracking**: the same real object receives a new
  source_url when it transitions between legal stages (Versteigerung ->
  Zuschlag pages are different URLs for the same unit). No field reliably
  identifies "the same object" across stages for every listing category.
  Accepted limitation, same investigation as above.
- **Local Postgres fallback** is a snapshot, not continuously synced.

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