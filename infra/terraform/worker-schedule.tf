resource "google_project_iam_custom_role" "worker_scaler" {
  count       = var.worker_schedule_enabled ? 1 : 0
  project     = var.project_id
  role_id     = "crmWorkerScaler"
  title       = "CRM Worker Scaler"
  description = "Allows Cloud Scheduler to update crm-worker min instances."
  permissions = [
    "run.services.get",
    "run.services.update",
  ]
}

resource "google_project_iam_member" "worker_scaler_run_update" {
  count   = var.worker_schedule_enabled ? 1 : 0
  project = var.project_id
  role    = google_project_iam_custom_role.worker_scaler[0].id
  member  = "serviceAccount:${google_service_account.worker_scaler[0].email}"
}

resource "google_service_account_iam_member" "worker_scaler_sa_user_worker" {
  count              = var.worker_schedule_enabled ? 1 : 0
  service_account_id = google_service_account.worker.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.worker_scaler[0].email}"
}

resource "google_service_account_iam_member" "worker_scaler_scheduler_impersonate" {
  count              = var.worker_schedule_enabled ? 1 : 0
  service_account_id = google_service_account.worker_scaler[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
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
      service_account_email = google_service_account.worker_scaler[0].email
    }
  }

  depends_on = [
    google_project_iam_member.worker_scaler_run_update,
    google_service_account_iam_member.worker_scaler_sa_user_worker,
    google_service_account_iam_member.worker_scaler_scheduler_impersonate,
  ]
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
      service_account_email = google_service_account.worker_scaler[0].email
    }
  }

  depends_on = [
    google_project_iam_member.worker_scaler_run_update,
    google_service_account_iam_member.worker_scaler_sa_user_worker,
    google_service_account_iam_member.worker_scaler_scheduler_impersonate,
  ]
}
