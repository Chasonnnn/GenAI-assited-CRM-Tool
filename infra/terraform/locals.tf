locals {
  app_url = "https://app.${var.domain}"
  ops_url = var.ops_frontend_url != "" ? var.ops_frontend_url : "https://ops.${var.domain}"
  api_url = "https://api.${var.domain}"

  api_image    = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/api:latest"
  worker_image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/worker:latest"
  web_image    = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_repo}/web:latest"

  monitoring_webhook_enabled = var.monitoring_webhook_token != ""
  monitoring_webhook_url     = "${local.api_url}/internal/alerts/gcp"
  alert_notification_channels = concat(
    var.alert_notification_channel_ids,
    google_monitoring_notification_channel.ops_webhook[*].name
  )
  alerting_enabled = length(local.alert_notification_channels) > 0
  cors_origins     = join(",", distinct(compact([local.app_url, local.ops_url])))

  optional_env = merge(
    var.s3_endpoint_url != "" ? { S3_ENDPOINT_URL = var.s3_endpoint_url } : {},
    var.s3_public_base_url != "" ? { S3_PUBLIC_BASE_URL = var.s3_public_base_url } : {},
    var.export_s3_endpoint_url != "" ? { EXPORT_S3_ENDPOINT_URL = var.export_s3_endpoint_url } : {},
    { S3_URL_STYLE = var.s3_url_style }
  )

  common_env = merge({
    ENV                             = "production"
    PLATFORM_BASE_DOMAIN            = var.domain
    API_BASE_URL                    = local.api_url
    FRONTEND_URL                    = local.app_url
    OPS_FRONTEND_URL                = local.ops_url
    COOKIE_DOMAIN                   = var.cookie_domain
    PLATFORM_ADMIN_EMAILS           = var.platform_admin_emails
    CORS_ORIGINS                    = local.cors_origins
    GOOGLE_REDIRECT_URI             = "${local.api_url}/auth/google/callback"
    ZOOM_REDIRECT_URI               = "${local.api_url}/integrations/zoom/callback"
    GMAIL_REDIRECT_URI              = "${local.api_url}/integrations/gmail/callback"
    GOOGLE_CALENDAR_REDIRECT_URI    = "${local.api_url}/integrations/google-calendar/callback"
    DUO_REDIRECT_URI                = "${local.app_url}/auth/duo/callback"
    STORAGE_BACKEND                 = var.storage_backend
    S3_BUCKET                       = var.s3_bucket
    S3_REGION                       = var.s3_region
    EXPORT_STORAGE_BACKEND          = var.export_storage_backend
    EXPORT_S3_BUCKET                = var.export_s3_bucket
    EXPORT_S3_REGION                = var.export_s3_region
    ATTACHMENT_SCAN_ENABLED         = tostring(var.attachment_scan_enabled)
    CLAMAV_SIGNATURES_BUCKET        = var.clamav_signatures_bucket
    CLAMAV_SIGNATURES_PREFIX        = var.clamav_signatures_prefix
    CLAMAV_SIGNATURES_MAX_AGE_HOURS = tostring(var.clamav_signatures_max_age_hours)
    CLAMAV_SIGNATURES_DOWNLOAD_ONLY = tostring(var.clamav_signatures_download_only)
    ALLOWED_EMAIL_DOMAINS           = var.allowed_email_domains
    GCP_MONITORING_ENABLED          = tostring(var.gcp_monitoring_enabled)
    GCP_PROJECT_ID                  = var.project_id
    GCP_SERVICE_NAME                = var.api_service_name
    DB_MIGRATION_CHECK              = tostring(var.db_migration_check)
    DB_AUTO_MIGRATE                 = tostring(var.db_auto_migrate)
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
    "AWS_SECRET_ACCESS_KEY",
    "META_APP_ID",
    "META_APP_SECRET",
    "META_VERIFY_TOKEN",
    "META_ACCESS_TOKEN",
    "DUO_CLIENT_ID",
    "DUO_CLIENT_SECRET",
    "DUO_API_HOST",
    "PLATFORM_RESEND_API_KEY",
    "PLATFORM_RESEND_WEBHOOK_SECRET"
  ]

  billing_secret_keys = [
    "BILLING_SLACK_WEBHOOK_URL"
  ]

  all_secret_keys = concat(local.common_secret_keys, local.billing_secret_keys)

  billing_export_table = "gcp_billing_export_v1_${replace(var.billing_account_id, "-", "")}"
}
