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
  redis.googleapis.com
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

## 3) Init + Apply
```bash
terraform init -backend-config="bucket=YOUR_STATE_BUCKET"
terraform apply
```

## 4) DNS
Terraform creates Cloud Run domain mappings (if enabled). Add the CNAME/TXT records shown in the Cloud Run console
for `api.<domain>` and `app.<domain>` in Cloudflare.

## 5) Build + Deploy
Cloud Build triggers are created for API and Web builds.
Push to `main` to build + deploy both services.

## Notes
- Migrations are defined as a Cloud Run job. Run manually when needed:
  `gcloud run jobs execute crm-migrate --region us-central1`
- Worker job is updated by the API build trigger.
