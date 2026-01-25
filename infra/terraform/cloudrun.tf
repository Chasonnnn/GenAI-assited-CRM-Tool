resource "google_cloud_run_v2_service" "api" {
  name     = var.api_service_name
  location = var.run_region
  ingress  = "INGRESS_TRAFFIC_ALL"

  # Ensure the revision service account has Secret Manager access before we
  # deploy a revision that references Secret Manager env vars.
  depends_on = [google_secret_manager_secret_iam_member.api_secret_access]

  template {
    annotations = {
      "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.crm.connection_name
    }

    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.run_min_instances
      max_instance_count = var.run_max_instances
    }

    vpc_access {
      connector = google_vpc_access_connector.crm.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = local.api_image

      resources {
        limits = {
          cpu    = var.run_cpu
          memory = var.run_memory
        }
        cpu_idle = var.run_cpu_idle
      }

      ports {
        container_port = 8000
      }

      startup_probe {
        # Cloud Run startup probes are strict by default (short timeouts / low
        # retries). Give the container a few minutes to finish cold start and
        # bind the port.
        failure_threshold = 18
        period_seconds    = 10
        timeout_seconds   = 5
        http_get {
          # Keep startup checks lightweight; /health/ready depends on DB/Redis and
          # can flap during VPC connector / dependency warm-up.
          path = "/health/live"
          port = 8000
        }
      }

      liveness_probe {
        http_get {
          path = "/health/live"
          port = 8000
        }
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
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image
    ]
  }
}

resource "google_cloud_run_v2_service" "web" {
  name     = var.web_service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.web.email

    scaling {
      min_instance_count = var.run_min_instances
      max_instance_count = var.run_max_instances
    }

    containers {
      image = local.web_image

      resources {
        limits = {
          cpu    = var.run_cpu
          memory = var.run_memory
        }
        cpu_idle = var.run_cpu_idle
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

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "api_invoker" {
  count    = var.enable_public_invoker ? 1 : 0
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "web_invoker" {
  count    = var.enable_public_invoker ? 1 : 0
  name     = google_cloud_run_v2_service.web.name
  location = google_cloud_run_v2_service.web.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job" "worker" {
  provider = google-beta
  name     = var.worker_job_name
  location = var.region

  # Ensure the job service account has Secret Manager access before we update
  # the job template to reference Secret Manager env vars.
  depends_on = [google_secret_manager_secret_iam_member.worker_secret_access]

  template {
    template {
      service_account = google_service_account.worker.email

      containers {
        image   = local.api_image
        command = ["python", "-m", "app.worker"]
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

resource "google_cloud_run_v2_job" "migrate" {
  provider = google-beta
  name     = var.migrate_job_name
  location = var.region

  # See note in google_cloud_run_v2_job.worker.
  depends_on = [google_secret_manager_secret_iam_member.worker_secret_access]

  template {
    template {
      service_account = google_service_account.worker.email

      containers {
        image   = local.api_image
        command = ["alembic", "upgrade", "head"]
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
