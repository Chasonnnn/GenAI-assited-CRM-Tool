# Grant Secret Manager access at the SECRET level (not project level).
# This avoids org/project IAM conditional-binding issues and ensures new secrets
# are immediately accessible to Cloud Run service accounts.

resource "google_secret_manager_secret_iam_member" "api_secret_access" {
  for_each = toset(local.all_secret_keys)

  project = var.project_id
  # Force a dependency on the secret resource so we don't try to set IAM before
  # the secret exists (common when adding a new secret key).
  secret_id = google_secret_manager_secret.secrets[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "worker_secret_access" {
  for_each = toset(local.all_secret_keys)

  project = var.project_id
  # See note above about dependency ordering.
  secret_id = google_secret_manager_secret.secrets[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}
