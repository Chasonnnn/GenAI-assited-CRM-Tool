# GCP OIDC Deploy Setup (GitHub Actions + Cloud Run)

This is a starter checklist to wire GitHub Actions to GCP using OIDC
(no long-lived keys). It matches the workflows in `.github/workflows/deploy-gcp.yml`.

## Custom Domains (Branded Redirect Portals)

Recommended structure for enterprise clients:
- `portal.clientdomain.com` → redirect service → `https://app.yourdomain.com`

Steps:
1) Domain mapping
   - Map a single redirect service to `portal.clientdomain.com`.
2) DNS
   - Create a CNAME record for `portal` pointing to the redirect service target hostname.
   - For Wix-managed domains, use subdomain CNAMEs (avoid apex CNAMEs).
3) Keep env vars on the primary domains
   - Backend:
     - `FRONTEND_URL=https://app.yourdomain.com`
     - `CORS_ORIGINS=https://app.yourdomain.com`
     - `API_BASE_URL=https://api.yourdomain.com`
   - Frontend:
     - `NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com`
4) Set org portal domain in the app
   - Settings → Organization → Portal Domain: `portal.clientdomain.com`

Note: A hosted per-client portal (same-site cookies on the client domain)
requires a shared host for UI + API or per-client cookie domain changes.
The redirect approach avoids cross-site cookie issues.

## 1) Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com
```

## 2) Create an Artifact Registry repo

```bash
gcloud artifacts repositories create crm-api \
  --repository-format=docker \
  --location=us-central1 \
  --description="CRM API images"
```

## 3) Create a GitHub Actions deployer service account

```bash
gcloud iam service-accounts create gh-actions-deployer \
  --display-name="GitHub Actions Deployer"
```

Grant roles to the deployer (this account builds, pushes, and deploys):

```bash
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:gh-actions-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:gh-actions-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:gh-actions-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

## 4) Create the Workload Identity Pool and Provider

Replace `GITHUB_ORG` and `GITHUB_REPO` with your repo values.

```bash
gcloud iam workload-identity-pools create "github-pool" \
  --project="$GCP_PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="$GCP_PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Actions Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="attribute.repository == 'GITHUB_ORG/GITHUB_REPO'"
```

Bind the GitHub principal to the deployer service account:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  "gh-actions-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$GCP_PROJECT_ID/locations/global/workloadIdentityPools/github-pool/attribute.repository/GITHUB_ORG/GITHUB_REPO"
```

## 5) Create a runtime service account (for Cloud Run)

The runtime account reads secrets at runtime.

```bash
gcloud iam service-accounts create crm-api-runtime \
  --display-name="CRM API Runtime"
```

Grant secret access to the runtime account (tighter than project-wide):

```bash
gcloud secrets add-iam-policy-binding DATABASE_URL \
  --member="serviceAccount:crm-api-runtime@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

If using Cloud SQL, also grant:

```bash
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:crm-api-runtime@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

## 6) Create Secret Manager secrets

```bash
gcloud secrets create DATABASE_URL --replication-policy="automatic"
printf "%s" "postgresql+psycopg://user:pass@/db?host=/cloudsql/PROJECT:REGION:INSTANCE" | \
  gcloud secrets versions add DATABASE_URL --data-file=-
```

## 7) Set GitHub Secrets

Add the following in GitHub → Settings → Secrets and variables → Actions:

- `GCP_PROJECT_ID`
- `GCP_REGION` (example: `us-central1`)
- `GCP_ARTIFACT_REPOSITORY` (example: `crm-api`)
- `GCP_CLOUD_RUN_SERVICE` (example: `crm-api`)
- `GCP_CLOUD_RUN_JOB` (example: `crm-api-migrate`)
- `GCP_DATABASE_URL_SECRET` (example: `DATABASE_URL`)
- `GCP_WORKLOAD_IDENTITY_PROVIDER` (full provider resource name)
- `GCP_SERVICE_ACCOUNT_EMAIL` (deployer service account email)

## 8) Optional: set the runtime service account on deploy

If you want to use `crm-api-runtime`, add this flag to the deploy step:

```bash
--service-account "crm-api-runtime@$GCP_PROJECT_ID.iam.gserviceaccount.com"
```
