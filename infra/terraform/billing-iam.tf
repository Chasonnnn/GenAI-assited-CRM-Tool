resource "google_project_iam_member" "billing_report_bigquery_job" {
  count   = var.billing_weekly_summary_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.billing_report.email}"
}

resource "google_bigquery_dataset_iam_member" "billing_report_viewer" {
  count      = var.billing_weekly_summary_enabled ? 1 : 0
  project    = var.project_id
  dataset_id = google_bigquery_dataset.billing_export[0].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.billing_report.email}"
}

resource "google_secret_manager_secret_iam_member" "billing_report_slack_secret" {
  count     = var.billing_weekly_summary_enabled ? 1 : 0
  project   = var.project_id
  secret_id = google_secret_manager_secret.secrets["BILLING_SLACK_WEBHOOK_URL"].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.billing_report.email}"
}

resource "google_project_iam_member" "billing_report_run_invoker" {
  count   = var.billing_weekly_summary_enabled ? 1 : 0
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.billing_report.email}"
}

resource "google_service_account_iam_member" "billing_report_scheduler_impersonate" {
  count              = var.billing_weekly_summary_enabled ? 1 : 0
  service_account_id = google_service_account.billing_report.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
}
