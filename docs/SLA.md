# Data Quality & Reliability Commitments

- **Geocoding coverage**: ≥95% of listings with a resolvable address geocoded 
  within 24 hours of discovery (see ADR-008; ~4% of listings have no genuinely 
  resolvable address in the source data itself, a data limitation, not a 
  pipeline failure)
- **Pipeline execution**: daily scrape/geocode/sync/dbt run completes by 03:00 
  UTC, monitored via Cloud Monitoring alert on job failure
- **Dashboard availability**: public Streamlit dashboard monitored via uptime 
  check (5-minute interval), alerting on any failed check
- **Database backups**: automated daily backups (Cloud SQL), 7-day retention, 
  01:00 UTC. Point-in-time recovery not currently enabled (daily granularity 
  only); local Postgres fallback provides an additional, independent copy