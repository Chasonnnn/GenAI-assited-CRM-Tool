resource "google_sql_database_instance" "crm" {
  name             = "crm-db"
  database_version = var.database_version
  region           = var.region

  settings {
    tier = var.database_tier
    ip_configuration {
      ipv4_enabled = true
    }
    backup_configuration {
      enabled                        = true
      start_time                     = var.backup_start_time
      point_in_time_recovery_enabled = var.enable_pitr
    }
  }

  deletion_protection = true
}

resource "google_sql_database" "crm" {
  name     = var.database_name
  instance = google_sql_database_instance.crm.name
}

resource "google_sql_user" "crm" {
  name     = var.database_user
  instance = google_sql_database_instance.crm.name
  password = var.database_password
}
