resource "google_dataplex_lake" "analytics_lake" {
  display_name     = "Edikte Analytics"
  name     = "edikte-analytics-lake"
  location = "europe-west3"
}

resource "google_dataplex_zone" "raw_zone" {
  display_name     = "Raw"
  name     = "raw-zone"
  lake     = google_dataplex_lake.analytics_lake.name
  location = "europe-west3"
  type     = "RAW"
  resource_spec {
    location_type = "SINGLE_REGION"
  }
  discovery_spec {
    enabled = false
  }
}

resource "google_dataplex_zone" "curated_zone" {
  display_name     = "Curated (dbt marts)"
  name     = "curated-zone"
  lake     = google_dataplex_lake.analytics_lake.name
  location = "europe-west3"
  type     = "CURATED"
  resource_spec {
    location_type = "SINGLE_REGION"
  }
  discovery_spec {
    enabled = false
  }
}

resource "google_dataplex_asset" "raw_bigquery_asset" {
  display_name     = "Raw synced tables"
  name          = "raw-bigquery-asset"
  location      = "europe-west3"
  lake          = google_dataplex_lake.analytics_lake.name
  dataplex_zone = google_dataplex_zone.raw_zone.name
  resource_spec {
    type = "BIGQUERY_DATASET"
    name = "projects/edikte-analytics-2026/datasets/edikte_analytics"
  }
  discovery_spec {
    enabled = true
  }
}

resource "google_dataplex_asset" "marts_bigquery_asset" {
  display_name     = "dbt staging and marts"
  name          = "marts-bigquery-asset"
  location      = "europe-west3"
  lake          = google_dataplex_lake.analytics_lake.name
  dataplex_zone = google_dataplex_zone.curated_zone.name
  resource_spec {
    type = "BIGQUERY_DATASET"
    name = "projects/edikte-analytics-2026/datasets/edikte_analytics_dbt"
  }
  discovery_spec {
    enabled = true
  }
}