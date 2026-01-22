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
