resource "google_secret_manager_secret" "secrets" {
  for_each  = local.secret_values
  secret_id = each.key

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "secrets" {
  for_each    = local.secret_values
  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value
}
