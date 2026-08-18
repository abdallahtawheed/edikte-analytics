# Postmortem: Celery worker crash loop (click library regression)

**Date of incident:** 2026-08-13
**Date resolved:** 2026-08-14
**Severity:** Medium — local Airflow orchestration fully non-functional; no data 
loss, no impact to already-collected data or the live Cloud SQL instance.
**Status:** Resolved

## Summary
Adding a 4th pipeline task (dbt) to the local Airflow deployment triggered a full 
image rebuild. After the rebuild, the Celery worker container entered a permanent 
crash loop on startup, `AttributeError: 'NoneType' object has no attribute 'split'` 
inside Celery's own hostname-resolution code. All scheduled and manually-triggered 
DAG runs failed to execute, since no worker was ever available to pick up queued 
tasks. Local development and Airflow-based orchestration were blocked for 
approximately two days while root-causing.

## Impact
- Local Airflow pipeline (scrape/geocode/sync/dbt) non-functional for ~2 days
- No impact to production data: Cloud SQL, BigQuery, and previously-collected 
  listings were entirely unaffected
- No impact to end users: no public dashboard existed yet at the time of this 
  incident

## Timeline
- **2026-08-13**: dbt task added to the DAG; image rebuilt; Celery worker began 
  crash-looping immediately on every startup attempt
- Multiple mitigation attempts made and failed identically: Docker Compose 
  `hostname:` field, explicit `--hostname` string passed to the Celery worker 
  command, Celery's own `%h` hostname template
- Initial (incorrect) hypothesis: Docker Desktop for Windows / WSL2 networking 
  causing unreliable low-level hostname resolution inside containers, a known 
  class of issue on that platform
- Switched Airflow's executor from CeleryExecutor to LocalExecutor as a working 
  interim fix (removes Celery, Redis, and the separate worker container entirely), 
  restoring orchestration capability
- **2026-08-14**: Migrated the development environment to native Linux (Ubuntu), 
  partly to unblock this class of issue permanently. The identical crash 
  reproduced immediately on the completely unmodified official Airflow 
  docker-compose template on native Linux, disproving the original 
  platform-specific hypothesis
- Root cause identified via targeted search: a breaking change in the `click` 
  library (v8.3.0) affecting how Celery's worker command parses its arguments, 
  a known, publicly-documented regression (confirmed via Astronomer's public 
  advisory and the upstream click GitHub issue)
- Fixed by pinning `click==8.2.1` in the Airflow image's requirements
- CeleryExecutor restored; confirmed all 4 pipeline tasks running successfully 
  end-to-end

## Root cause
`click` 8.3.0 introduced a change to command-line argument parsing that broke 
Celery's worker startup command construction, causing Celery's internal 
hostname-formatting logic to receive `None` where it expected a string. This 
was a transitive dependency, `click` was never directly pinned by this project; 
it was pulled in automatically as a dependency of `dbt-bigquery`, added to the 
Airflow image in the same change that triggered the rebuild.

## What went well
- The `LocalExecutor` fallback correctly restored functionality within the 
  same day, keeping development largely unblocked while root-causing continued
- Testing the hypothesis against native Linux (rather than continuing to patch 
  Windows-specific workarounds) was the step that actually surfaced the real 
  cause, migrating environments as a diagnostic step, not just a permanent fix, 
  was the right call
- No production data was ever at risk; the incident was fully contained to 
  local orchestration tooling

## What went wrong / contributing factors
- The initial platform-specific diagnosis was accepted for a full session 
  before being tested against a genuinely different environment; four different 
  mitigation attempts were made against the *same* (wrong) hypothesis before 
  it was seriously questioned
- No pinned `click` version meant a transitive dependency could silently 
  introduce a breaking regression with no warning at build time

## Action items
- [x] Pin `click==8.2.1` in Airflow image requirements
- [x] Restore CeleryExecutor, remove `LocalExecutor` workaround
- [ ] Consider pinning transitive dependencies more broadly (e.g. via 
  `pip-compile`/`uv lock` constraints) to catch similar upstream regressions 
  before they reach a running environment, rather than after
- [ ] When a bug appears environment-specific, test against a genuinely 
  different environment earlier in the investigation, rather than after 
  several same-hypothesis mitigation attempts have already failed