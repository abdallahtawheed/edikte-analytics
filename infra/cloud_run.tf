resource "google_cloud_run_v2_service" "dashboard" {
  name     = "edikte-analytics-dashboard"
  location = "europe-west3"
    lifecycle {
    ignore_changes = [client, client_version]
    }
  template {
    containers {
      image = "gcr.io/edikte-analytics-2026/streamlit-app"
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = "db-password"
            version = "latest"
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "pipeline" {
  name     = "pipeline-job"
  location = "europe-west3"
  lifecycle {
    ignore_changes = [client, client_version]
    }
  template {
    template {
      max_retries = 1
      containers {
        image   = "gcr.io/edikte-analytics-2026/pipeline-jobs"
        command = ["uv"]
        args    = ["run", "python", "run_pipeline.py"]
        env {
          name = "DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = "db-password"
              version = "latest"
            }
          }
        }
      }
    }
  }
}