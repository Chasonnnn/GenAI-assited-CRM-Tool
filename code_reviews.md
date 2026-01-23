# Code Reviews (End-to-End)

Date: 2026-01-23  
Repo: Surrogacy Force Platform (`GenAI-assited-CRM-Tool`)

## Scope & Method

- Read all **git-tracked** files in the repository (`git ls-files`): **833 files** / **208,984 text lines** (+ **13 binary assets**).
- Excluded from “read every file” scope: **untracked/ignored dependency and build dirs** (e.g., `apps/web/node_modules/`, `.venv/`, local `.env`), because they are not part of your maintainable codebase and can be machine-specific.
- Cross-referenced existing audits and roadmaps: `ENTERPRISE_GAPS.md`, `LAUNCH_READINESS.md`, `REVIEW.md`, `database_optimization.md`.

> Note: `ENTERPRISE_GAPS.md` already captures SSO/SCIM, ABAC posture, audit read-access, retention/DSAR, observability, backups/DR, integration idempotency, and job processing roadmap items. I do **not** repeat those here except when a finding intersects them.

---

## Executive Summary (Fix Order for Launch)

### Launch blockers (fix before onboarding the first agency)

1) ✅ **Team invite onboarding is broken end-to-end** (backend + frontend) — **RESOLVED 2026-01-23**  
2) ✅ **Campaigns API response references a non-existent `User.full_name`** (runtime error) — **RESOLVED 2026-01-23**  
3) ✅ **Attachment “virus scanning” can silently fail open (mark clean) if ClamAV is missing** — **RESOLVED 2026-01-23**  
4) ✅ **Stored/preview HTML rendering risks (email templates + search snippets) → potential stored XSS** — **RESOLVED 2026-01-23**  
5) ✅ **Repo contains tracked build/artifact binaries (`infra/terraform/tfplan`, `apps/web/node-compile-cache/...`)** — **RESOLVED 2026-01-23**
6) ✅ **Protobuf CVE-2026-0994 (ParseDict Any recursion bypass) flagged by audit** — **MITIGATED 2026-01-23**

### High-value architecture hardening (not in `ENTERPRISE_GAPS.md`)

- **Async FastAPI endpoints + sync SQLAlchemy** (blocking the event loop) → reliability/perf risk under concurrent use (WebSockets + long responses).
- **DB-level tenant integrity**: composite FKs (org_id, entity_id) to prevent cross-org references even if application bugs slip in.

---

## Findings (Ranked)

### Critical

#### C1) Team invite onboarding is broken (backend + frontend)

**Status:** ✅ Resolved on 2026-01-23

- Evidence (backend):
  - Inviter name uses `User.full_name` but `User` model has `display_name` (no `full_name` field):
    - `apps/api/app/services/invite_email_service.py:123`
    - `apps/api/app/services/invite_service.py:214`
  - Invite accept flow sets `user.active_org_id` (field does not exist on `User` model):
    - `apps/api/app/services/invite_service.py:266-267`
- Evidence (frontend):
  - Invite page calls API endpoints that are likely unusable without a session/CSRF:
    - `apps/web/app/invite/[id]/page.tsx:36` (GET `/settings/invites/accept/{id}`)
    - `apps/web/app/invite/[id]/page.tsx:55` (POST `/settings/invites/accept/{id}`)
  - Invite page “Sign in” uses a non-existent route:
    - `apps/web/app/invite/[id]/page.tsx:70` (`/api/auth/google?...`) — only the login page uses `${NEXT_PUBLIC_API_BASE_URL}/auth/google/login`.
- Impact:
  - You can’t reliably invite and onboard additional staff (your “20 users” target) via the product.
  - Invite emails may never send successfully (exception inside `send_invite_email`), and invite pages may 500.
- Recommendation (one clear direction):
  - **Make invite acceptance happen via Google login (already implemented in `apps/api/app/services/auth_service.py`)**:
    - Frontend `/invite/[id]`: remove “Accept Invitation” mutation; show invite details + “Continue with Google” button that redirects to `${NEXT_PUBLIC_API_BASE_URL}/auth/google/login?login_hint=<invite.email>&return_to=app`.
    - Backend: keep only `GET /settings/invites/accept/{id}` as a *public details* endpoint (or move to a `/public/invites/{id}` path) and fix inviter name to `display_name`.
  - Add tests:
    - Backend: invite creation + invite email send path (mock Gmail) should not crash.
    - Frontend: invite page renders and redirects to backend login URL.

#### C2) Tracked Terraform plan file in git

**Status:** ✅ Resolved on 2026-01-23

- Evidence:
  - `infra/terraform/tfplan` is committed (binary, machine-generated).
- Impact:
  - Repo hygiene and potential leakage risk (plans can contain sensitive values depending on workflow).
  - Causes needless churn and platform-specific diffs.
- Recommendation:
  - Remove `infra/terraform/tfplan` from git history and add `infra/terraform/tfplan` to `.gitignore`.

#### C3) Attachment “virus scanning” can fail open when scanner is missing

**Status:** ✅ Resolved on 2026-01-23 (fail-closed in non-dev + worker preflight check)

- Evidence:
  - `apps/api/app/jobs/scan_attachment.py:71-80` treats ClamAV errors / missing scanner as “clean” (`scan_error`, `scanner_not_available`).
- Impact:
  - In production, if the worker image doesn’t actually include ClamAV (or daemon isn’t reachable), attachments can be marked clean and released without being scanned.
  - This undermines the “Upload safety” gate in `LAUNCH_READINESS.md`.
- Recommendation:
  - Add an explicit **fail-closed** mode for non-dev:
    - If scanning is enabled and scanner is unavailable/error/timeout → keep `quarantined=True` and set `scan_status='error'` (or `'blocked'`) + create a `SystemAlert`.
  - Add a startup self-check for the worker: verify `clamdscan`/`clamscan` availability when `ATTACHMENT_SCAN_ENABLED=true` and `ENV!=dev`.

#### C4) Protobuf CVE-2026-0994 (ParseDict Any recursion bypass)

**Status:** ✅ Mitigated on 2026-01-23 (runtime depth guard + audit ignore until upstream release)

- Evidence:
  - Dependency audit flags `protobuf==6.33.4` as vulnerable (CVE-2026-0994).
- Impact:
  - Potential DoS if untrusted JSON is parsed via `google.protobuf.json_format.ParseDict` on nested `Any` payloads.
- Mitigation implemented:
  - Runtime depth guard applied before JSON parse to enforce max recursion depth.
  - Audit ignore added with the guard in place until upstream releases a patched protobuf version.

### High

#### H1) Campaigns API likely crashes due to `User.full_name`

**Status:** ✅ Resolved on 2026-01-23

- Evidence:
  - `apps/api/app/routers/campaigns.py:367` references `campaign.created_by.full_name`, but `User` model does not have `full_name`.
- Impact:
  - Campaign list/detail responses can 500 when `created_by` is present (email campaigns are a key feature).
- Recommendation:
  - Replace with `campaign.created_by.display_name` (or introduce a `full_name` alias property on `User` if you want that naming consistently).
  - Add test coverage for campaigns list serialization (at least one campaign with `created_by_user_id` set).

#### H2) Stored XSS risk: email template preview renders raw HTML

**Status:** ✅ Resolved on 2026-01-23 (server-side sanitization + client preview sanitize)

- Evidence:
  - `apps/web/app/(app)/automation/email-templates/page.tsx:972` renders `previewHtml` via `dangerouslySetInnerHTML`.
  - Backend stores `EmailTemplate.body` without sanitization: `apps/api/app/services/email_service.py` (template CRUD).
- Impact:
  - A malicious/compromised admin account could store HTML that executes in other users’ browsers (session theft / cross-user stored XSS inside the org).
- Recommendation:
  - Sanitize at render-time (client) **and/or** at write-time (server):
    - Client: apply `sanitizeHtml()` before setting `previewHtml` and anywhere templates are previewed.
    - Server: sanitize/validate `EmailTemplate.body` to forbid scripts/event handlers at minimum.
  - Consider sandboxing template previews in an `<iframe sandbox>` for defense-in-depth.

### Medium

#### M1) Search results snippet is treated as HTML in the UI

**Status:** ✅ Resolved on 2026-01-23 (client-side sanitize for snippets)

- Evidence:
  - `apps/web/app/(app)/search/page.tsx:179-182` renders `result.snippet` as HTML.
  - Backend builds snippets using `ts_headline` and returns them as-is (`apps/api/app/services/search_service.py`).
- Impact:
  - If any indexed text contains HTML-like content (intentionally or via bad input), it could become an XSS vector.
- Recommendation:
  - Prefer returning **plain text + highlight ranges** (or escape then wrap highlights) rather than raw HTML.
  - If you keep HTML snippets: sanitize before rendering.

#### M2) Workflow engine entity loading is not org-scoped (defense-in-depth gap)

- Evidence:
  - `apps/api/app/services/workflow_engine.py:805-819` loads entities by `id` only (no `organization_id` filter).
- Impact:
  - If a caller bug ever triggers workflows with an `entity_id` from another org, the engine can read/mutate cross-org data (and even create cross-org FK links).
- Recommendation:
  - Require `org_id` in `_get_entity(...)` and enforce org scoping for all org-owned entities.
  - Add a hard assertion: `entity.organization_id == workflow.organization_id` before executing actions.

#### M3) FastAPI has many `async def` endpoints while DB access is synchronous

- Evidence:
  - DB is sync SQLAlchemy (`apps/api/app/db/session.py`), but routers include many `async def` endpoints (example: `apps/api/app/routers/invites.py`).
- Impact:
  - Blocking DB/network work inside `async def` will block the event loop (hurts concurrency; can starve WebSockets and increase tail latency).
- Recommendation:
  - Pick one:
    1) Convert endpoints that touch DB to `def` (sync) so FastAPI runs them in a threadpool, OR
    2) Migrate to SQLAlchemy AsyncEngine/AsyncSession and make DB operations truly async.

### Low

#### L1) Missing `X-Requested-With` header in the web API client (docs drift)

- Evidence:
  - `apps/web/lib/api.ts:31-40` does not set `X-Requested-With`.
  - Repo guidelines/docs reference always sending it (e.g., `agents.md` examples; load tests also send it).
- Impact:
  - Not a functional bug today (CSRF is double-submit), but docs and tooling drift increases future security risk.
- Recommendation:
  - Either (a) add the header globally in `apps/web/lib/api.ts`, or (b) remove the requirement from docs/tests if it’s not actually needed.

#### L2) Reverse tabnabbing hardening is inconsistent

- Evidence:
  - Some `window.open(..., "_blank")` calls omit `"noopener,noreferrer"` (e.g., `apps/web/components/surrogates/LatestUpdatesCard.tsx:46`).
- Impact:
  - Low-probability but easy-to-fix security hardening issue; will show up in ZAP findings.
- Recommendation:
  - Standardize `window.open(url, "_blank", "noopener,noreferrer")` everywhere.

#### L3) Cloud Build configs deploy `:latest` images

- Evidence:
  - `cloudbuild/api.yaml` and `cloudbuild/web.yaml` use `...:latest`.
- Impact:
  - Makes deployments less traceable/rollbackable; “what’s running” is harder to answer.
- Recommendation:
  - Tag images with commit SHA and keep `latest` only as an optional moving tag.

---

## Enterprise-Level Improvements (Not in `ENTERPRISE_GAPS.md`)

1) **DB tenant integrity without full RLS**  
   - Add composite unique keys and composite foreign keys like `(organization_id, id)` to prevent cross-org references (tasks → surrogates, notes → entities, attachments → surrogates, etc.).
   - This complements your app-layer org scoping and reduces blast radius of any bug.

2) **HTML safety policy**  
   - Create a single “HTML content contract”: what sources are allowed to contain HTML (notes, transcripts, templates, signatures), and how each is sanitized (server vs client).
   - Enforce via shared utilities and tests; ban raw `dangerouslySetInnerHTML` except behind a sanitizer wrapper component.

3) **Git hygiene gates**  
   - Add CI checks to prevent committing build artifacts (e.g., `tfplan`, node compile caches).
   - Consider a pre-commit hook or CI `git diff --name-only` denylist.

4) **“Prod feature self-checks” on startup**  
   - When `ENV!=dev`, verify critical integrations are actually functional (e.g., attachment scanning availability when enabled, Redis when rate limiting requires it).

---

## Immediate Pre-Launch Checklist (Beyond Code)

- Execute and record the items in `LAUNCH_READINESS.md` (ZAP baseline run, migration idempotency log, restore test log, monitoring/alert routing verification).
- Add/extend automated tests for:
  - Invite onboarding (happy path + expired/revoked invite).
  - Campaign list serialization (created_by present).
  - Email template preview sanitization (no script execution).
