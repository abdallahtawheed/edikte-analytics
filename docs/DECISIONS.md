## ADR-001: Batch orchestration with Airflow, not a streaming architecture

**Date:** 2026-08-08
**Status:** Accepted

**Context:** Ediktsdatei is a static government webpage updated periodically by court 
offices, not a continuously-producing system. Needed to decide whether to build a 
streaming pipeline (Kafka + consumers) or a scheduled batch pipeline.

**Decision:** Poll the source on a fixed schedule (daily) via Airflow, diff against 
the last snapshot, and write new/changed rows to the event log.

**Alternatives considered:** Kafka-based streaming ingestion. Rejected - there is no 
producer here. A producer is a system actively pushing discrete events in real time 
(a sensor, a web server emitting click events). Ediktsdatei has no equivalent; the 
scraper must actively pull and compare against prior state, which is a batch/pull 
pattern by nature, not a stream/push one. Using Kafka here would add operational 
complexity without a corresponding architectural need, purely to list the tool.

**Consequences:** Update latency is bounded by poll frequency (up to ~24h), which is 
acceptable - auction lifecycle changes (postponement, status transitions) do not 
require near-real-time detection.

## ADR-002: GCP over AWS

**Date:** 2026-08-08
**Status:** Accepted

**Context:** Existing hands-on experience (RDS, EC2) is on AWS, from a prior personal 
project. GCP was considered as an alternative for this project specifically to build 
exposure to a second major cloud provider. Job postings targeted for this project's 
relevance showed Dataplex appearing repeatedly, while DataHub did not.

**Decision:** Use GCP (Cloud SQL, Cloud Storage, BigQuery, Dataplex) for this project.

**Alternatives considered:** Staying on AWS, leveraging existing RDS/EC2 experience 
directly, and running DataHub for governance there instead. DataHub is not 
AWS specific and could technically run on GCP as well, but Dataplex was chosen because 
it is GCP native (tighter integration with BigQuery and Cloud SQL, no separate service 
to host) and it is the tool that actually appeared in the target job postings. Azure 
was also considered and rejected, not because it is a worse fit, but to avoid spreading 
cloud exposure across three providers with no project depth in any of them. Azure is 
reserved for a possible future project instead.

**Consequences:** Existing AWS experience (RDS, EC2 from the labor market project) 
does not get reinforced or deepened here. This is a deliberate tradeoff, not an 
oversight, in favor of broadening rather than deepening cloud exposure at this stage. 
Some relearning of equivalent concepts under different naming and conventions is 
required.

## ADR-003: No Spark/Dask/Hadoop at current data volume

**Date:** 2026-08-08
**Status:** Accepted

**Context:** Spark, Dask, and Hadoop are frameworks for distributed processing across 
multiple machines, built for data volumes that don't fit or don't process efficiently 
on a single node. A search-results sample from Ediktsdatei showed ~88 new/updated 
listings per week, nationally, across all property categories, several orders of 
magnitude below the volume these tools are designed for.

**Decision:** Do not use Spark, Dask, or Hadoop. Process data with plain Python/Pandas 
and Postgres/BigQuery SQL.

**Alternatives considered:** Generating synthetic data to artificially inflate volume 
and justify using one of these tools. Rejected, this would mean building the project 
around a fabricated constraint instead of the real one, which defeats the purpose of 
having a defensible architecture at all.

**Consequences:** If the project were later expanded significantly in scope (e.g. 
beyond Austria, or to a much higher-frequency data source), this decision would need 
to be revisited. At current scale, revisiting it would itself be a bad sign, a 
correct decision doesn't need reversing just because more tools exist.

## ADR-004: Postgres for transactional layer, BigQuery for analytical layer

**Date:** 2026-08-08
**Status:** Accepted

**Context:** BigQuery is capable of handling both transactional writes and analytical 
queries, so using it alone for everything was a real option, not a strawman.

**Decision:** Use Cloud SQL (Postgres) as the transactional store for the append-only 
event log and state machine, and BigQuery as a separate analytical layer fed by dbt 
transformations from Postgres.

**Alternatives considered:** BigQuery for both OLTP and OLAP. Rejected - BigQuery is 
optimized for large scan-heavy analytical queries, not frequent small row-level writes 
and updates, which the event log and state machine require continuously as listings 
change. Splitting the two also means ingestion and analytics fail independently: a bug 
in the scrape/write path doesn't take down the analytical layer, and a broken dbt model 
doesn't block new data from being captured.

**Consequences:** Requires a sync step (dbt) moving data from Postgres into BigQuery on 
a schedule - an additional moving part, and a place things can break that wouldn't 
exist in a single-database design. Accepted as worth it for the isolation benefit above.

## ADR-005: Application Default Credentials for local Terraform auth, not a service account key

**Date:** 2026-08-08
**Status:** Accepted

**Context:** Terraform needs GCP credentials to provision resources. Two standard 
options exist: Application Default Credentials (ADC, reusing the developer's own 
gcloud login) or a dedicated service account with a downloaded JSON key file.

**Decision:** Use ADC (`gcloud auth application-default login`) for local development.

**Alternatives considered:** A dedicated service account with a JSON key, originally 
planned. Reconsidered because a downloaded key file is a credential sitting on disk 
that must never be committed to git, and leaked service account keys are a common, 
real way personal cloud projects get compromised. For a solo developer running 
Terraform locally, ADC provides the same functionality with meaningfully less risk 
surface, since there is no key file to leak in the first place.

**Consequences:** This project's current IAM setup is not representative of how a 
team or production environment would authenticate automated systems, since a 
scheduled Airflow pipeline running unattended (not on a developer's own machine) 
would need a scoped service account regardless. That is a deliberate future addition 
once Airflow moves off local execution, not an oversight in the current setup.

## ADR-006: Prose-based extraction for Zuschlag sale prices

**Date:** 2026-08-10
**Status:** Accepted

**Context:** The generic div.row label:value parser correctly handles most fields, 
but Zuschlag-type listings (ohne/mit/nach Uberbot) embed the actual sale price 
(Meistbot) in a prose sentence rather than a structured field, e.g. "...um das 
Meistbot von 314.000,00 EUR zugeschlagen." This was initially missed entirely, 
confirmed by testing against real scraped data rather than assumed correct.

**Decision:** Added a secondary regex-based extraction pass over the full page 
text, run after the main div.row loop, specifically targeting this sentence 
pattern. Captured value is normalized into the same raw_fields dict as other 
price fields so downstream parsing (parse_de_number) handles it identically.

**Alternatives considered:** None seriously, this is the only place the value 
exists on the page. The real alternative considered was whether to silently 
accept the gap versus fix it, rejected since Zuschlag ohne Uberbot listings are 
the one reliable historical price signal this entire project is built around.

**Consequences:** Confirmed via real batch run: 173 listings picked up newly 
extracted Meistbot values on rerun, correctly detected as changed content via 
the hash mechanism, no manual cleanup needed.

## ADR-007: BLNr as per-object identity, source_url as change-detection key

**Date:** 2026-08-10
**Status:** Accepted

**Context:** Discovered that a single Aktenzeichen can represent many distinct 
purchasable objects (e.g. an apartment plus its parking spaces, or multiple 
storage/motorbike spaces in one building), each sharing one EZ but each carrying 
its own BLNr, its own detail page, and, confirmed via real Versteigerung listings, 
its own independently-set Schätzwert/Vadium/Geringstes Gebot. Original change-detection 
logic keyed on Aktenzeichen alone, causing every object under a multi-object case to 
be treated as a change of every other object, producing runaway duplicate inserts.

**Decision:** Change-detection now keys on source_url, guaranteed unique per real 
page. listing_parcels gains a snapshot_id foreign key, linking each parcel row to 
the specific object/page it was extracted from, rather than only the shared 
Aktenzeichen.

**Alternatives considered:** Keying on (Aktenzeichen, BLNr) instead of source_url. 
Rejected as primary key for change detection since BLNr's raw text format varies 
across listings (plain numbers, ranges, fractional-share notation), making it 
less reliable than the site's own guaranteed-unique URL for this specific purpose. 
BLNr remains a first-class, meaningful field on listing_parcels.

**Consequences:** Confirms the project's real unit of analysis, for pricing, 
mapping, and eventual bidding research, is the individual object (source_url/BLNr 
level), not the Aktenzeichen case. This should inform how Streamlit later presents 
listings: grouped by case, but browsable and analyzable at the object level.

## ADR-008: Accept ~96% geocoding coverage, defer further address-cleaning refinement

**Date:** 2026-08-10
**Status:** Accepted

**Context:** After fixing multi-street address parsing (splitting on comma/slash/
"und"), 407 of 425 real objects geocoded successfully via Nominatim. The remaining 
17 failures break down into: genuinely missing addresses ("keine"), informal rural 
location descriptions ("Bergwerk 1", "neben Kleindorf I/5"), zone/area names rather 
than street addresses ("Gewerbezone Zell bei Ebenthal"), addresses in villages 
likely below Nominatim's data granularity, and a small number where the cleaning 
regex may still be incomplete (e.g. "u." as an abbreviation for "und" not handled).

**Decision:** Accept the current ~96% geocoding coverage as sufficient for now. Do 
not invest further time refining address-cleaning edge cases at this stage.

**Alternatives considered:** Further regex refinement (handling "u." abbreviation, 
adjusting slash-splitting to avoid breaking "Stg. 2/7"-style unit references), or a 
paid/more capable geocoding service. Rejected for now: most remaining failures are 
genuinely unresolvable from the source data itself (no real address exists), not a 
tooling gap, so the ceiling on further improvement from code changes alone is low.

**Consequences:** A small number of real objects, mostly undeveloped land, informal 
rural descriptions, and zone-level addresses, will not appear on map views. This is 
an honest data limitation to note in the README, not a hidden gap. Worth revisiting 
if a future systematic review shows the failure count growing disproportionately as 
more listings are scraped, or if map coverage becomes a more central feature.

## ADR-009: SQLAlchemy version must not be pinned in Airflow's environment

**Date:** 2026-08-11
**Status:** Accepted

**Context:** Airflow's own internals (flask-appbuilder, apache-airflow-core) depend 
on SQLAlchemy 1.4.x specifically, and this dependency is not visible from outside 
Airflow's own package metadata. Initially built the Airflow Docker image's 
requirements.txt by copying exact versions from the local project's uv.lock, 
including sqlalchemy==2.0.51 and pandas==3.0.5, matching what the scraper code was 
developed and tested against locally.

This broke Airflow in two stages. First, installing SQLAlchemy 2.0.51 overwrote 
Airflow's required 1.4.x version at image build time, breaking flask-appbuilder and 
causing the airflow-apiserver container to fail its healthcheck entirely. Fixing the 
version pin resolved that, but surfaced a second, more subtle issue: application 
code written against SQLAlchemy 2.0's Connection.commit() method failed at runtime 
inside Airflow's containers, where SQLAlchemy 1.4's Connection object does not 
expose that method the same way.

**Decision:** Do not pin sqlalchemy or pandas in the Airflow image's 
requirements.txt; let Airflow's own installed versions stand. Separately, rewrote 
all database write functions (insert_snapshot, insert_parcel, insert_status_event, 
insert_coordinates) to use engine.begin() instead of engine.connect() + explicit 
.commit(), since begin()'s auto-commit-on-success behavior is syntax that works 
identically across SQLAlchemy 1.4 and 2.0.

**Alternatives considered:** Running Airflow tasks in an isolated virtualenv per 
task (Airflow supports this via PythonVirtualenvOperator), which would allow 
pinning any version freely. Rejected for now as unnecessary added complexity at 
this project's scale; the engine.begin() fix makes the existing code portable 
without needing environment isolation per task.

**Consequences:** Any future code touching the database must use engine.begin() 
rather than engine.connect() + .commit(), to remain compatible with both the local 
development environment (SQLAlchemy 2.0) and Airflow's runtime (SQLAlchemy 1.4). 
This is now a real constraint on the codebase, not just a one-off fix, worth noting 
for anyone extending it.

## ADR-010: Object-level status must be derived from status_title, not the case-level state machine

**Date:** 2026-08-12
**Status:** Accepted

**Context:** listing_status_events tracks status transitions keyed by aktenzeichen 
(case), consistent with its original design purpose (case-level anomaly detection). 
Discovered via real data that objects_current's join against this table produced 
incorrect status values when a single Aktenzeichen has multiple objects at 
different lifecycle stages simultaneously (e.g. one object already sold via 
Zuschlag while a sibling object under the same case is still pre-auction). The 
joined status reflected whichever object was most recently scraped for that 
Aktenzeichen, not the specific object being displayed.

**Decision:** objects_current no longer joins listing_status_events. Object-level 
status is derived by classifying each row's own status_title (already correctly 
per-object) via classify_status(), applied in the application layer (Streamlit).

**Alternatives considered:** Rekeying listing_status_events to source_url instead 
of aktenzeichen. Rejected for now, since case-level anomaly detection (its original 
purpose) is still a legitimate, separate use case worth preserving; rekeying would 
conflate two different questions ("is this case's history normal" vs "what state is 
this object in") into one table.

**Consequences:** Two parallel status concepts now coexist deliberately: 
status_title/classify_status() for accurate per-object display, and 
listing_status_events for case-level transition validation. Any future feature 
needing "current status" must be explicit about which granularity it means.

## ADR-011: Evidence-based flag keyword selection via corpus frequency analysis

**Date:** 2026-08-12
**Status:** Accepted

**Context:** Original flag keywords (ADR/design decision from earlier in the 
project) were selected by manually reading ~15 individual listings during 
development, not validated against the full scraped corpus. This risked both 
missing genuinely common risk terms and including boilerplate legal language 
that happens to sound risk-related.

**Decision:** Ran word-frequency analysis across all ~450 scraped listings' 
Beschreibung/Sonstige Hinweise text, reviewed top-100 and rare-word tails, and 
spot-checked ambiguous candidates against real excerpts before inclusion or 
rejection. Confirmed several new real categories (financial arrears, boundary 
disputes, environmental contamination, foreign-buyer restrictions, unauthorized 
construction) and explicitly rejected several high-frequency candidates that 
turned out to be standard legal boilerplate present on nearly every listing 
regardless of actual risk (Risiko, Räumung, Delogierung, Wiederversteigerung, 
Schuld, Errichtet, Abgaben).

**Alternatives considered:** LLM-based classification (sending listing text to 
an LLM for context-aware risk extraction) would likely outperform keyword 
matching, particularly for negation handling (e.g. "NOT registered as a 
contaminated site" vs "IS registered"). Deferred to v1.5/v2: real cost, latency, 
and reliability tradeoffs versus the immediate, evidence-backed keyword approach 
built here.

**Consequences:** Flags are now organized into explicit categories (structural 
damage, construction/legality, legal/financial, boundary/access, environmental, 
buyer restrictions) rather than a flat list, both for more meaningful Streamlit 
display and to make future additions easier to reason about. Existing regex 
patterns remain vulnerable to negation (a "not contaminated" statement could 
still match a bare "Altlast" pattern); this is a known, accepted limitation 
pending the eventual LLM-based approach.