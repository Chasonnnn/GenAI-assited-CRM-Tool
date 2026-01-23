# GCP Deploy Setup (Cloud Build Triggers + Cloud Run)

We deploy via **GCP Cloud Build triggers** (2nd gen repo connections) that build Docker images and
update Cloud Run services/jobs.

GitHub Actions OIDC deploy (and `.github/workflows/deploy-gcp.yml`) has been removed to avoid
having two competing deploy paths.

For the canonical setup, follow:
- `infra/terraform/README.md` (Terraform-provisioned Cloud Build triggers, Cloud Run, Cloud SQL, etc.)

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

## Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com
```

## Cloud Build Repo Connection (2nd gen)

In the GCP Console:
- Cloud Build -> Repositories -> Create host connection (GitHub)
- Link the repo to the connection
- Ensure the connection + repository are in the same region as Terraform `cloudbuild_location`

Then set these Terraform variables:
- `cloudbuild_location` (e.g. `us-central1`)
- `cloudbuild_repository` (resource name shown in Cloud Build)

Example `cloudbuild_repository` format:
`projects/PROJECT_ID/locations/REGION/connections/CONNECTION/repositories/REPO`

## Notes

- Terraform creates Secret Manager **secrets** (containers) only; add secret **versions** out-of-band.
- Deploy is driven by Cloud Build triggers; see:
  - `cloudbuild/api.yaml` (build + deploy API + worker)
  - `cloudbuild/web.yaml` (build + deploy web)
