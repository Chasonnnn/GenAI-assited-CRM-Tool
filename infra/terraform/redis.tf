resource "google_redis_instance" "crm" {
  name               = "crm-redis"
  region             = var.region
  memory_size_gb     = var.redis_memory_size_gb
  tier               = "BASIC"
  authorized_network = google_compute_network.crm.id

  auth_enabled = false

  lifecycle {
    ignore_changes = [auth_enabled]
  }
}
