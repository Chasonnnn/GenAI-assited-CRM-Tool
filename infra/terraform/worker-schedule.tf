resource "google_project_iam_member" "worker_run_admin" {
  count   = var.worker_schedule_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_cloud_scheduler_job" "worker_scale_up" {
  count     = var.worker_schedule_enabled ? 1 : 0
  name      = "${var.worker_job_name}-scale-up"
  region    = var.region
  schedule  = var.worker_scale_up_cron
  time_zone = var.worker_schedule_timezone

  http_target {
    http_method = "PATCH"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/services/${google_cloud_run_v2_service.worker.name}?updateMask=template.scaling.minInstanceCount"
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode(jsonencode({
      template = {
        scaling = {
          minInstanceCount = var.worker_min_instances_day
        }
      }
    }))
    oauth_token {
      service_account_email = google_service_account.worker.email
    }
  }
}

resource "google_cloud_scheduler_job" "worker_scale_down" {
  count     = var.worker_schedule_enabled ? 1 : 0
  name      = "${var.worker_job_name}-scale-down"
  region    = var.region
  schedule  = var.worker_scale_down_cron
  time_zone = var.worker_schedule_timezone

  http_target {
    http_method = "PATCH"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/services/${google_cloud_run_v2_service.worker.name}?updateMask=template.scaling.minInstanceCount"
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode(jsonencode({
      template = {
        scaling = {
          minInstanceCount = var.worker_min_instances_night
        }
      }
    }))
    oauth_token {
      service_account_email = google_service_account.worker.email
    }
  }
}
