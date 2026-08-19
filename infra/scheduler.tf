resource "google_cloud_scheduler_job" "pipeline_daily" {
  name      = "pipeline-daily"
  region    = "europe-west3"
  schedule  = "0 2 * * *"
  time_zone = "Etc/UTC"
  http_target {
    uri         = "https://europe-west3-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/edikte-analytics-2026/jobs/pipeline-job:run"
    http_method = "POST"
    oauth_token {
      service_account_email = "pipeline-runner@edikte-analytics-2026.iam.gserviceaccount.com"
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
  retry_config {
    retry_count          = 0
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }
}