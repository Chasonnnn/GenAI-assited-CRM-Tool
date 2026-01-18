output "api_url" {
  value = local.api_url
}

output "web_url" {
  value = local.app_url
}

output "cloudsql_connection_name" {
  value = google_sql_database_instance.crm.connection_name
}

output "redis_host" {
  value = google_redis_instance.crm.host
}

output "artifact_registry_repo" {
  value = google_artifact_registry_repository.crm.repository_id
}
