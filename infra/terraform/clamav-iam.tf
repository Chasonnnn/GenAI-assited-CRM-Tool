resource "google_project_iam_member" "worker_run_invoker" {
  count   = var.clamav_update_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "api_run_invoker" {
  count   = var.attachment_scan_job_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_run_developer" {
  count   = var.attachment_scan_job_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# The worker claims scheduled scan jobs and starts the scan job with per-scan argument
# overrides, so it needs execute-with-overrides on that job only.
resource "google_cloud_run_v2_job_iam_member" "worker_attachment_scan_executor" {
  count    = var.attachment_scan_job_enabled ? 1 : 0
  project  = var.project_id
  location = google_cloud_run_v2_job.attachment_scan[0].location
  name     = google_cloud_run_v2_job.attachment_scan[0].name
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_service_account_iam_member" "worker_scheduler_impersonate" {
  count              = var.clamav_update_enabled ? 1 : 0
  service_account_id = google_service_account.worker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
}
