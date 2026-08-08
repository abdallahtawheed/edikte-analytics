output "sql_instance_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "storage_bucket_url" {
  value = google_storage_bucket.raw_documents.url
}

output "bigquery_dataset_id" {
  value = google_bigquery_dataset.analytics.dataset_id
}