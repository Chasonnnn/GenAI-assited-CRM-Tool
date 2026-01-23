# Terraform (GCP + Cloud Build)

This folder provisions infrastructure for Cloud Run + Cloud Build with remote state.
Secret values are added out-of-band (never commit them).

## 1) One-time bootstrap

Create a GCS bucket for Terraform state (global unique name):
```bash
gcloud storage buckets create gs://YOUR_STATE_BUCKET \
  --project YOUR_PROJECT_ID \
  --location US \
  --uniform-bucket-level-access \
  --public-access-prevention
```
Helper:
```bash
scripts/bootstrap_tf_state_bucket.sh YOUR_PROJECT_ID YOUR_STATE_BUCKET US [KMS_KEY]
```

Terraform enables required APIs (Cloud Run, Cloud SQL, Secret Manager, Artifact Registry,
Cloud Build, Logging/Monitoring, IAM, Compute, Service Networking, VPC Access, Redis).
Ensure your Terraform credentials can enable services.

Authenticate for Terraform (ADC):
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Connect GitHub to Cloud Build (Console, 2nd gen):
- Cloud Build -> Repositories -> Create host connection
- Link the repo to that connection
- Make sure the connection and linked repo are in the same region as `var.region` (e.g. us-central1).

Get the repository resource name:
```bash
gcloud beta builds repositories list \
  --connection=YOUR_CONNECTION \
  --region=us-central1 \
  --format="value(name)"
```

## 2) Configure variables

Create `terraform.tfvars` (do not commit):
```hcl
project_id         = "your-project-id"
region             = "us-central1"
domain             = "example.com"
github_owner       = "your-org"
github_repo        = "your-repo"
cloudbuild_repository = "projects/PROJECT/locations/REGION/connections/CONNECTION/repositories/REPO"

s3_bucket          = "..."
export_s3_bucket   = "..."

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
```
You can copy the example:
```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Terraform only creates Secret Manager containers. Add secret versions out-of-band (manual or CI):
```bash
gcloud secrets versions add JWT_SECRET --data-file=- <<<"your-secret"
gcloud secrets versions add DATABASE_URL --data-file=- <<<"postgresql+psycopg://crm_user:<password>@/crm?host=/cloudsql/<connection_name>"
gcloud secrets versions add REDIS_URL --data-file=- <<<"redis://:<redis-auth>@<redis-host>:6379/0"
gcloud secrets versions add BILLING_SLACK_WEBHOOK_URL --data-file=- <<<"https://hooks.slack.com/services/..."
```

Redis AUTH is enabled out-of-band to avoid storing auth strings in Terraform state:
```bash
gcloud redis instances update crm-redis --region us-central1 --enable-auth
```

Fetch the auth string and host, then write REDIS_URL directly to Secret Manager:
```bash
gcloud redis instances describe crm-redis --region us-central1 --format="value(authString)"
terraform -chdir=infra/terraform output -raw redis_host
```

If Terraform refreshes the Redis instance after AUTH is enabled, the provider will record the auth
string in state. To keep state clean, avoid refresh/apply against the Redis resource after enabling
AUTH, or remove the Redis resource from state once it is created.
If auth strings have already been captured, treat the Terraform state as sensitive and rotate
the Redis auth string.

Safe sequence:
1) `terraform apply` (creates Redis with AUTH disabled).
2) `gcloud redis instances update ... --enable-auth`.
3) `gcloud redis instances describe ...` + `gcloud secrets versions add REDIS_URL ...`.
4) Deploy Cloud Run services to pick up the secret.

Database user/password are managed outside Terraform to keep secrets out of state.
Create the user and set the password manually (or via a secure job).

If your org policy blocks global secrets, set `secret_replication_location` to an allowed region
(for example `us-central1`).

Cloud SQL is private IP only; Terraform creates the Private Service Access range and connection.
Set `private_service_access_address`/`private_service_access_prefix_length` if you need a specific range.

## Monitoring + budget alerts
Terraform creates alert policies for Cloud SQL CPU/memory/disk, Redis memory usage, and Cloud Run 5xx spikes.
Provide a Monitoring notification channel ID (Slack/email) via `alert_notification_channel_ids`.
Create the Slack notification channel out-of-band so webhooks never enter Terraform state.

Budget alerts use the same channel. Set `billing_account_id` and `billing_budget_amount_usd`.

## Weekly spend summary (optional)
Terraform provisions a BigQuery dataset and a Cloud Run job that posts a weekly spend summary to Slack.
Set the `BILLING_SLACK_WEBHOOK_URL` secret out-of-band and enable Cloud Billing export to BigQuery:
1. Cloud Billing -> Billing export -> BigQuery export.
2. Select the dataset `billing_export` (or your configured `billing_export_dataset`).
3. Wait for `gcp_billing_export_v1_<billing_account>` table to appear.

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
