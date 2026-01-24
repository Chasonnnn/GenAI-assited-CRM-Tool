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
