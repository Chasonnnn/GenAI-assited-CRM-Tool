# Terraform Deployment Guide (Step-by-Step)

This is a beginner-friendly checklist to deploy Surrogacy Force on GCP using Terraform + Cloud Build.
Follow the steps in order. Anything marked "manual" is something you must do in the GCP console.

## 0) What you need
- A GCP project with billing enabled.
- `gcloud` installed and logged in.
- Terraform installed (`terraform --version`).
- A GitHub repo connected to Cloud Build (manual step).
- A domain in Cloudflare (for `app.<domain>` and `api.<domain>`).

## 1) Set your working variables
Pick a project and region. Replace placeholders.
```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export DOMAIN="example.com"
```

Confirm gcloud is using your project:
```bash
gcloud config set project "$PROJECT_ID"
```

## 2) Enable required APIs
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  redis.googleapis.com
```

## 3) Create a Terraform state bucket (one-time)
Terraform needs a GCS bucket to store state.
```bash
export TF_STATE_BUCKET="${PROJECT_ID}-tfstate"
gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
  --project "$PROJECT_ID" \
  --location "US" \
  --uniform-bucket-level-access
```
Or use the helper script:
```bash
scripts/bootstrap_tf_state_bucket.sh "$PROJECT_ID" "$TF_STATE_BUCKET" "US"
```

## 4) Connect GitHub to Cloud Build (manual)
In the GCP Console:
1. Go to Cloud Build -> Settings -> GitHub.
2. Connect your GitHub account/org.
3. Authorize the repo you want to deploy.

## 5) Create `terraform.tfvars` (do not commit)
Create `infra/terraform/terraform.tfvars` with your values:
```hcl
project_id        = "your-project-id"
region            = "us-central1"
domain            = "example.com"
github_owner      = "your-github-org-or-user"
github_repo       = "your-repo-name"

database_password = "replace-me"
s3_bucket         = "your-s3-bucket"
export_s3_bucket  = "your-export-s3-bucket"

# Optional
allowed_email_domains = ""
```
You can copy the example:
```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

## 6) Provide secrets (manual + local)
Terraform expects secrets via `TF_VAR_secrets` (never commit this).

Example:
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
Helper (optional): set env vars first, then generate JSON:
```bash
export TF_VAR_secrets="$(scripts/prepare_tf_secrets.sh)"
```

## 7) Terraform init + apply
From repo root:
```bash
cd infra/terraform
terraform init -backend-config="bucket=${TF_STATE_BUCKET}"
terraform apply
```

## 8) Domain mapping (manual)
Terraform creates Cloud Run domain mappings if enabled.
Get the CNAME/TXT records and add them in Cloudflare.

```bash
gcloud run domain-mappings describe "api.${DOMAIN}" --region "$REGION"
gcloud run domain-mappings describe "app.${DOMAIN}" --region "$REGION"
```
Add the DNS records in Cloudflare and wait for verification.

## 9) OAuth redirect URIs (manual)
Update OAuth apps with production URLs:
- Google Login: `https://api.<domain>/auth/google/callback`
- Gmail: `https://api.<domain>/integrations/gmail/callback`
- Google Calendar: `https://api.<domain>/integrations/google-calendar/callback`
- Zoom: `https://api.<domain>/integrations/zoom/callback`
- Duo: `https://app.<domain>/auth/duo/callback`

## 10) Build + deploy (automatic on push)
Terraform creates Cloud Build triggers. Push to your main branch to deploy:
```bash
git push origin main
```
This builds and deploys:
- API service
- Worker job
- Web service

## 11) Run migrations (manual, on first deploy)
```bash
gcloud run jobs execute crm-migrate --region "$REGION"
```

## 12) Verify
- `https://app.<domain>` loads
- `https://api.<domain>/health` returns 200
- Log in, check core pages

## Notes for personal vs company accounts
You must repeat the full flow in the company account:
- New project
- New state bucket
- New secrets
- New Cloud Build GitHub connection
- New domain mapping DNS records

Keep separate `terraform.tfvars` and state bucket per project.
