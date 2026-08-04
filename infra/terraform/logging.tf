resource "google_logging_project_bucket_config" "default_retention" {
  project        = var.project_id
  location       = "global"
  bucket_id      = "_Default"
  retention_days = var.logging_retention_days
}

# Cloud Run request logs retain the full request target before application
# middleware can sanitize it. Unsubscribe URLs therefore use opaque,
# single-purpose tokens and their platform request logs are not retained.
# Route-template metrics emitted by the API and Cloud Run service metrics remain
# available because this exclusion only matches run.googleapis.com/requests.
resource "google_logging_project_exclusion" "unsubscribe_request_urls" {
  project     = var.project_id
  name        = "unsubscribe-request-urls"
  description = "Do not retain Cloud Run request URLs containing unsubscribe bearer tokens"
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    log_id("run.googleapis.com/requests")
    httpRequest.requestUrl =~ "/email/unsubscribe/"
  EOT
}
