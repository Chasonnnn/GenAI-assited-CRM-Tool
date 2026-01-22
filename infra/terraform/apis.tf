locals {
  required_services = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "logging.googleapis.com",
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
  ])
}

resource "google_project_service" "required" {
  for_each = local.required_services
  project  = var.project_id
  service  = each.value

  disable_on_destroy = false
}
