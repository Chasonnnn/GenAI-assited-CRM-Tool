resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(local.all_secret_keys)
  project   = var.project_id
  secret_id = each.value

  replication {
    user_managed {
      replicas {
        location = var.secret_replication_location
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}