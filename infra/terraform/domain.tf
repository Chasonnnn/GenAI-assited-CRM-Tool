resource "google_cloud_run_domain_mapping" "api" {
  count    = var.enable_domain_mapping ? 1 : 0
  location = var.region
  name     = "api.${var.domain}"

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_service.api.name
  }
}

resource "google_cloud_run_domain_mapping" "web" {
  count    = var.enable_domain_mapping ? 1 : 0
  location = var.region
  name     = "app.${var.domain}"

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_service.web.name
  }
}
