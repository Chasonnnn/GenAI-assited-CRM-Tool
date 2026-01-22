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
export PROJECT_ID="surrogacy-force-test-deploy"
export REGION="us-central1"
export DOMAIN="surrogacyforce.com"
```

Confirm gcloud is using your project:
```bash
gcloud config set project "$PROJECT_ID"
```

## 2) Enable required APIs
Terraform enables required APIs (Cloud Run, Cloud SQL, Secret Manager, Artifact Registry,
Cloud Build, Logging/Monitoring, IAM, Compute, Service Networking, VPC Access, Redis).
Ensure your Terraform credentials can enable services.

## 2.1) Authenticate for Terraform (ADC)
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project "$PROJECT_ID"
```

## 3) Create a Terraform state bucket (one-time)
Terraform needs a GCS bucket to store state.
```bash
export TF_STATE_BUCKET="${PROJECT_ID}-tfstate"
gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
  --project "$PROJECT_ID" \
  --location "US" \
  --uniform-bucket-level-access \
  --public-access-prevention
```
Or use the helper script:
```bash
scripts/bootstrap_tf_state_bucket.sh "$PROJECT_ID" "$TF_STATE_BUCKET" "US" [KMS_KEY]
```

## 4) Connect GitHub to Cloud Build (manual)
In the GCP Console:
1. Go to Cloud Build -> Repositories.
2. Create a host connection (GitHub) in your region.
3. Link your repo to that connection.
4. Ensure the connection + linked repo live in the same region as `region` (e.g. us-central1).

Get the repository resource name:
```bash
gcloud beta builds repositories list \
  --connection=YOUR_CONNECTION \
  --region=us-central1 \
  --format="value(name)"
```

## 5) Create `terraform.tfvars` (do not commit)
Create `infra/terraform/terraform.tfvars` with your values:
```hcl
project_id        = "surrogacy-force-test-deploy"
region            = "us-central1"
domain            = "surrogacyforce.com"
github_owner      = "Chasonnnn"
github_repo       = "GenAI-assited-CRM-Tool"
cloudbuild_repository = "projects/PROJECT/locations/REGION/connections/CONNECTION/repositories/REPO"

s3_bucket         = "your-s3-bucket"
export_s3_bucket  = "your-export-s3-bucket"

# Optional
allowed_email_domains = ""
secret_replication_location = "us-central1"
logging_retention_days = 90
enable_cloudbuild_triggers = true
enable_public_invoker = true
enable_domain_mapping = true

# Monitoring + budgets (recommended)
alert_notification_channel_ids = ["projects/PROJECT_ID/notificationChannels/CHANNEL_ID"]
billing_account_id = "000000-000000-000000"
billing_budget_amount_usd = 300
billing_budget_thresholds = [0.5, 0.75, 0.9, 1.0]

# Weekly billing summary (optional)
billing_weekly_summary_enabled = true
billing_export_dataset = "billing_export"
billing_export_dataset_location = "US"
billing_weekly_summary_cron = "0 13 * * 1"
billing_weekly_summary_timezone = "Etc/UTC"

# Private Service Access (optional override)
# private_service_access_address = "10.10.0.0"
# private_service_access_prefix_length = 16

# Database user management (optional)
# manage_database_user = true
# database_password = "replace-me"
```
You can copy the example:
```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

## 6) Provide secrets (manual or CI)
Terraform creates Secret Manager containers only. Add secret versions out-of-band:
```bash
gcloud secrets versions add JWT_SECRET --data-file=- <<<"your-secret"
gcloud secrets versions add DATABASE_URL --data-file=- <<<"postgresql+psycopg://crm_user:<password>@/crm?host=/cloudsql/<connection_name>"
gcloud secrets versions add REDIS_URL --data-file=- <<<"redis://:<redis-auth>@<redis-host>:6379/0"
gcloud secrets versions add BILLING_SLACK_WEBHOOK_URL --data-file=- <<<"https://hooks.slack.com/services/..."
```

Database user/password are managed outside Terraform to keep secrets out of state.
Create the user and set the password manually (or via a secure job).

If your org policy blocks global secrets, set `secret_replication_location` to an allowed region
(for example `us-central1`).

Cloud SQL uses private IP only; Terraform creates the Private Service Access range + connection.
Override `private_service_access_address`/`private_service_access_prefix_length` if needed.

## 6.0) Monitoring + budgets
Terraform creates alert policies for Cloud SQL CPU/memory/disk, Redis memory usage, and Cloud Run 5xx spikes.
Create the Slack notification channel out-of-band and pass its ID via `alert_notification_channel_ids`
so the webhook never enters Terraform state.

Budget alerts use the same channel. Set `billing_account_id` and `billing_budget_amount_usd`.

## 6.0.1) Weekly spend summary (optional)
Terraform creates a BigQuery dataset and a Cloud Run job that posts weekly spend to Slack.
Enable Cloud Billing export to BigQuery (manual):
1. Cloud Billing -> Billing export -> BigQuery export.
2. Select dataset `billing_export` (or your configured `billing_export_dataset`).
3. Wait for `gcp_billing_export_v1_<billing_account>` to appear before the first run.

Enable Redis AUTH out-of-band to avoid storing auth strings in Terraform state:
```bash
gcloud redis instances update crm-redis --region us-central1 --enable-auth
```

Fetch the auth string and host:
```bash
gcloud redis instances describe crm-redis --region us-central1 --format="value(authString)"
terraform -chdir=infra/terraform output -raw redis_host
```

If Terraform refreshes the Redis instance after AUTH is enabled, the provider will record the auth
string in state. To keep state clean, avoid refresh/apply against the Redis resource after enabling
AUTH, or remove the Redis resource from state once it is created.
If auth strings have already been captured, treat the Terraform state as sensitive and rotate
the Redis auth string.

Safer sequence:
1) `terraform apply` (creates Redis with AUTH disabled).
2) `gcloud redis instances update ... --enable-auth`.
3) `gcloud redis instances describe ...` + `gcloud secrets versions add REDIS_URL ...`.
4) Deploy Cloud Run services to pick up the secret.

## 6.1) GCS instead of AWS S3 (optional)
If you want full GCP storage, use GCS with S3 interoperability.

Manual steps:
1. Create two GCS buckets (attachments + exports).
2. Enable HMAC keys: Cloud Storage -> Settings -> Interoperability -> Create key.
3. Use the HMAC Access Key + Secret as `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.

Command shortcut:
```bash
gcloud storage hmac create SERVICE_ACCOUNT_EMAIL --project "$PROJECT_ID"
```

Add these optional fields to `terraform.tfvars`:
```hcl
s3_bucket             = "your-gcs-attachments-bucket"
export_s3_bucket      = "your-gcs-exports-bucket"
s3_endpoint_url       = "https://storage.googleapis.com"
s3_public_base_url    = "https://storage.googleapis.com"
s3_url_style          = "path"
export_s3_endpoint_url = "https://storage.googleapis.com"
```

## 6.2) Storage hardening (recommended for HIPAA)
If you want Terraform to enforce private buckets and IAM:
```hcl
manage_storage_buckets = true
storage_bucket_location = "us-central1"
storage_service_account_email = "crm-storage-sa@your-project-id.iam.gserviceaccount.com"
```
If buckets already exist, import them before apply:
```bash
cd infra/terraform
terraform import 'google_storage_bucket.attachments[0]' surrogacyforce-attachments-test
terraform import 'google_storage_bucket.exports[0]' surrogacyforce-exports-test
```
## 7) Terraform init + apply
From repo root:
```bash
cd infra/terraform
terraform init -backend-config="bucket=${TF_STATE_BUCKET}"
terraform apply
```
If you see backend/credentials errors, rerun:
```bash
terraform init -reconfigure -backend-config="bucket=${TF_STATE_BUCKET}"
```

## 8) Domain mapping (manual)
Terraform creates Cloud Run domain mappings if enabled.
Get the CNAME/TXT records and add them in Cloudflare.

```bash
gcloud run domain-mappings describe "api.${DOMAIN}" --region "$REGION"
gcloud run domain-mappings describe "app.${DOMAIN}" --region "$REGION"
```
Add the DNS records in Cloudflare and wait for verification.

If your org policy blocks public invokers, set:
```hcl
enable_public_invoker = false
```

If domain mapping fails due to verification, set:
```hcl
enable_domain_mapping = false
```
Then verify ownership in Google Search Console and re-enable.
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

## HIPAA readiness (infra-level)
Terraform now enables:
- Cloud SQL backups + PITR
- Audit logs for GCS + Cloud SQL
- GCS bucket hardening (if managed via Terraform)

## Notes for personal vs company accounts
You must repeat the full flow in the company account:
- New project
- New state bucket
- New secrets
- New Cloud Build GitHub connection
- New domain mapping DNS records

Keep separate `terraform.tfvars` and state bucket per project.
