# edikte-analytics

## What this does
Scrapes Austrian judicial property auction listings (Ediktsdatei) on a schedule, 
tracks each listing through its full legal lifecycle, and builds the historical 
price archive that doesn't otherwise exist. Includes geographic plotting, price 
comparison by category/location/size, keyword-based risk flagging, and a 
self-retraining price-estimation model that activates automatically once enough 
real auction outcomes accumulate.

Deployed both to the cloud (public dashboard, scheduled pipeline) and locally 
(personal fallback, continues working independent of cloud credits).

## Live deployment
- **Dashboard:** [Cloud Run URL] — public, multi-page (Listings/Map, Analytics, Case Browser)
- **Analytics report:** [Looker Studio URL]
- Pipeline runs daily via Cloud Scheduler → Cloud Run Job (02:00 UTC): scrape → 
  geocode → sync → dbt → price model training

## Problem statement
No public archive of Austrian judicial auction (Zwangsversteigerung) prices exists. 
The official Ediktsdatei is the only searchable source, but the data is scattered 
across individual listing pages, uses inconsistent terminology, and offers no 
historical view. Once a listing resolves, the information effectively disappears. 
This project scrapes, structures, and tracks listings over their full lifecycle to 
build the dataset that doesn't otherwise exist, and to make sense of what's 
actually happening in it.

## Architecture
See [ARCHITECTURE.md](/docs/ARCHITECTURE.md) for the full pipeline diagram, 
deployment topology (cloud + local), orchestration, and CI details.

## Tech Stack

**Core (v1):**
| Tool | Role |
|---|---|
| Cloud SQL (Postgres) | Transactional store: append-only event log, state machine, parcels, documents, flags, coordinates |
| Local Postgres | Schema-identical fallback copy, toggled via `DB_MODE` env var |
| Cloud Storage | Raw HTML/PDF retention; also stores versioned price model artifacts |
| BigQuery | Analytical layer: dbt marts, price/location/flag analysis, model training run log |
| scikit-learn | Price-ratio estimation model, retrains automatically as data accumulates |
| Airflow (CeleryExecutor, local) | Scheduled scrape, geocode, sync, dbt, model training (dev/manual) |
| Cloud Run Jobs + Cloud Scheduler | Same pipeline, cloud-native, unattended, independent of local machine |
| dbt | Transformation layer (staging → 6 marts), with real schema tests (not_null/unique) |
| Terraform | Infrastructure as code — full coverage of live infrastructure (service accounts, Cloud Run, Scheduler, Secret Manager, monitoring, Dataplex), verified against actual GCP state, not just core resources |
| Streamlit (Cloud Run + local) | Multi-page dashboard: filtering, map, per-object detail, case/BLNr browser, embedded Looker Studio |
| Looker Studio | Analytical reporting on top of BigQuery marts |
| Secret Manager | Credential storage, no secrets in code or CLI args |
| Cloud Monitoring | Pipeline failure alerting + dashboard uptime monitoring, both tested end-to-end |
| GitHub Actions | CI: pytest + dbt tests on every push/PR (no auto-deploy, deliberately) |
| Dataplex | Cataloging across both BigQuery datasets |

**Deferred (v1.5/v2):** LLM-based flag classification (better negation handling 
than keyword matching), RAG over Langgutachten PDFs, price model results surfaced 
in Streamlit (built and running, not yet user-facing), mit/nach Überbot price 
training data (requires tracking overbid-window resolution).

**Explicitly out of scope:** cost and time-to-fix estimation for flagged defects, 
true embedding-based similarity search between listings, auto-deploy-on-merge CI/CD 
(deliberate scope decision given solo-developer scale, see DECISIONS.md).

Full reasoning for each choice, including tools deliberately rejected, in 
[DECISIONS.md](/docs/DECISIONS.md).

## Data model summary
Core pattern: an append-only event log (`listing_snapshots`, one row per detected 
change per object/`source_url`, never overwritten) plus a state machine layer 
(`listing_status_events`, tracked per-object via `source_url`, see ADR-013) 
tracking legal lifecycle transitions (Versteigerung, Verschiebung, Entfall des 
Termins, Zuschlag ohne/mit/nach Überbot, Meistbotsverteilung, Schriftliche Anbote) 
and flagging anomalous jumps.

Supporting tables: `listing_parcels` (EZ/BLNr/size per object), `listing_documents` 
(photos, floor plans, appraisal reports), `listing_flags` (categorized keyword-based 
risk signals), `listing_coordinates` (geocoded, object-level, decoupled from the 
versioned snapshot log).

Fields not yet confirmed stable across enough listings are held in a JSONB `extra` 
column on `listing_snapshots` rather than fixed columns, promoted to real columns 
once confirmed stable (this has already happened for `schaetzwert`, 
`geringstes_gebot`, `meistbot`, `grundbuch`, `kategorie`, and others).

Analytical layer (BigQuery + dbt): staging models (one per raw table) feed six 
marts — `mart_current_objects`, `mart_price_history`, `mart_market_by_region`, 
`mart_flag_summary`, `mart_lifecycle_funnel`, `mart_document_availability`.

Full schema in [SCHEMA.md](/docs/SCHEMA.md).

## Price estimation
`train_price_model.py` runs as the final pipeline stage, predicting 
`meistbot_to_schaetzwert_ratio` (not raw price) via a GradientBoostingRegressor. 
Deliberately refuses to train below 20 rows to avoid overfitting noise; every run, 
including skips, is logged to `model_training_runs` with its reasoning. Fully 
automated: no manual retraining step, improves on its own as real auction outcomes 
accumulate in `mart_price_history`. Not yet surfaced in Streamlit (see Deferred).

## Setup/run instructions

**Local development:**
```bash
uv sync
cp .env.example .env  # fill in DB_PASSWORD, DB_MODE=cloud or local
uv run python run_scrape.py
uv run python src/scraper/run_geocoding.py
uv run streamlit run streamlit_app.py
```

**Local orchestration (Airflow):**
```bash
cd airflow
docker compose up -d --build
# UI at localhost:8080
```

**dbt:**
```bash
cd dbt/edikte_dbt
dbt run
dbt test
```

**Tests:**
```bash
uv run pytest tests/ -v
```

**Cloud deployment** (Streamlit + pipeline job): see `deploy/streamlit/Dockerfile` 
and `deploy/pipeline/Dockerfile`, build/push/deploy commands documented inline 
in DECISIONS.md's relevant ADRs.

**Infrastructure:**
```bash
cd infra
terraform init
terraform plan   # should report no changes if state matches reality
```

Secrets required (never committed): `.env`, `infra/terraform.tfvars`, 
`airflow-key.json`, `airflow/.env`, `dbt/edikte_dbt/profiles_docker.yml` / 
`profiles_cloudrun.yml` / `profiles_ci.yml`. CI additionally requires a 
`GCP_SA_KEY` GitHub repository secret (github-actions-deployer service account).

## Known limitations
- Final sale price for "Zuschlag mit/nach Überbot" outcomes is provisional 
  (subject to a 14-day overbid window) and not reliably final at scrape time; 
  only "Zuschlag ohne Überbot" outcomes are used for price-history training data. 
  Incorporating mit/nach Überbot data would require tracking whether each case's 
  overbid window closed without a higher bid — logged as an open item.
- Property condition/defects exist only as unstructured free text. Flagging is 
  evidence-based keyword matching (see ADR-011) organized into six categories 
  (structural, construction/legality, legal/financial, boundary/access, 
  environmental, buyer restrictions), not a substitute for reading the full report. 
  Negation handling is basic (nearby "nicht/kein" check); LLM-based classification 
  deferred to v1.5/v2.
- ~4% of scraped objects could not be geocoded (informal rural addresses, zone-level 
  descriptions, or genuinely missing addresses in the source data). See ADR-008.
- Schriftliche Anbote (written-offer) pages, a real fallback auction procedure used 
  when no bidder appears in person, use their own distinct field structure; 
  extraction for this page type has been built and verified against real examples.
- **BLNr, the true legally purchasable unit, cannot serve as a universal schema key.** 
  The source site never publishes per-unit pricing for bundled sales (14% of 
  parcels), and BLNr's meaning varies by property category: a genuine unique 
  per-unit identifier for Wohnungseigentum (condominium-style ownership), but a 
  shared ownership-group reference (not unique) for agricultural/forestry land sold 
  "nach Gruppen." `source_url` is the schema's reliable per-object key throughout. 
  `mart_price_history` handles bundled sales via explicit `is_bundled`/`unit_count` 
  features rather than per-unit price attribution. Fully investigated and resolved 
  as an accepted limitation, not an open gap — see the BLNr open item in DECISIONS.md 
  for the complete investigation.
- Cross-lifecycle object tracking (following one real object across its 
  Versteigerung → Zuschlag stage transitions, which use different URLs) has no 
  reliable key across all listing categories; accepted limitation, same 
  investigation as above.
- Local Postgres fallback is a point-in-time copy, not continuously synced; 
  requires running the pipeline manually with `DB_MODE=local` to update it.

Full ADR history in [DECISIONS.md](/docs/DECISIONS.md).