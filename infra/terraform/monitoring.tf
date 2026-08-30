resource "google_monitoring_notification_channel" "ops_webhook" {
  count = local.monitoring_webhook_enabled ? 1 : 0

  display_name = "Ops internal alerts webhook"
  type         = "webhook_tokenauth"

  labels = {
    url   = local.monitoring_webhook_url
    token = var.monitoring_webhook_token
  }
}

resource "google_monitoring_alert_policy" "cloudsql_cpu_high" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "Cloud SQL CPU high"
  combiner              = "OR"
  notification_channels = local.alert_notification_channels

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
  notification_channels = local.alert_notification_channels

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
  notification_channels = local.alert_notification_channels

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
  notification_channels = local.alert_notification_channels

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
  notification_channels = local.alert_notification_channels

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

resource "google_logging_metric" "ticketing_outbound_failures" {
  name   = "ticketing_outbound_failures"
  filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.worker_job_name}\" (textPayload=~\"type=ticket_outbound_send.*final=true\" OR jsonPayload.message=~\"type=ticket_outbound_send.*final=true\") severity>=ERROR"

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "Ticketing outbound send failures"
  }
}

resource "google_logging_metric" "mailbox_ingestion_failures" {
  name   = "mailbox_ingestion_failures"
  filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.worker_job_name}\" (textPayload=~\"type=(mailbox_backfill|mailbox_history_sync|mailbox_watch_refresh|email_occurrence_fetch_raw|email_occurrence_parse|email_occurrence_stitch|ticket_apply_linking).*final=true\" OR jsonPayload.message=~\"type=(mailbox_backfill|mailbox_history_sync|mailbox_watch_refresh|email_occurrence_fetch_raw|email_occurrence_parse|email_occurrence_stitch|ticket_apply_linking).*final=true\") severity>=ERROR"

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "Mailbox ingestion failures"
  }
}

resource "google_logging_metric" "websocket_publish_failures" {
  name   = "websocket_publish_failures"
  filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.api_service_name}\" jsonPayload.event=\"ws_event_publish_failed\""

  label_extractors = {
    event        = "EXTRACT(jsonPayload.event)"
    org_id       = "EXTRACT(jsonPayload.org_id)"
    user_id      = "EXTRACT(jsonPayload.user_id)"
    message_type = "EXTRACT(jsonPayload.message_type)"
  }

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "WebSocket backplane publish failures"

    labels {
      key        = "event"
      value_type = "STRING"
    }
    labels {
      key        = "org_id"
      value_type = "STRING"
    }
    labels {
      key        = "user_id"
      value_type = "STRING"
    }
    labels {
      key        = "message_type"
      value_type = "STRING"
    }
  }
}

resource "google_logging_metric" "api_memory_limit_exceeded" {
  name   = "api_memory_limit_exceeded"
  filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.api_service_name}\" textPayload:\"Memory limit of\" textPayload:\"exceeded with\""

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "API Cloud Run memory limit exceeded"
  }
}

resource "google_monitoring_alert_policy" "ticketing_outbound_failures" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "Ticketing outbound dead-letter failures"
  combiner              = "OR"
  notification_channels = local.alert_notification_channels

  conditions {
    display_name = "Ticketing outbound dead-letter failures > 0 in 5m"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.ticketing_outbound_failures.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
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

resource "google_monitoring_alert_policy" "mailbox_ingestion_failures" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "Mailbox ingestion dead-letter failures"
  combiner              = "OR"
  notification_channels = local.alert_notification_channels

  conditions {
    display_name = "Mailbox ingestion dead-letter failures > 0 in 5m"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.mailbox_ingestion_failures.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
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

resource "google_monitoring_alert_policy" "websocket_publish_failures" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "WebSocket backplane publish failures"
  combiner              = "OR"
  notification_channels = local.alert_notification_channels

  conditions {
    display_name = "WebSocket backplane publish failures > 0 in 5m"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.websocket_publish_failures.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
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

resource "google_monitoring_alert_policy" "api_memory_limit_exceeded" {
  count = local.alerting_enabled ? 1 : 0

  display_name          = "API Cloud Run memory limit exceeded"
  combiner              = "OR"
  notification_channels = local.alert_notification_channels

  conditions {
    display_name = "API memory limit exceeded > 0 in 5m"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.api_memory_limit_exceeded.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
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
