locals {
  app_url = "https://app.${var.domain}"
  api_url = "https://api.${var.domain}"

  api_image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/api:latest"
  web_image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/web:latest"

  optional_env = merge(
    var.s3_endpoint_url != "" ? { S3_ENDPOINT_URL = var.s3_endpoint_url } : {},
    var.s3_public_base_url != "" ? { S3_PUBLIC_BASE_URL = var.s3_public_base_url } : {},
    var.export_s3_endpoint_url != "" ? { EXPORT_S3_ENDPOINT_URL = var.export_s3_endpoint_url } : {},
    { S3_URL_STYLE = var.s3_url_style }
  )

  common_env = merge({
    ENV                          = "production"
    API_BASE_URL                 = local.api_url
    FRONTEND_URL                 = local.app_url
    CORS_ORIGINS                 = local.app_url
    GOOGLE_REDIRECT_URI          = "${local.api_url}/auth/google/callback"
    ZOOM_REDIRECT_URI            = "${local.api_url}/integrations/zoom/callback"
    GMAIL_REDIRECT_URI           = "${local.api_url}/integrations/gmail/callback"
    GOOGLE_CALENDAR_REDIRECT_URI = "${local.api_url}/integrations/google-calendar/callback"
    DUO_REDIRECT_URI             = "${local.app_url}/auth/duo/callback"
    STORAGE_BACKEND              = var.storage_backend
    S3_BUCKET                    = var.s3_bucket
    S3_REGION                    = var.s3_region
    EXPORT_STORAGE_BACKEND       = var.export_storage_backend
    EXPORT_S3_BUCKET             = var.export_s3_bucket
    EXPORT_S3_REGION             = var.export_s3_region
    ATTACHMENT_SCAN_ENABLED      = tostring(var.attachment_scan_enabled)
    ALLOWED_EMAIL_DOMAINS        = var.allowed_email_domains
    GCP_MONITORING_ENABLED       = tostring(var.gcp_monitoring_enabled)
    GCP_PROJECT_ID               = var.project_id
    GCP_SERVICE_NAME             = var.api_service_name
  }, local.optional_env)

  common_secret_keys = [
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "DEV_SECRET",
    "INTERNAL_SECRET",
    "META_ENCRYPTION_KEY",
    "FERNET_KEY",
    "DATA_ENCRYPTION_KEY",
    "PII_HASH_KEY",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "ZOOM_CLIENT_ID",
    "ZOOM_CLIENT_SECRET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY"
  ]
}
