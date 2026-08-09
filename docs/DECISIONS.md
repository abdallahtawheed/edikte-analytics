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