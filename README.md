# edikte-analytics

## What this does

Scrapes Austrian judicial property auction listings (Ediktsdatei) on a schedule, 
tracks each listing through its full legal lifecycle, and builds the historical 
price archive that doesn't otherwise exist. Includes geographic plotting, price 
comparison by category/location/size, and a price-estimation model trained on 
recoverable historical outcomes.

# Problem statement

No public archive of Austrian judicial auction (Zwangsversteigerung) prices exists. 
The official Ediktsdatei is the only searchable source, but the data is scattered 
across individual listing pages, uses inconsistent terminology, and offers no 
historical view. Once a listing resolves, the information effectively disappears. 
This project scrapes, structures, and tracks listings over their full lifecycle to 
build the dataset that doesn't otherwise exist, and to make sense of what's 
actually happening in it.

# Architecture Diagram

[TBD]

# Tech Stack

**Core (v1):**

| Tool | Role |
|---|---|
| Cloud SQL (Postgres) | Transactional store: append-only event log, state machine, parcels, documents |
| Cloud Storage | Raw HTML/PDF retention for re-parsing without re-scraping |
| BigQuery | Analytical layer: dbt marts, price/location analysis |
| Dataplex | Cataloging and lineage across Cloud SQL and BigQuery |
| Airflow | Scheduled scrape, parse, geocode, diff, alert pipeline |
| dbt | Transformation layer (staging to marts) |
| Terraform | Infrastructure as code for all GCP resources |
| Streamlit | Filtering, timeline, and map interface on top of the data |

**Planned extensions (not in v1):** RAG over Langgutachten PDFs for condition/defect 
flagging, GA4 usage tracking, keyword-based defect flagging as an interim step before RAG.

**Explicitly out of scope:** cost and time-to-fix estimation for flagged defects, 
true embedding-based similarity search between listings (basic filter-based 
similarity by category, region, and size is in scope; see Data model summary).

Full reasoning for each choice, including tools deliberately rejected, in 
[DECISIONS.md](/docs/DECISIONS.md).

# Data model summary

Core pattern: an append-only event log (`listing_snapshots`, one row per detected 
change per Aktenzeichen, never overwritten) plus a validated state machine layer 
(`listing_status_events`) tracking legal lifecycle transitions (Versteigerung, 
Verschiebung, Entfall des Termins, Zuschlag ohne/mit/nach Überbot, 
Meistbotsverteilung) and flagging anomalous jumps.

Supporting tables: `listing_parcels` (one row per EZ, since that is the actual 
purchasable unit, with its own Vadium, size, and land parcel list), 
`listing_documents` (photos, floor plans, site plans, appraisal reports), and 
`case_links` (legally bundled listings, e.g. an apartment and its associated 
parking spaces auctioned as separate edikts).

Fields not yet confirmed stable across enough listings (Schätzwert, Meistbot, 
Betreibende/Verpflichtete Partei, rental status, etc) are held in a JSONB `extra` 
column on `listing_snapshots` rather than fixed columns, deliberately, until their 
shape is well understood. These get promoted to real columns once confirmed stable. 
Full schema in [SCHEMA.md](/docs/SCHEMA.md).

# Setup/run instructions

[TBD]

# Known limitations

- Final sale price for "Zuschlag mit/nach Überbot" outcomes is not published by 
  the source and cannot be recovered without direct court or notary follow-up. 
  Only "Zuschlag ohne Überbot" outcomes (minimum bid equals final price) provide 
  a reliable historical price signal.
- Some listing fields (property condition, defects) exist only as unstructured 
  free text within the appraisal description, not as structured fields. Initial 
  handling is keyword-based flagging; not a substitute for reading the full report.
- Cost and time to remediate flagged defects is not estimated, this would require 
  construction-cost domain knowledge outside this project's scope.
- ~4% of scraped objects (17 of 425 as of Aug 2026) could not be geocoded, mostly 
  due to informal rural location descriptions, zone-level addresses, or genuinely 
  missing street addresses in the source data itself, not a tooling gap. See 
  ADR-008 for the full breakdown.

Full ADR history in [DECISIONS.md](/docs/DECISIONS.md).