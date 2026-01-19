# Deployment (GCP Cloud Run)

This guide deploys Surrogacy Force to GCP Cloud Run with `app.<domain>` and `api.<domain>`.
It assumes you’re using Cloud SQL (Postgres) and Memorystore (Redis).

Prefer Terraform? See `infra/terraform/README.md` for a full Cloud Build + Cloud Run setup.

## 1) Prerequisites
- GCP project created and billing enabled.
- `gcloud` CLI installed and authenticated.
- Domain managed in Cloudflare.

Set these once:
```bash
PROJECT_ID="your-project-id"
REGION="us-central1"
DOMAIN="example.com"
```

## 2) Enable APIs
```bash
gcloud config set project "$PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

## 3) Artifact Registry
```bash
gcloud artifacts repositories create crm \
  --repository-format=docker \
  --location="$REGION" \
  --description="Surrogacy Force images"
```

## 4) Cloud SQL (Postgres)
```bash
gcloud sql instances create crm-db \
  --database-version=POSTGRES_15 \
  --region="$REGION" \
  --tier=db-g1-small

gcloud sql databases create crm --instance crm-db
gcloud sql users create crm_user --instance crm-db --password 'REPLACE_ME'
```

## 5) Redis (Memorystore)
```bash
gcloud redis instances create crm-redis \
  --size=1 --region="$REGION"
```
Use the instance IP for `REDIS_URL`.

## 6) Service Accounts
```bash
gcloud iam service-accounts create crm-api-sa
gcloud iam service-accounts create crm-web-sa
gcloud iam service-accounts create crm-worker-sa

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:crm-api-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:crm-api-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:crm-worker-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:crm-worker-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## 7) Secrets (Secret Manager)
Create secrets for all production-required values:
```bash
echo -n "super-secret" | gcloud secrets create JWT_SECRET --data-file=-
echo -n "internal-secret" | gcloud secrets create INTERNAL_SECRET --data-file=-
# Repeat for GOOGLE_CLIENT_SECRET, ZOOM_CLIENT_SECRET, GMAIL_CLIENT_SECRET, etc.
```

## 8) Required Env Vars (API)
These must be set in non-dev environments:
- `ENV=production`
- `DATABASE_URL=postgresql+psycopg://crm_user:PASS@/crm?host=/cloudsql/PROJECT:REGION:crm-db`
- `API_BASE_URL=https://api.<domain>`
- `FRONTEND_URL=https://app.<domain>`
- `CORS_ORIGINS=https://app.<domain>`
- `REDIS_URL=redis://<memorystore-ip>:6379/0`
- `ATTACHMENT_SCAN_ENABLED=true`
- `STORAGE_BACKEND=s3` (Cloud Run local disk is ephemeral)
- `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Optional GCS (S3 interoperability): `S3_ENDPOINT_URL=https://storage.googleapis.com`,
  `S3_PUBLIC_BASE_URL=https://storage.googleapis.com`, `S3_URL_STYLE=path`
- `EXPORT_STORAGE_BACKEND=s3` (recommended)
- `EXPORT_S3_BUCKET`, `EXPORT_S3_REGION`
- Optional GCS export endpoint: `EXPORT_S3_ENDPOINT_URL=https://storage.googleapis.com`
- Encryption keys: `FERNET_KEY`, `DATA_ENCRYPTION_KEY`, `PII_HASH_KEY`, `META_ENCRYPTION_KEY`
- OAuth redirects:
  - `GOOGLE_REDIRECT_URI=https://api.<domain>/auth/google/callback`
  - `GMAIL_REDIRECT_URI=https://api.<domain>/integrations/gmail/callback`
  - `GOOGLE_CALENDAR_REDIRECT_URI=https://api.<domain>/integrations/google-calendar/callback`
  - `ZOOM_REDIRECT_URI=https://api.<domain>/integrations/zoom/callback`
  - `DUO_REDIRECT_URI=https://app.<domain>/auth/duo/callback`

Note on scanning: the API image does not include ClamAV binaries. If you need true AV scanning, install ClamAV in the worker image or use a scanning service. `ATTACHMENT_SCAN_ENABLED` is required to be `true` in production.

## 9) Build + Deploy API (Cloud Run)
```bash
IMAGE_API="$REGION-docker.pkg.dev/$PROJECT_ID/crm/api:$(git rev-parse --short HEAD)"
gcloud builds submit apps/api --tag "$IMAGE_API"

gcloud run deploy crm-api \
  --image "$IMAGE_API" \
  --region "$REGION" \
  --allow-unauthenticated \
  --service-account "crm-api-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --port 8000 \
  --add-cloudsql-instances "$PROJECT_ID:$REGION:crm-db" \
  --set-env-vars "ENV=production,API_BASE_URL=https://api.${DOMAIN},FRONTEND_URL=https://app.${DOMAIN},CORS_ORIGINS=https://app.${DOMAIN},REDIS_URL=redis://<memorystore-ip>:6379/0,ATTACHMENT_SCAN_ENABLED=true,STORAGE_BACKEND=s3,EXPORT_STORAGE_BACKEND=s3" \
  --set-secrets "JWT_SECRET=JWT_SECRET:latest,DEV_SECRET=DEV_SECRET:latest,INTERNAL_SECRET=INTERNAL_SECRET:latest,FERNET_KEY=FERNET_KEY:latest,DATA_ENCRYPTION_KEY=DATA_ENCRYPTION_KEY:latest,PII_HASH_KEY=PII_HASH_KEY:latest,META_ENCRYPTION_KEY=META_ENCRYPTION_KEY:latest,GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest,ZOOM_CLIENT_ID=ZOOM_CLIENT_ID:latest,ZOOM_CLIENT_SECRET=ZOOM_CLIENT_SECRET:latest,GMAIL_CLIENT_ID=GMAIL_CLIENT_ID:latest,GMAIL_CLIENT_SECRET=GMAIL_CLIENT_SECRET:latest"
```

## 10) Migrations (Cloud Run Job)
```bash
gcloud run jobs create crm-migrate \
  --image "$IMAGE_API" \
  --region "$REGION" \
  --command "alembic" --args "upgrade","head" \
  --add-cloudsql-instances "$PROJECT_ID:$REGION:crm-db" \
  --service-account "crm-worker-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --set-env-vars "ENV=production,DATABASE_URL=postgresql+psycopg://crm_user:PASS@/crm?host=/cloudsql/$PROJECT_ID:$REGION:crm-db"

gcloud run jobs execute crm-migrate --region "$REGION"
```

## 11) Worker (Cloud Run Job)
```bash
gcloud run jobs create crm-worker \
  --image "$IMAGE_API" \
  --region "$REGION" \
  --command "python" --args "-m","app.worker" \
  --add-cloudsql-instances "$PROJECT_ID:$REGION:crm-db" \
  --service-account "crm-worker-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --set-env-vars "ENV=production,DATABASE_URL=postgresql+psycopg://crm_user:PASS@/crm?host=/cloudsql/$PROJECT_ID:$REGION:crm-db,REDIS_URL=redis://<memorystore-ip>:6379/0"
```

## 12) Build + Deploy Web (Cloud Run)
```bash
IMAGE_WEB="$REGION-docker.pkg.dev/$PROJECT_ID/crm/web:$(git rev-parse --short HEAD)"

gcloud builds submit . \
  --file apps/web/Dockerfile \
  --tag "$IMAGE_WEB" \
  --build-arg NEXT_PUBLIC_API_BASE_URL="https://api.${DOMAIN}"

gcloud run deploy crm-web \
  --image "$IMAGE_WEB" \
  --region "$REGION" \
  --allow-unauthenticated \
  --service-account "crm-web-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --port 3000
```

## 13) Domain Mapping + Cloudflare
```bash
gcloud run domain-mappings create --service crm-api --domain api.${DOMAIN} --region "$REGION"
gcloud run domain-mappings create --service crm-web --domain app.${DOMAIN} --region "$REGION"
```
Add the CNAME/TXT records Cloud Run provides into Cloudflare. Set SSL to Full/Strict.

## 14) OAuth Redirect URIs
Update OAuth apps with production URLs:
- Google Login: `https://api.<domain>/auth/google/callback`
- Gmail: `https://api.<domain>/integrations/gmail/callback`
- Google Calendar: `https://api.<domain>/integrations/google-calendar/callback`
- Zoom: `https://api.<domain>/integrations/zoom/callback`

## 15) Monitoring Webhook + Log Metrics
Use `docs/monitoring-runbook.md`:
- Create log‑based metric `ws_send_failed_count` with label extractors.
- Alert policy → webhook to `https://api.<domain>/internal/alerts/gcp` with header `X-Internal-Secret`.

## 16) Post‑Deploy Checklist
- `alembic upgrade head` ran successfully.
- App loads at `https://app.<domain>`.
- API health check `https://api.<domain>/health` returns 200.
- OAuth redirects updated.
- Monitoring alerts verified.
