variable "project_id" {
  type        = string
  description = "GCP project id"
}

variable "region" {
  type        = string
  description = "GCP region"
  default     = "us-central1"
}

variable "domain" {
  type        = string
  description = "Base domain (e.g. example.com)"
}

variable "artifact_repo" {
  type        = string
  description = "Artifact Registry repo name"
  default     = "crm"
}

variable "github_owner" {
  type        = string
  description = "GitHub org/user for Cloud Build triggers"
}

variable "github_repo" {
  type        = string
  description = "GitHub repo name for Cloud Build triggers"
}

variable "cloudbuild_repository" {
  type        = string
  description = "Cloud Build repository resource name (2nd gen)."
  default     = ""
}

variable "run_region" {
  type        = string
  description = "Region for Cloud Run, Cloud SQL, Redis"
}

variable "cloudbuild_location" {
  type        = string
  description = "Location/region for Cloud Build v2 connections and triggers"
}

variable "github_branch" {
  type        = string
  description = "GitHub branch for Cloud Build triggers"
  default     = "main"
}

variable "api_service_name" {
  type    = string
  default = "crm-api"
}

variable "web_service_name" {
  type    = string
  default = "crm-web"
}

variable "worker_job_name" {
  type    = string
  default = "crm-worker"
}

variable "migrate_job_name" {
  type    = string
  default = "crm-migrate"
}

variable "database_tier" {
  type    = string
  default = "db-g1-small"
}

variable "database_version" {
  type    = string
  default = "POSTGRES_15"
}

variable "database_name" {
  type    = string
  default = "crm"
}

variable "database_user" {
  type    = string
  default = "crm_user"
}

variable "manage_database_user" {
  type        = bool
  description = "Whether Terraform should create the database user (password stored in state)."
  default     = false
}

variable "database_password" {
  type      = string
  sensitive = true
  default   = ""
  validation {
    condition     = var.manage_database_user ? length(var.database_password) > 0 : true
    error_message = "database_password is required when manage_database_user=true."
  }
}

variable "redis_memory_size_gb" {
  type    = number
  default = 1
}

variable "vpc_connector_cidr" {
  type    = string
  default = "10.8.0.0/28"
}

variable "private_service_access_address" {
  type        = string
  description = "Optional base address for the Private Service Access range (leave null for auto-assignment)."
  default     = null
}

variable "private_service_access_prefix_length" {
  type        = number
  description = "Prefix length for the Private Service Access range."
  default     = 16
}
variable "backup_start_time" {
  type    = string
  default = "03:00"
}

variable "enable_pitr" {
  type    = bool
  default = true
}

variable "manage_storage_buckets" {
  type    = bool
  default = false
}

variable "storage_bucket_location" {
  type    = string
  default = "us-central1"
}

variable "secret_replication_location" {
  type        = string
  description = "Secret Manager replica location (must comply with org policy)."
  default     = "us-central1"
}

variable "storage_service_account_email" {
  type    = string
  default = ""
}

variable "run_cpu" {
  type    = string
  default = "1"
}

variable "run_memory" {
  type    = string
  default = "1Gi"
}

variable "run_min_instances" {
  type    = number
  default = 0
}

variable "run_max_instances" {
  type    = number
  default = 10
}

variable "storage_backend" {
  type    = string
  default = "s3"
}

variable "s3_bucket" {
  type = string
}

variable "s3_region" {
  type    = string
  default = "us-east-1"
}

variable "s3_endpoint_url" {
  type    = string
  default = ""
}

variable "s3_public_base_url" {
  type    = string
  default = ""
}

variable "s3_url_style" {
  type    = string
  default = "path"
}

variable "export_storage_backend" {
  type    = string
  default = "s3"
}

variable "export_s3_bucket" {
  type = string
}

variable "export_s3_region" {
  type    = string
  default = "us-east-1"
}

variable "export_s3_endpoint_url" {
  type    = string
  default = ""
}

variable "attachment_scan_enabled" {
  type    = bool
  default = true
}

variable "allowed_email_domains" {
  type    = string
  default = ""
}

variable "gcp_monitoring_enabled" {
  type    = bool
  default = true
}

variable "logging_retention_days" {
  type        = number
  description = "Cloud Logging retention in days for the default bucket."
  default     = 90
}

variable "enable_domain_mapping" {
  type    = bool
  default = true
}

variable "enable_public_invoker" {
  type    = bool
  default = true
}

variable "enable_cloudbuild_triggers" {
  type    = bool
  default = true
}

variable "alert_notification_channel_ids" {
  type        = list(string)
  description = "Monitoring notification channel IDs for alerts (Slack/email)."
  default     = []
}

variable "billing_account_id" {
  type        = string
  description = "Billing account ID for budget alerts and exports."
  default     = ""
  validation {
    condition     = (var.billing_budget_enabled || var.billing_weekly_summary_enabled) ? length(var.billing_account_id) > 0 : true
    error_message = "billing_account_id is required when billing budgets or weekly summaries are enabled."
  }
}

variable "billing_budget_enabled" {
  type    = bool
  default = true
}

variable "billing_budget_amount_usd" {
  type        = number
  description = "Monthly budget amount in USD."
  default     = 300
}

variable "billing_budget_thresholds" {
  type        = list(number)
  description = "Budget alert thresholds (0-1)."
  default     = [0.5, 0.75, 0.9, 1.0]
}

variable "billing_export_dataset" {
  type        = string
  description = "BigQuery dataset for Cloud Billing export."
  default     = "billing_export"
}

variable "billing_export_dataset_location" {
  type        = string
  description = "BigQuery dataset location for Cloud Billing export."
  default     = "US"
}

variable "billing_weekly_summary_enabled" {
  type    = bool
  default = false
}

variable "billing_weekly_job_name" {
  type    = string
  default = "crm-billing-weekly"
}

variable "billing_weekly_summary_cron" {
  type        = string
  description = "Cron schedule for weekly billing summary."
  default     = "0 13 * * 1"
}

variable "billing_weekly_summary_timezone" {
  type        = string
  description = "Timezone for weekly billing summary schedule."
  default     = "Etc/UTC"
}
