resource "google_cloud_run_v2_job" "clamav_update" {
  count    = var.clamav_update_enabled ? 1 : 0
  provider = google-beta
  name     = var.clamav_update_job_name
  location = var.region

  depends_on = [google_secret_manager_secret_iam_member.worker_secret_access]

  template {
    template {
      service_account = google_service_account.worker.email

      containers {
        image   = local.worker_image
        command = ["python", "-m", "app.clamav_update"]
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }

        dynamic "env" {
          for_each = local.common_env
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = { for key in sort(local.common_secret_keys) : key => key }
          content {
            name = env.value
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.secrets[env.value].secret_id
                version = "latest"
              }
            }
          }
        }
      }

      vpc_access {
        connector = google_vpc_access_connector.crm.id
        egress    = "PRIVATE_RANGES_ONLY"
      }

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.crm.connection_name]
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image
    ]
  }
}

resource "google_cloud_scheduler_job" "clamav_update" {
  count     = var.clamav_update_enabled ? 1 : 0
  name      = "${var.clamav_update_job_name}-schedule"
  region    = var.region
  schedule  = var.clamav_update_cron
  time_zone = var.clamav_update_timezone

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.clamav_update[0].name}:run"
    oauth_token {
      service_account_email = google_service_account.worker.email
    }
  }
}
