variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region."
  type        = string
  default     = "us-central1"
}

variable "domain" {
  description = "Base domain (e.g. example.com)."
  type        = string
}

variable "ops_frontend_url" {
  description = "Ops console frontend URL (for platform admin redirects)."
  type        = string
  default     = ""
}

variable "cookie_domain" {
  description = "Cookie domain for cross-subdomain auth (e.g., .example.com)."
  type        = string
  default     = ""
}

variable "platform_admin_emails" {
  description = "Comma-separated platform admin email allowlist."
  type        = string
  default     = ""
}

variable "artifact_repo" {
  description = "Artifact Registry repo name."
  type        = string
  default     = "crm"
}

variable "github_owner" {
  description = "GitHub org/user for Cloud Build triggers."
  type        = string
}

variable "github_repo" {
  description = "GitHub repo name for Cloud Build triggers."
  type        = string
}

variable "cloudbuild_repository" {
  description = "Cloud Build repository resource name (2nd gen)."
  type        = string
  default     = ""
}

variable "run_region" {
  description = "Region for Cloud Run, Cloud SQL, Redis."
  type        = string
}

variable "cloudbuild_location" {
  description = "Location/region for Cloud Build v2 connections and triggers."
  type        = string
}

variable "github_branch" {
  description = "GitHub branch for Cloud Build triggers."
  type        = string
  default     = "main"
}

variable "github_tag_regex" {
  description = "Tag regex (RE2) for Cloud Build deploy triggers (e.g. ^v.*$)."
  type        = string
  default     = "^surrogacy-crm-platform-v.*$"
}

variable "api_service_name" {
  description = "Name of the Cloud Run API service."
  type        = string
  default     = "crm-api"
}

variable "web_service_name" {
  description = "Name of the Cloud Run web frontend service."
  type        = string
  default     = "crm-web"
}

variable "worker_job_name" {
  description = "Name of the Cloud Run worker job."
  type        = string
  default     = "crm-worker"
}

variable "migrate_job_name" {
  description = "Name of the Cloud Run database migration job."
  type        = string
  default     = "crm-migrate"
}

variable "database_tier" {
  description = "Cloud SQL instance machine type."
  type        = string
  default     = "db-g1-small"
}

variable "database_version" {
  description = "Cloud SQL PostgreSQL version."
  type        = string
  default     = "POSTGRES_15"
}

variable "database_deletion_protection" {
  description = "Protect Cloud SQL instance from accidental deletion."
  type        = bool
  default     = true
}

variable "database_name" {
  description = "Name of the PostgreSQL database."
  type        = string
  default     = "crm"
}

variable "database_user" {
  description = "PostgreSQL database user name."
  type        = string
  default     = "crm_user"
}

variable "manage_database_user" {
  description = "Whether Terraform should create the database user (password stored in state)."
  type        = bool
  default     = false
}

variable "database_password" {
  description = "PostgreSQL database user password."
  type        = string
  default     = ""
  sensitive   = true

  validation {
    condition     = var.manage_database_user ? length(var.database_password) > 0 : true
    error_message = "database_password is required when manage_database_user=true."
  }
}

variable "redis_memory_size_gb" {
  description = "Redis instance memory size in GB."
  type        = number
  default     = 1
}

variable "vpc_connector_cidr" {
  description = "CIDR range for the VPC connector used by Cloud Run."
  type        = string
  default     = "10.8.0.0/28"
}

variable "private_service_access_address" {
  description = "Optional base address for the Private Service Access range (leave null for auto-assignment)."
  type        = string
  default     = null
}

variable "private_service_access_prefix_length" {
  description = "Prefix length for the Private Service Access range."
  type        = number
  default     = 16
}

variable "backup_start_time" {
  description = "Cloud SQL backup start time in HH:MM format (UTC)."
  type        = string
  default     = "03:00"
}

variable "enable_pitr" {
  description = "Enable point-in-time recovery for Cloud SQL."
  type        = bool
  default     = true
}

variable "manage_storage_buckets" {
  description = "Whether Terraform should create and manage GCS storage buckets."
  type        = bool
  default     = false
}

variable "storage_bucket_location" {
  description = "GCS bucket location for managed storage buckets."
  type        = string
  default     = "us-central1"
}

variable "secret_replication_location" {
  description = "Secret Manager replica location (must comply with org policy)."
  type        = string
  default     = "us-central1"
}

variable "storage_service_account_email" {
  description = "Service account email for storage bucket access."
  type        = string
  default     = ""
}

variable "run_cpu" {
  description = "CPU allocation for Cloud Run services."
  type        = string
  default     = "1"

  # Cloud Run CPU values are strings. We intentionally cap these services at
  # 0.5–1 vCPU to control cost and latency jitter.
  validation {
    condition     = contains(["0.5", "500m", "1", "1000m"], var.run_cpu)
    error_message = "run_cpu must be 0.5 or 1 vCPU (\"0.5\"/\"500m\" or \"1\"/\"1000m\")."
  }
}

variable "run_memory" {
  description = "Memory allocation for Cloud Run services."
  type        = string
  default     = "1Gi"
}

variable "run_cpu_idle" {
  description = "Whether Cloud Run should throttle CPU when idle (CPU allocated only during request handling)."
  type        = bool
  default     = true
}

variable "run_min_instances" {
  description = "Minimum number of Cloud Run instances."
  type        = number
  default     = 1
}

variable "run_max_instances" {
  description = "Maximum number of Cloud Run instances."
  type        = number
  default     = 10
}

variable "storage_backend" {
  description = "Storage backend type for file attachments (gcs or s3)."
  type        = string
  default     = "s3"
}

variable "s3_bucket" {
  description = "S3 bucket name for file attachments."
  type        = string
}

variable "s3_region" {
  description = "S3 bucket region."
  type        = string
  default     = "us-east-1"
}

variable "s3_endpoint_url" {
  description = "Custom S3 endpoint URL (for S3-compatible storage)."
  type        = string
  default     = ""
}

variable "s3_public_base_url" {
  description = "Public base URL for S3 objects (for signed URLs)."
  type        = string
  default     = ""
}

variable "s3_url_style" {
  description = "S3 URL style: path or virtual-hosted."
  type        = string
  default     = "path"
}

variable "export_storage_backend" {
  description = "Storage backend type for data exports (gcs or s3)."
  type        = string
  default     = "s3"
}

variable "export_s3_bucket" {
  description = "S3 bucket name for data exports."
  type        = string
}

variable "export_s3_region" {
  description = "S3 bucket region for data exports."
  type        = string
  default     = "us-east-1"
}

variable "export_s3_endpoint_url" {
  description = "Custom S3 endpoint URL for data exports."
  type        = string
  default     = ""
}

variable "attachment_scan_enabled" {
  description = "Enable malware scanning for file attachments."
  type        = bool
  default     = true
}

variable "allowed_email_domains" {
  description = "Comma-separated list of allowed email domains for user registration."
  type        = string
  default     = ""
}

variable "gcp_monitoring_enabled" {
  description = "Enable GCP Cloud Monitoring integration."
  type        = bool
  default     = true
}

variable "db_migration_check" {
  description = "Fail readiness checks when database migrations are pending."
  type        = bool
  default     = true
}

variable "db_auto_migrate" {
  description = "Automatically apply Alembic migrations on API startup."
  type        = bool
  default     = false
}

variable "logging_retention_days" {
  description = "Cloud Logging retention in days for the default bucket."
  type        = number
  default     = 90
}

variable "enable_domain_mapping" {
  description = "Enable custom domain mapping for Cloud Run services."
  type        = bool
  default     = true
}

variable "enable_load_balancer" {
  description = "Enable external HTTPS load balancer for wildcard subdomains."
  type        = bool
  default     = false
}

variable "enable_public_invoker" {
  description = "Allow unauthenticated public access to Cloud Run services."
  type        = bool
  default     = true
}

variable "enable_cloudbuild_triggers" {
  description = "Enable Cloud Build triggers for CI/CD."
  type        = bool
  default     = true
}

variable "alert_notification_channel_ids" {
  description = "Monitoring notification channel IDs for alerts (Slack/email)."
  type        = list(string)
  default     = []
}

variable "monitoring_webhook_token" {
  description = "Token for authenticating the internal monitoring webhook (sent via header)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "billing_account_id" {
  description = "Billing account ID for budget alerts and exports."
  type        = string
  default     = ""

  validation {
    condition     = (var.billing_budget_enabled || var.billing_weekly_summary_enabled) ? length(var.billing_account_id) > 0 : true
    error_message = "billing_account_id is required when billing budgets or weekly summaries are enabled."
  }
}

variable "billing_budget_enabled" {
  description = "Enable Cloud Billing budget alerts."
  type        = bool
  default     = true
}

variable "billing_budget_amount_usd" {
  description = "Monthly budget amount in USD."
  type        = number
  default     = 300
}

variable "billing_budget_thresholds" {
  description = "Budget alert thresholds (0-1)."
  type        = list(number)
  default     = [0.5, 0.75, 0.9, 1.0]
}

variable "billing_export_dataset" {
  description = "BigQuery dataset for Cloud Billing export."
  type        = string
  default     = "billing_export"
}

variable "billing_export_dataset_location" {
  description = "BigQuery dataset location for Cloud Billing export."
  type        = string
  default     = "US"
}

variable "billing_weekly_summary_enabled" {
  description = "Enable weekly billing summary reports."
  type        = bool
  default     = false
}

variable "billing_weekly_job_name" {
  description = "Name of the Cloud Run job for weekly billing summaries."
  type        = string
  default     = "crm-billing-weekly"
}

variable "billing_weekly_summary_cron" {
  description = "Cron schedule for weekly billing summary."
  type        = string
  default     = "0 13 * * 1"
}

variable "billing_weekly_summary_timezone" {
  description = "Timezone for weekly billing summary schedule."
  type        = string
  default     = "Etc/UTC"
}
