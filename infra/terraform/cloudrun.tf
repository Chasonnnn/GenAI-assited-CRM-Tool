resource "google_cloud_run_service" "api" {
  name     = var.api_service_name
  location = var.region

  metadata {
    annotations = {
      "run.googleapis.com/ingress"             = "all"
    }
  }

  template {
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale"       = tostring(var.run_min_instances)
        "autoscaling.knative.dev/maxScale"       = tostring(var.run_max_instances)
        "run.googleapis.com/cloudsql-instances"  = google_sql_database_instance.crm.connection_name
        "run.googleapis.com/vpc-access-connector" = google_vpc_access_connector.crm.id
        "run.googleapis.com/vpc-access-egress"     = "all-traffic"
      }
    }

    spec {
      service_account_name = google_service_account.api.email

      containers {
        image = local.api_image

        resources {
          limits = {
            cpu    = var.run_cpu
            memory = var.run_memory
          }
        }

        ports {
          container_port = 8000
        }

        dynamic "env" {
          for_each = local.common_env
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = toset(local.common_secret_keys)
          content {
            name = env.value
            value_from {
              secret_key_ref {
                name = google_secret_manager_secret.secrets[env.value].secret_id
                key  = "latest"
              }
            }
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  lifecycle {
    ignore_changes = [
      template[0].spec[0].containers[0].image
    ]
  }
}

resource "google_cloud_run_service" "web" {
  name     = var.web_service_name
  location = var.region

  metadata {
    annotations = {
      "run.googleapis.com/ingress"        = "all"
    }
  }

  template {
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = tostring(var.run_min_instances)
        "autoscaling.knative.dev/maxScale" = tostring(var.run_max_instances)
      }
    }

    spec {
      service_account_name = google_service_account.web.email

      containers {
        image = local.web_image

        resources {
          limits = {
            cpu    = var.run_cpu
            memory = var.run_memory
          }
        }

        ports {
          container_port = 3000
        }

        env {
          name  = "NEXT_PUBLIC_API_BASE_URL"
          value = local.api_url
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  lifecycle {
    ignore_changes = [
      template[0].spec[0].containers[0].image
    ]
  }
}

resource "google_cloud_run_service_iam_member" "api_invoker" {
  service  = google_cloud_run_service.api.name
  location = google_cloud_run_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "web_invoker" {
  service  = google_cloud_run_service.web.name
  location = google_cloud_run_service.web.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job" "worker" {
  provider = google-beta
  name     = var.worker_job_name
  location = var.region

  template {
    template {
      service_account = google_service_account.worker.email

      containers {
        image   = local.api_image
        command = ["python", "-m", "app.worker"]

        dynamic "env" {
          for_each = local.common_env
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = toset(local.common_secret_keys)
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
        egress    = "ALL_TRAFFIC"
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image
    ]
  }
}

resource "google_cloud_run_v2_job" "migrate" {
  provider = google-beta
  name     = var.migrate_job_name
  location = var.region

  template {
    template {
      service_account = google_service_account.worker.email

      containers {
        image   = local.api_image
        command = ["alembic", "upgrade", "head"]

        dynamic "env" {
          for_each = local.common_env
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = toset(local.common_secret_keys)
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
        egress    = "ALL_TRAFFIC"
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image
    ]
  }
}
