resource "google_service_account" "api" {
  account_id   = "crm-api-sa"
  display_name = "Surrogacy Force API Service Account"
}

resource "google_service_account" "web" {
  account_id   = "crm-web-sa"
  display_name = "Surrogacy Force Web Service Account"
}

resource "google_service_account" "worker" {
  account_id   = "crm-worker-sa"
  display_name = "Surrogacy Force Worker Service Account"
}

resource "google_service_account" "cloudbuild" {
  account_id   = "crm-cloudbuild-sa"
  display_name = "Surrogacy Force Cloud Build Service Account"
}
