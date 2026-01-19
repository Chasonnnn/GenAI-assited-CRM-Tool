resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(local.common_secret_keys)
  secret_id = each.value

  replication {
    user_managed {
      replicas {
        location = var.secret_replication_location
      }
    }
  }
}

resource "google_secret_manager_secret_version" "secrets" {
  for_each    = toset(local.common_secret_keys)
  secret      = google_secret_manager_secret.secrets[each.value].id
  secret_data = local.secret_values[each.value]
}
