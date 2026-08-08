# Cloud SQL: Postgres instance for the transactional layer
resource "google_sql_database_instance" "postgres" {
  name             = "edikte-analytics-db"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier = var.db_instance_tier

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "edikte_db" {
  name     = "edikte_analytics"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "app_user" {
  name     = "edikte_app"
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}

# Cloud Storage: raw HTML/PDF retention
resource "google_storage_bucket" "raw_documents" {
  name                        = "edikte-analytics-raw-docs"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
}

# BigQuery: analytical layer, fed by dbt from Postgres
resource "google_bigquery_dataset" "analytics" {
  dataset_id = "edikte_analytics"
  location   = var.region
}