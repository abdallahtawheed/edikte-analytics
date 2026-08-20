# infra/modules/service_account/main.tf
variable "account_id" { type = string }
variable "display_name" { type = string }
variable "project_id" { type = string }
variable "roles" { type = list(string) }

resource "google_service_account" "this" {
  account_id   = var.account_id
  display_name = var.display_name
}

resource "google_project_iam_member" "bindings" {
  for_each = toset(var.roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.this.email}"
}

output "email" {
  value = google_service_account.this.email
}