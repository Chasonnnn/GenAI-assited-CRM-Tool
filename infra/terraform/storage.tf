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

resource "google_storage_bucket_iam_member" "attachments_storage_admin" {
  count  = var.manage_storage_buckets && var.storage_service_account_email != "" ? 1 : 0
  bucket = google_storage_bucket.attachments[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.storage_service_account_email}"
}

resource "google_storage_bucket_iam_member" "exports_storage_admin" {
  count  = var.manage_storage_buckets && var.storage_service_account_email != "" ? 1 : 0
  bucket = google_storage_bucket.exports[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.storage_service_account_email}"
}
