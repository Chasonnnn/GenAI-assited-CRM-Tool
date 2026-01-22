resource "google_cloudbuild_trigger" "api" {
  count       = var.enable_cloudbuild_triggers ? 1 : 0
  name        = "crm-api-deploy"
  description = "Build and deploy API + worker on main"
  filename    = "cloudbuild/api.yaml"
  location    = var.cloudbuild_location

  repository_event_config {
    repository = var.cloudbuild_repository
    push {
      branch = var.github_branch
    }
  }

  substitutions = {
    _REGION      = var.region
    _API_SERVICE = var.api_service_name
    _WORKER_JOB  = var.worker_job_name
    _IMAGE_API   = local.api_image
  }

}

resource "google_cloudbuild_trigger" "web" {
  count       = var.enable_cloudbuild_triggers ? 1 : 0
  name        = "crm-web-deploy"
  description = "Build and deploy web on main"
  filename    = "cloudbuild/web.yaml"
  location    = var.region

  repository_event_config {
    repository = var.cloudbuild_repository
    push {
      branch = var.github_branch
    }
  }

  substitutions = {
    _REGION       = var.region
    _WEB_SERVICE  = var.web_service_name
    _IMAGE_WEB    = local.web_image
    _API_BASE_URL = local.api_url
  }

}
