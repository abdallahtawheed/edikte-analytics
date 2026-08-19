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