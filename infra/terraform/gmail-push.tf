variable "gmail_push_enabled" {
  description = "Enable authenticated Gmail notifications; polling remains the recovery path."
  type        = bool
  default     = false
}

locals {
  gmail_push_endpoint = "${local.api_url}/webhooks/google-gmail"
}

resource "google_pubsub_topic" "gmail" {
  count      = var.gmail_push_enabled ? 1 : 0
  name       = "crm-gmail-push"
  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic_iam_member" "gmail_publisher" {
  count  = var.gmail_push_enabled ? 1 : 0
  topic  = google_pubsub_topic.gmail[0].name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:gmail-api-push@system.gserviceaccount.com"
}

resource "google_service_account" "gmail_push" {
  count        = var.gmail_push_enabled ? 1 : 0
  account_id   = "crm-gmail-push"
  display_name = "Gmail Pub/Sub push identity"
}

resource "google_project_service_identity" "pubsub" {
  provider   = google-beta
  count      = var.gmail_push_enabled ? 1 : 0
  project    = var.project_id
  service    = "pubsub.googleapis.com"
  depends_on = [google_project_service.required]
}

resource "google_service_account_iam_member" "pubsub_push_token" {
  count              = var.gmail_push_enabled ? 1 : 0
  service_account_id = google_service_account.gmail_push[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_project_service_identity.pubsub[0].email}"
}

resource "google_pubsub_subscription" "gmail" {
  count                      = var.gmail_push_enabled ? 1 : 0
  name                       = "crm-gmail-push"
  topic                      = google_pubsub_topic.gmail[0].id
  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"
  expiration_policy {
    ttl = ""
  }
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
  push_config {
    push_endpoint = local.gmail_push_endpoint
    oidc_token {
      service_account_email = google_service_account.gmail_push[0].email
      audience              = local.gmail_push_endpoint
    }
  }
  depends_on = [google_service_account_iam_member.pubsub_push_token]
}

resource "google_monitoring_alert_policy" "gmail_push_backlog" {
  count                 = var.gmail_push_enabled && local.alerting_enabled ? 1 : 0
  display_name          = "Gmail push delivery delayed"
  combiner              = "OR"
  notification_channels = local.alert_notification_channels
  conditions {
    display_name = "Gmail notification unacknowledged for over 5 minutes"
    condition_threshold {
      filter          = "resource.type=\"pubsub_subscription\" AND resource.label.subscription_id=\"${google_pubsub_subscription.gmail[0].name}\" AND metric.type=\"pubsub.googleapis.com/subscription/oldest_unacked_message_age\""
      comparison      = "COMPARISON_GT"
      threshold_value = 300
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
      trigger {
        count = 1
      }
    }
  }
}
