# Terraform (GCP + Cloud Build)

This folder provisions infrastructure for Cloud Run + Cloud Build with remote state.
It expects you to provide secrets via `TF_VAR_secrets` (never commit them).

## 1) One-time bootstrap

Create a GCS bucket for Terraform state (global unique name):
```bash
gcloud storage buckets create gs://YOUR_STATE_BUCKET \
  --project YOUR_PROJECT_ID \
  --location US \
  --uniform-bucket-level-access
```
Helper:
```bash
scripts/bootstrap_tf_state_bucket.sh YOUR_PROJECT_ID YOUR_STATE_BUCKET US
```

Enable required APIs:
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  redis.googleapis.com \
  vpcaccess.googleapis.com
```

Authenticate for Terraform (ADC):
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Connect GitHub to Cloud Build (Console):
- Cloud Build -> Settings -> GitHub -> Connect
- Ensure the repo is authorized

## 2) Configure variables

Create `terraform.tfvars` (do not commit):
```hcl
project_id         = "your-project-id"
region             = "us-central1"
domain             = "example.com"
github_owner       = "your-org"
github_repo        = "your-repo"

database_password  = "..."
s3_bucket          = "..."
export_s3_bucket   = "..."

# Optional
allowed_email_domains = ""
secret_replication_location = "us-central1"
enable_cloudbuild_triggers = true
enable_public_invoker = true
enable_domain_mapping = true
```
You can copy the example:
```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Provide secrets via environment variable:
```bash
export TF_VAR_secrets='{
  "JWT_SECRET":"...",
  "DEV_SECRET":"...",
  "INTERNAL_SECRET":"...",
  "META_ENCRYPTION_KEY":"...",
  "FERNET_KEY":"...",
  "DATA_ENCRYPTION_KEY":"...",
  "PII_HASH_KEY":"...",
  "GOOGLE_CLIENT_ID":"...",
  "GOOGLE_CLIENT_SECRET":"...",
  "ZOOM_CLIENT_ID":"...",
  "ZOOM_CLIENT_SECRET":"...",
  "AWS_ACCESS_KEY_ID":"...",
  "AWS_SECRET_ACCESS_KEY":"..."
}'
```
Helper (optional):
```bash
export TF_VAR_secrets="$(scripts/prepare_tf_secrets.sh)"
```

If your org policy blocks global secrets, set `secret_replication_location` to an allowed region
(for example `us-central1`).

## GCS instead of AWS S3 (optional)
To stay fully on GCP, use GCS with S3 interoperability.
1. Create two GCS buckets (attachments + exports).
2. Enable HMAC keys: Cloud Storage -> Settings -> Interoperability -> Create key.
3. Use the HMAC Access Key + Secret as `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.

Command shortcut for HMAC keys:
```bash
gcloud storage hmac create SERVICE_ACCOUNT_EMAIL --project YOUR_PROJECT_ID
```

Set these optional vars in `terraform.tfvars`:
```hcl
s3_endpoint_url        = "https://storage.googleapis.com"
s3_public_base_url     = "https://storage.googleapis.com"
s3_url_style           = "path"
export_s3_endpoint_url = "https://storage.googleapis.com"
```

## Storage hardening (recommended for HIPAA)
To have Terraform enforce private buckets and IAM:
```hcl
manage_storage_buckets = true
storage_bucket_location = "us-central1"
storage_service_account_email = "crm-storage-sa@your-project-id.iam.gserviceaccount.com"
```
If buckets already exist, import them before apply:
```bash
terraform import 'google_storage_bucket.attachments[0]' surrogacyforce-attachments-test
terraform import 'google_storage_bucket.exports[0]' surrogacyforce-exports-test
```

## 3) Init + Apply
```bash
terraform init -backend-config="bucket=YOUR_STATE_BUCKET"
terraform apply
```
If you see backend/credentials errors, rerun:
```bash
terraform init -reconfigure -backend-config="bucket=YOUR_STATE_BUCKET"
```

## What Terraform configures for HIPAA readiness
- Cloud SQL backups + PITR enabled
- GCS buckets: public access prevention + uniform bucket-level access (if managed)
- Audit logs for GCS + Cloud SQL (DATA_READ/DATA_WRITE/ADMIN_READ)

## 4) DNS
Terraform creates Cloud Run domain mappings (if enabled). Add the CNAME/TXT records shown in the Cloud Run console
for `api.<domain>` and `app.<domain>` in Cloudflare.

If your org policy blocks `allUsers`, set:
```hcl
enable_public_invoker = false
```
You can re-enable after you wire up a private invoker/IAP.

If domain mapping fails due to verification, set:
```hcl
enable_domain_mapping = false
```
Then verify domain ownership in Google Search Console and re-enable.

## 5) Build + Deploy
Cloud Build triggers are created for API and Web builds.
Push to `main` to build + deploy both services.

## Notes
- Migrations are defined as a Cloud Run job. Run manually when needed:
  `gcloud run jobs execute crm-migrate --region us-central1`
- Worker job is updated by the API build trigger.
