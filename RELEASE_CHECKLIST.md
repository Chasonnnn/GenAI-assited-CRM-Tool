# Release Checklist (Detailed)

Use this checklist before any production deployment. It is intentionally verbose to serve as a reference.

## 0) Prep
- Confirm you're on the intended branch (usually `main`) and have the latest changes.
- Confirm local environment matches the target environment assumptions (prod settings in `infra/terraform/terraform.tfvars`).
- Confirm no unexpected untracked or modified files beyond the intended changes.

## 1) Backend Quality Gates

### 1.1 Lint + format
```
cd apps/api
ruff check .
ruff format .
```

### 1.2 Tests
```
cd apps/api
uv run -m pytest -v
```

### 1.3 Migrations
- Ensure there are no pending migrations at deploy time:
```
cd apps/api
uv run -m alembic upgrade head
```
- If `db_migration_check=true`, the API will fail readiness if migrations are pending.

## 2) Frontend Quality Gates

### 2.1 Lint + typecheck
```
cd apps/web
pnpm lint
pnpm tsc --noEmit
```

### 2.2 Tests
```
cd apps/web
pnpm test --run
```

### 2.3 Local smoke run (optional)
```
cd apps/web
pnpm dev
```

## 3) Infra Readiness (Terraform)

### 3.1 Terraform state clean
```
cd infra/terraform
terraform fmt
terraform plan
```
- Resolve any state locks (never use `-lock=false` for apply).

### 3.2 Load balancer enabled (wildcard subdomains)
- Make sure these are set in `infra/terraform/terraform.tfvars`:
```
enable_load_balancer  = true
enable_domain_mapping = false
```

### 3.3 Certificate Manager API enabled
```
gcloud services enable certificatemanager.googleapis.com --project probable-dream-484923-n7
```

### 3.4 Apply Terraform
```
cd infra/terraform
terraform apply
```

### 3.5 DNS Authorization (Certificate Manager)
- After apply, create the DNS authorization record:
```
terraform output lb_dns_authorization_root
```
- Add the returned CNAME in Cloudflare.

### 3.6 DNS A records for load balancer
```
terraform output load_balancer_ip
```
- Create **DNS-only** A records in Cloudflare pointing to the LB IP:
  - `@`
  - `*`
  - `api`
  - `ops`
  - `app`

### 3.7 Cert status check
```
gcloud certificate-manager certificates describe crm-wildcard-cert \
  --location=global \
  --project probable-dream-484923-n7
```
- Must show `state: ACTIVE`.

## 4) Required Runtime Config (Cloud Run)

### 4.1 API service env
```
gcloud run services describe crm-api \
  --region us-central1 \
  --project probable-dream-484923-n7 \
  --format="value(spec.template.spec.containers[0].env)"
```
Confirm at least:
- `PLATFORM_BASE_DOMAIN=surrogacyforce.com`
- `COOKIE_DOMAIN=.surrogacyforce.com`
- `FRONTEND_URL=https://app.surrogacyforce.com`
- `OPS_FRONTEND_URL=https://ops.surrogacyforce.com`
- `API_BASE_URL=https://api.surrogacyforce.com`

### 4.2 Web service env
```
gcloud run services describe crm-web \
  --region us-central1 \
  --project probable-dream-484923-n7 \
  --format="value(spec.template.spec.containers[0].env)"
```
Confirm at least:
- `PLATFORM_BASE_DOMAIN=surrogacyforce.com`
- `NEXT_PUBLIC_API_BASE_URL=https://api.surrogacyforce.com`

## 5) DNS Verification (Authoritative)

```
dig CNAME _acme-challenge.surrogacyforce.com @lila.ns.cloudflare.com
dig CNAME _acme-challenge.surrogacyforce.com @nico.ns.cloudflare.com
```
Must return:
```
af541437-36c0-4828-8832-27eea92d6ebe.10.authorize.certificatemanager.goog.
```

## 6) Critical App Flow Checks (Manual)

### 6.1 Ops
- `https://ops.surrogacyforce.com` loads
- Login → Google auth → MFA/Duo → lands on `/ops`
- Create agency works
- Org creation logs/audits appear

### 6.2 Org (tenant subdomain)
- Visit `https://<slug>.surrogacyforce.com`
- Login → Google auth → MFA/Duo → lands on `/dashboard`
- `/auth/me` returns 200
- No redirect loop to `/login`

### 6.3 Invite link
- `https://<slug>.surrogacyforce.com/invite/<uuid>` loads
- Invite acceptance flow works

### 6.4 API health
- `https://api.surrogacyforce.com/health/live` returns 200

## 7) Security Checks
- Host validation enforced (wrong subdomain => 403)
- CORS allows tenant origins (if using CORS path)
- CSRF enforced on mutations
- No mixed content warnings in browser console

## 8) Monitoring & Logs (Post‑Deploy)
- Check Cloud Run logs for `403`, `500`, or `CORS` errors.
- Monitor error rate and latency on `crm-api` and `crm-web`.
- Confirm no spike in `Session invalid for this domain`.

## 9) Go / No-Go Criteria
Go only if all are true:
- All tests & lint pass
- Terraform apply clean
- Certificate **ACTIVE**
- DNS A records resolve to LB IP
- Ops + tenant login flows succeed
- Invite links resolve
- API health OK

## 10) Rollback Plan

### Option A: Roll back Cloud Run revisions
```
gcloud run services update-traffic crm-api \
  --region us-central1 \
  --project probable-dream-484923-n7 \
  --to-revisions <previous-revision>=100
```
Repeat for `crm-web`.

### Option B: Disable LB path and restore Cloud Run domain mapping
- Set in `terraform.tfvars`:
```
enable_load_balancer  = false
enable_domain_mapping = true
```
- Apply Terraform and restore `api/app/ops` CNAMEs to `ghs.googlehosted.com`.

## 11) Future Hardening (Optional)
- Move API to same-origin `/api` proxy (removes CORS).
- Switch to host-only cookies for strongest tenant isolation.
