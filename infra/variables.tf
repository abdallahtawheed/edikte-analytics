variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "edikte-analytics-2026"
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "europe-west3"
}

variable "db_instance_tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-f1-micro"
}

variable "db_password" {
  description = "Password for the Postgres app user"
  type        = string
  sensitive   = true
}