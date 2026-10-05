locals {
  required_services = toset(concat([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "logging.googleapis.com",
    "clouderrorreporting.googleapis.com",
    "monitoring.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "vpcaccess.googleapis.com",
    "redis.googleapis.com",
    "bigquery.googleapis.com",
    "cloudscheduler.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "certificatemanager.googleapis.com",
    ],
    var.private_tracing_enabled ? ["cloudtrace.googleapis.com", "telemetry.googleapis.com"] : [],
    var.gmail_push_enabled ? ["pubsub.googleapis.com"] : [],
  ))
}

resource "google_project_service" "required" {
  for_each = local.required_services
  project  = var.project_id
  service  = each.value

  disable_on_destroy = false
}
