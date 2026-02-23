resource "google_storage_bucket" "attachments" {
  count    = var.manage_storage_buckets ? 1 : 0
  name     = var.s3_bucket
  location = var.storage_bucket_location

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket" "exports" {
  count    = var.manage_storage_buckets ? 1 : 0
  name     = var.export_s3_bucket
  location = var.storage_bucket_location

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket_iam_member" "attachments_storage_admin_managed" {
  count  = var.manage_storage_buckets && var.storage_service_account_email != "" ? 1 : 0
  bucket = google_storage_bucket.attachments[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.storage_service_account_email}"
}

resource "google_storage_bucket_iam_member" "exports_storage_admin_managed" {
  count  = var.manage_storage_buckets && var.storage_service_account_email != "" ? 1 : 0
  bucket = google_storage_bucket.exports[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.storage_service_account_email}"
}

# Apply storage IAM bindings even when buckets are pre-existing and managed
# outside Terraform. This keeps storage access durable across migrations.
resource "google_storage_bucket_iam_member" "attachments_storage_admin_existing" {
  count  = !var.manage_storage_buckets && var.storage_service_account_email != "" ? 1 : 0
  bucket = var.s3_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.storage_service_account_email}"
}

resource "google_storage_bucket_iam_member" "exports_storage_admin_existing" {
  count  = !var.manage_storage_buckets && var.storage_service_account_email != "" ? 1 : 0
  bucket = var.export_s3_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.storage_service_account_email}"
}

# Preserve state continuity after renaming IAM resources.
moved {
  from = google_storage_bucket_iam_member.attachments_storage_admin
  to   = google_storage_bucket_iam_member.attachments_storage_admin_managed
}

moved {
  from = google_storage_bucket_iam_member.exports_storage_admin
  to   = google_storage_bucket_iam_member.exports_storage_admin_managed
}
