# Grant Secret Manager access at the SECRET level (not project level).
# This avoids org/project IAM conditional-binding issues and ensures new secrets
# are immediately accessible to Cloud Run service accounts.

resource "google_secret_manager_secret_iam_member" "api_secret_access" {
  for_each = toset(local.all_secret_keys)

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "worker_secret_access" {
  for_each = toset(local.all_secret_keys)

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}
