resource "google_compute_network" "crm" {
  name                    = "crm-vpc"
  auto_create_subnetworks = true
}

resource "google_vpc_access_connector" "crm" {
  name          = "crm-connector"
  region        = var.region
  network       = google_compute_network.crm.name
  ip_cidr_range = var.vpc_connector_cidr
}
