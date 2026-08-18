# Runbook

## Pipeline job failed (Cloud Monitoring alert received)

1. Check the failed execution's logs:

gcloud run jobs executions list --job=pipeline-job --region=europe-west3
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=pipeline-job AND labels."run.googleapis.com/execution_name"="<execution-id>" AND severity>=ERROR" --limit 50 --format "value(textPayload)"

2. Common causes and fixes:
   - **Missing file in image** ("No such file or directory"): the Docker image is 
     stale or a COPY step is missing. Rebuild: `docker build -f deploy/pipeline/Dockerfile -t gcr.io/edikte-analytics-2026/pipeline-jobs . --no-cache`, push, `gcloud run jobs update pipeline-job --image ...`
   - **Auth/permission error**: check the relevant service account 
     (`pipeline-runner`) has the needed IAM role. See DECISIONS.md ADR-005 
     for the full least-privilege setup.
   - **dbt profile error**: confirm `profiles_cloudrun.yml` is correctly 
     copied and renamed to `profiles.yml` inside the image at build time.
   - **Scraper error on a specific listing**: usually self-healing, 
     `process_listing()` catches and logs per-listing errors without 
     killing the run. Only worth investigating if the whole run failed.
3. Manually retrigger once fixed:

gcloud run jobs execute pipeline-job --region europe-west3

4. If the fix isn't obvious within a few minutes, the pipeline can safely 
   wait until tomorrow's scheduled run, no data is lost by a missed day, 
   the scraper is idempotent and will pick up where it left off.

## Dashboard uptime alert received (dashboard unreachable)

1. Confirm it's really down:

curl -I $(gcloud run services describe edikte-analytics-dashboard --region europe-west3 --format="value(status.url)")

2. Check recent deploys, a bad deploy is the most likely cause:

gcloud run revisions list --service=edikte-analytics-dashboard --region=europe-west3

3. Roll back to the last known-good revision:

gcloud run services update-traffic edikte-analytics-dashboard --region=europe-west3 --to-revisions=<revision-name>=100

4. Once the real fix is in place, restore to latest:

gcloud run services update-traffic edikte-analytics-dashboard --region=europe-west3 --to-latest

5. **Always verify current traffic state after any rollback/restore**, it's 
   easy to leave the service pinned to an old revision by mistake:

gcloud run services describe edikte-analytics-dashboard --region=europe-west3 --format="value(status.traffic)"


## Database issue / suspected data corruption

1. Cloud SQL automated backups: daily, 7-day retention, point-in-time 
   recovery enabled (as of 2026-08-16).
2. Restore via console: Cloud SQL → edikte-analytics-db → Backups → select 
   backup or specific timestamp → Restore.
3. Independent fallback: local Postgres copy exists (point-in-time snapshot, 
   not continuously synced), accessible via `DB_MODE=local`.

## Credentials/secrets need rotating

1. Service account keys: `gcloud iam service-accounts keys create ...` 
   (generate new), then delete the old key from the GCP console (IAM → 
   Service Accounts → the account → Keys tab).
2. DB password: update in Secret Manager (`gcloud secrets versions add 
   db-password --data-file=-`), Cloud Run services automatically pick up 
   `:latest` on next revision deploy (existing running revisions do NOT 
   pick up a new secret version without a redeploy).

## Full outage / start from scratch

See docs/ARCHITECTURE.md for the complete deployment topology. Core 
resources (Terraform-managed): Cloud SQL, Cloud Storage, BigQuery dataset. 
Manually-created (documented in DECISIONS.md and this runbook): service 
accounts, Cloud Run services/jobs, Cloud Scheduler, Secret Manager entries, 
monitoring policies, Dataplex lake.