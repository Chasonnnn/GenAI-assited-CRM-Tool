output "api_url" {
  description = "Public URL of the Cloud Run API service."
  value       = local.api_url
}

output "web_url" {
  description = "Public URL of the Cloud Run web frontend."
  value       = local.app_url
}

output "cloudsql_connection_name" {
  description = "Cloud SQL instance connection string for Cloud Run."
  value       = google_sql_database_instance.crm.connection_name
}

output "redis_host" {
  description = "Redis instance hostname for internal access."
  value       = google_redis_instance.crm.host
}

output "artifact_registry_repo" {
  description = "Artifact Registry repository ID for container images."
  value       = google_artifact_registry_repository.crm.repository_id
}

output "load_balancer_ip" {
  description = "External IP address for the load balancer (when enabled)."
  value       = var.enable_load_balancer ? google_compute_global_address.lb_ip[0].address : null
}

output "lb_dns_authorization_root" {
  description = "DNS record for root domain authorization (Certificate Manager)."
  value       = var.enable_load_balancer ? google_certificate_manager_dns_authorization.root[0].dns_resource_record : null
}
