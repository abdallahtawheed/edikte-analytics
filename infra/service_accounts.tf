resource "google_service_account" "pipeline_runner" {
  account_id   = "pipeline-runner"
  display_name = "Pipeline jobs (scrape, geocode, sync, dbt)"
}

resource "google_service_account" "streamlit_runner" {
  account_id   = "streamlit-runner"
  display_name = "Streamlit Cloud Run app"
}

resource "google_service_account" "airflow_runner" {
  account_id   = "airflow-runner"
  display_name = "Airflow pipeline runner"
}

resource "google_service_account" "github_actions_deployer" {
  account_id   = "github-actions-deployer"
  display_name = "GitHub Actions CI/CD"
}

resource "google_project_iam_member" "github_actions_run_admin" {
  project = "edikte-analytics-2026"
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}

resource "google_project_iam_member" "github_actions_sa_user" {
  project = "edikte-analytics-2026"
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}

resource "google_project_iam_member" "github_actions_storage_admin" {
  project = "edikte-analytics-2026"
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}

resource "google_project_iam_member" "github_actions_bq_job_user" {
  project = "edikte-analytics-2026"
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}

resource "google_project_iam_member" "github_actions_bq_data_viewer" {
  project = "edikte-analytics-2026"
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.github_actions_deployer.email}"
}