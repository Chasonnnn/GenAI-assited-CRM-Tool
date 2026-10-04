variable "private_tracing_enabled" {
  description = "Export sanitized API spans through a local collector to Cloud Trace."
  type        = bool
  default     = false
}

variable "private_tracing_sample_rate" {
  type    = number
  default = 0.1
  validation {
    condition     = var.private_tracing_sample_rate >= 0 && var.private_tracing_sample_rate <= 1
    error_message = "Tracing sample rate must be between zero and one."
  }
}

resource "google_project_iam_member" "api_trace_writer" {
  count   = var.private_tracing_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_telemetry_consumer" {
  count   = var.private_tracing_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.api.email}"
}
