resource "google_monitoring_alert_policy" "cloudsql_cpu_high" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "Cloud SQL CPU high"
  combiner              = "OR"
  notification_channels = var.alert_notification_channel_ids

  conditions {
    display_name = "Cloud SQL CPU > 70% for 15m"
    condition_threshold {
      filter          = "resource.type=\"cloudsql_database\" metric.type=\"cloudsql.googleapis.com/database/cpu/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.7
      duration        = "900s"
      trigger {
        count = 1
      }
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
}

resource "google_monitoring_alert_policy" "cloudsql_memory_high" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "Cloud SQL memory high"
  combiner              = "OR"
  notification_channels = var.alert_notification_channel_ids

  conditions {
    display_name = "Cloud SQL memory > 80% for 15m"
    condition_threshold {
      filter          = "resource.type=\"cloudsql_database\" metric.type=\"cloudsql.googleapis.com/database/memory/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "900s"
      trigger {
        count = 1
      }
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
}

resource "google_monitoring_alert_policy" "cloudsql_disk_high" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "Cloud SQL disk high"
  combiner              = "OR"
  notification_channels = var.alert_notification_channel_ids

  conditions {
    display_name = "Cloud SQL disk > 80% for 15m"
    condition_threshold {
      filter          = "resource.type=\"cloudsql_database\" metric.type=\"cloudsql.googleapis.com/database/disk/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "900s"
      trigger {
        count = 1
      }
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
}

resource "google_monitoring_alert_policy" "redis_memory_high" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "Redis memory high"
  combiner              = "OR"
  notification_channels = var.alert_notification_channel_ids

  conditions {
    display_name = "Redis memory usage > 80% for 15m"
    condition_threshold {
      filter          = "resource.type=\"redis_instance\" metric.type=\"redis.googleapis.com/stats/memory/usage_ratio\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "900s"
      trigger {
        count = 1
      }
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
}

resource "google_monitoring_alert_policy" "cloud_run_5xx" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "Cloud Run 5xx spike"
  combiner              = "OR"
  notification_channels = var.alert_notification_channel_ids

  conditions {
    display_name = "Cloud Run 5xx > 5 in 5m"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" metric.type=\"run.googleapis.com/request_count\" metric.label.\"response_code_class\"=\"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "300s"
      trigger {
        count = 1
      }
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
}
