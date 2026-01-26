resource "google_compute_global_address" "lb_ip" {
  count = var.enable_load_balancer ? 1 : 0
  name  = "crm-lb-ip"
}

resource "google_compute_region_network_endpoint_group" "web_neg" {
  count                 = var.enable_load_balancer ? 1 : 0
  name                  = "crm-web-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.web.name
  }
}

resource "google_compute_region_network_endpoint_group" "api_neg" {
  count                 = var.enable_load_balancer ? 1 : 0
  name                  = "crm-api-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.api.name
  }
}

resource "google_compute_backend_service" "web_backend" {
  count                 = var.enable_load_balancer ? 1 : 0
  name                  = "crm-web-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30

  backend {
    group = google_compute_region_network_endpoint_group.web_neg[0].id
  }
}

resource "google_compute_backend_service" "api_backend" {
  count                 = var.enable_load_balancer ? 1 : 0
  name                  = "crm-api-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30

  backend {
    group = google_compute_region_network_endpoint_group.api_neg[0].id
  }
}

resource "google_compute_url_map" "crm" {
  count           = var.enable_load_balancer ? 1 : 0
  name            = "crm-url-map"
  default_service = google_compute_backend_service.web_backend[0].id

  host_rule {
    hosts        = ["api.${var.domain}"]
    path_matcher = "api"
  }

  host_rule {
    hosts = [
      var.domain,
      "app.${var.domain}",
      "ops.${var.domain}",
      "*.${var.domain}",
    ]
    path_matcher = "web"
  }

  path_matcher {
    name            = "api"
    default_service = google_compute_backend_service.api_backend[0].id
  }

  path_matcher {
    name            = "web"
    default_service = google_compute_backend_service.web_backend[0].id
  }
}

resource "google_certificate_manager_dns_authorization" "root" {
  provider = google-beta
  count    = var.enable_load_balancer ? 1 : 0
  name     = "crm-root-dns-auth"
  domain   = var.domain
  location = "global"
}

resource "google_certificate_manager_certificate" "wildcard" {
  provider = google-beta
  count    = var.enable_load_balancer ? 1 : 0
  name     = "crm-wildcard-cert"
  location = "global"

  managed {
    domains = [
      var.domain,
      "*.${var.domain}",
    ]
    dns_authorizations = [
      google_certificate_manager_dns_authorization.root[0].id,
    ]
  }
}

resource "google_certificate_manager_certificate_map" "crm" {
  provider = google-beta
  count    = var.enable_load_balancer ? 1 : 0
  name     = "crm-cert-map"
}

resource "google_certificate_manager_certificate_map_entry" "root" {
  provider     = google-beta
  count        = var.enable_load_balancer ? 1 : 0
  name         = "crm-cert-root"
  map          = google_certificate_manager_certificate_map.crm[0].name
  hostname     = var.domain
  certificates = [google_certificate_manager_certificate.wildcard[0].id]
}

resource "google_certificate_manager_certificate_map_entry" "wildcard" {
  provider     = google-beta
  count        = var.enable_load_balancer ? 1 : 0
  name         = "crm-cert-wildcard"
  map          = google_certificate_manager_certificate_map.crm[0].name
  hostname     = "*.${var.domain}"
  certificates = [google_certificate_manager_certificate.wildcard[0].id]
}

resource "google_compute_target_https_proxy" "crm" {
  provider        = google-beta
  count           = var.enable_load_balancer ? 1 : 0
  name            = "crm-https-proxy"
  url_map         = google_compute_url_map.crm[0].id
  certificate_map = "//certificatemanager.googleapis.com/${google_certificate_manager_certificate_map.crm[0].id}"
}

resource "google_compute_url_map" "http_redirect" {
  count = var.enable_load_balancer ? 1 : 0
  name  = "crm-http-redirect"

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_target_http_proxy" "http" {
  count   = var.enable_load_balancer ? 1 : 0
  name    = "crm-http-proxy"
  url_map = google_compute_url_map.http_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "https" {
  count                 = var.enable_load_balancer ? 1 : 0
  name                  = "crm-https-forwarding"
  target                = google_compute_target_https_proxy.crm[0].id
  port_range            = "443"
  ip_address            = google_compute_global_address.lb_ip[0].address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_global_forwarding_rule" "http" {
  count                 = var.enable_load_balancer ? 1 : 0
  name                  = "crm-http-forwarding"
  target                = google_compute_target_http_proxy.http[0].id
  port_range            = "80"
  ip_address            = google_compute_global_address.lb_ip[0].address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
