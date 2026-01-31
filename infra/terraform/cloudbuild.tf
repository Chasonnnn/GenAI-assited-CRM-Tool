resource "google_cloudbuild_trigger" "api" {
  provider    = google-beta
  count       = var.enable_cloudbuild_triggers ? 1 : 0
  name        = "crm-api-deploy"
  description = "Build and deploy API + worker on main"
  filename    = "cloudbuild/api.yaml"
  location    = var.cloudbuild_location
  # Cloud Build expects a fully-qualified service account resource name.
  service_account = google_service_account.cloudbuild.name

  repository_event_config {
    repository = var.cloudbuild_repository
    push {
      # Deploy only on version tags (e.g. v0.24.0), not on every main commit.
      tag = var.github_tag_regex
    }
  }

  substitutions = {
    _REGION            = var.region
    _API_SERVICE       = var.api_service_name
    _WORKER_SERVICE    = var.worker_job_name
    _IMAGE_API         = local.api_image
    _IMAGE_WORKER      = local.worker_image
    _CLAMAV_UPDATE_JOB = var.clamav_update_job_name
  }

}

resource "google_cloudbuild_trigger" "web" {
  provider    = google-beta
  count       = var.enable_cloudbuild_triggers ? 1 : 0
  name        = "crm-web-deploy"
  description = "Build and deploy web on main"
  filename    = "cloudbuild/web.yaml"
  location    = var.cloudbuild_location
  # Cloud Build expects a fully-qualified service account resource name.
  service_account = google_service_account.cloudbuild.name

  repository_event_config {
    repository = var.cloudbuild_repository
    push {
      # Deploy only on version tags (e.g. v0.24.0), not on every main commit.
      tag = var.github_tag_regex
    }
  }

  substitutions = {
    _REGION       = var.region
    _WEB_SERVICE  = var.web_service_name
    _IMAGE_WEB    = local.web_image
    _API_BASE_URL = local.api_url
  }

}
