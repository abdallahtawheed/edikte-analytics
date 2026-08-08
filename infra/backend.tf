terraform {
  backend "gcs" {
    bucket = "edikte-analytics-tfstate-2026"
    prefix = "terraform/state"
  }
}