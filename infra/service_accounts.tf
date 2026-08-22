module "pipeline_runner" {
  source       = "./modules/service_account"
  account_id   = "pipeline-runner"
  display_name = "Pipeline jobs (scrape, geocode, sync, dbt)"
  project_id   = "edikte-analytics-2026"
  roles        = [
    "roles/cloudsql.client",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/storage.objectAdmin",
    "roles/run.invoker",
  ]
}

module "streamlit_runner" {
  source       = "./modules/service_account"
  account_id   = "streamlit-runner"
  display_name = "Streamlit Cloud Run app"
  project_id   = "edikte-analytics-2026"
  roles = [
    "roles/cloudsql.client",
    "roles/bigquery.jobUser",
    "roles/bigquery.dataViewer",
    "roles/storage.objectViewer",
  ]
}


module "airflow_runner" {
  source       = "./modules/service_account"
  account_id   = "airflow-runner"
  display_name = "Airflow pipeline runner"
  project_id   = "edikte-analytics-2026"
  roles        = [
    "roles/cloudsql.client",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
  ]
}

module "github_actions_deployer" {
  source       = "./modules/service_account"
  account_id   = "github-actions-deployer"
  display_name = "GitHub Actions CI/CD"
  project_id   = "edikte-analytics-2026"
  roles = [
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/storage.admin",
    "roles/bigquery.jobUser",
    "roles/bigquery.dataViewer",
  ]
}



