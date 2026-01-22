resource "google_compute_network" "crm" {
  name                    = "crm-vpc"
  auto_create_subnetworks = true
}

resource "google_compute_global_address" "private_service_access" {
  name          = "crm-private-service-access"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = var.private_service_access_prefix_length
  address       = var.private_service_access_address
  network       = google_compute_network.crm.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.crm.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_access.name]
}

resource "google_vpc_access_connector" "crm" {
  name          = "crm-connector"
  region        = var.region
  network       = google_compute_network.crm.name
  ip_cidr_range = var.vpc_connector_cidr
}
