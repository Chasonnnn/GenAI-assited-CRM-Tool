resource "google_artifact_registry_repository" "crm" {
  location      = var.region
  repository_id = var.artifact_repo
  description   = "Surrogacy Force images"
  format        = "DOCKER"
}
