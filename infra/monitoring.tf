resource "google_monitoring_notification_channel" "email" {
  type         = "email"
  display_name = "Pipeline failure alerts"
  labels = {
    email_address = "boudy1131@gmail.com"
  }
}

resource "google_monitoring_uptime_check_config" "dashboard_uptime" {
  display_name = "edikte-dashboard-uptime"
  timeout      = "60s"
  http_check {
    path    = "/"
    port    = 80
    use_ssl = false
  }
  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = "edikte-analytics-2026"
      host       = "edikte-analytics-dashboard-523082904080.europe-west3.run.app"
    }
  }
}

resource "google_monitoring_alert_policy" "pipeline_failure" {
  display_name = "Pipeline job failure"
  combiner      = "OR"
  conditions {
    display_name = "Cloud Run Job execution failed"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"pipeline-job\" AND metric.type=\"run.googleapis.com/job/completed_execution_count\" AND metric.labels.result=\"failed\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_COUNT"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.name]
}

resource "google_monitoring_alert_policy" "dashboard_uptime_failure" {
  display_name = "Dashboard uptime failure"
  combiner      = "OR"
  conditions {
    display_name = "Uptime check failed"
    condition_threshold {
      filter          = "resource.type=\"uptime_url\" AND metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.labels.check_id=\"edikte-dashboard-uptime-KvijgIcHfZg\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "300s"
      aggregations {
        alignment_period      = "300s"
        per_series_aligner    = "ALIGN_FRACTION_TRUE"
        cross_series_reducer  = "REDUCE_MEAN"
      }
      trigger {
        count = 1
      }
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.name]
}