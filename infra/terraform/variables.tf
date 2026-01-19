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

variable "github_branch" {
  type        = string
  description = "GitHub branch for Cloud Build triggers"
  default     = "main"
}

variable "api_service_name" {
  type        = string
  default     = "crm-api"
}

variable "web_service_name" {
  type        = string
  default     = "crm-web"
}

variable "worker_job_name" {
  type        = string
  default     = "crm-worker"
}

variable "migrate_job_name" {
  type        = string
  default     = "crm-migrate"
}

variable "database_tier" {
  type        = string
  default     = "db-g1-small"
}

variable "database_version" {
  type        = string
  default     = "POSTGRES_15"
}

variable "database_name" {
  type        = string
  default     = "crm"
}

variable "database_user" {
  type        = string
  default     = "crm_user"
}

variable "database_password" {
  type        = string
  sensitive   = true
}

variable "redis_memory_size_gb" {
  type        = number
  default     = 1
}

variable "vpc_connector_cidr" {
  type        = string
  default     = "10.8.0.0/28"
}

variable "backup_start_time" {
  type        = string
  default     = "03:00"
}

variable "enable_pitr" {
  type        = bool
  default     = true
}

variable "manage_storage_buckets" {
  type        = bool
  default     = false
}

variable "storage_bucket_location" {
  type        = string
  default     = "us-central1"
}

variable "secret_replication_location" {
  type        = string
  description = "Secret Manager replica location (must comply with org policy)."
  default     = "us-central1"
}

variable "storage_service_account_email" {
  type        = string
  default     = ""
}

variable "run_cpu" {
  type        = string
  default     = "1"
}

variable "run_memory" {
  type        = string
  default     = "1Gi"
}

variable "run_min_instances" {
  type        = number
  default     = 0
}

variable "run_max_instances" {
  type        = number
  default     = 10
}

variable "storage_backend" {
  type        = string
  default     = "s3"
}

variable "s3_bucket" {
  type        = string
}

variable "s3_region" {
  type        = string
  default     = "us-east-1"
}

variable "s3_endpoint_url" {
  type        = string
  default     = ""
}

variable "s3_public_base_url" {
  type        = string
  default     = ""
}

variable "s3_url_style" {
  type        = string
  default     = "path"
}

variable "export_storage_backend" {
  type        = string
  default     = "s3"
}

variable "export_s3_bucket" {
  type        = string
}

variable "export_s3_region" {
  type        = string
  default     = "us-east-1"
}

variable "export_s3_endpoint_url" {
  type        = string
  default     = ""
}

variable "attachment_scan_enabled" {
  type        = bool
  default     = true
}

variable "allowed_email_domains" {
  type        = string
  default     = ""
}

variable "gcp_monitoring_enabled" {
  type        = bool
  default     = true
}

variable "logging_retention_days" {
  type        = number
  description = "Cloud Logging retention in days for the default bucket."
  default     = 90
}

variable "manage_secret_versions" {
  type        = bool
  description = "Whether Terraform should create Secret Manager versions (stores secret values in state)."
  default     = true
}

variable "secrets" {
  type        = map(string)
  sensitive   = true
  description = "Map of secret values (provided via TF_VAR_secrets)."
  default     = {}
  validation {
    condition = var.manage_secret_versions ? alltrue([
      for k in [
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
      ] : contains(keys(var.secrets), k)
    ]) : true
    error_message = "secrets map is missing one or more required keys when manage_secret_versions=true."
  }
}

variable "enable_domain_mapping" {
  type        = bool
  default     = true
}

variable "enable_public_invoker" {
  type        = bool
  default     = true
}

variable "enable_cloudbuild_triggers" {
  type        = bool
  default     = true
}
