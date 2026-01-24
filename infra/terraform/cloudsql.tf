resource "google_sql_database_instance" "crm" {
  name             = "crm-db"
  database_version = var.database_version
  region           = var.region

  settings {
    tier = var.database_tier
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.crm.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }
    backup_configuration {
      enabled                        = true
      start_time                     = var.backup_start_time
      point_in_time_recovery_enabled = var.enable_pitr
    }
  }

  deletion_protection = var.database_deletion_protection

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

resource "google_sql_database" "crm" {
  name     = var.database_name
  instance = google_sql_database_instance.crm.name
}

resource "google_sql_user" "crm" {
  count    = var.manage_database_user ? 1 : 0
  name     = var.database_user
  instance = google_sql_database_instance.crm.name
  password = var.database_password
}
