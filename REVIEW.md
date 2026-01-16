# REVIEW

Date: 2026-01-15
Scope: Full repository read (all files) + targeted audit of auth/session, routers, services, public endpoints, integrations, frontend auth/data access.

## Findings (Ranked)

### Critical

- None observed.

### High

- None observed.

### Medium

#### 1) Tracking click endpoint is an open redirect
- Severity: Medium
- Category: Security
- Evidence: `apps/api/app/routers/tracking.py:126-166` accepts arbitrary `url` query param; `apps/api/app/services/tracking_service.py:168-211` returns the decoded URL.
- Impact: Attackers can turn your domain into an open redirect for phishing, reducing deliverability and reputation.
- Fix recommendation (exact steps):
  1) Store original URLs server-side at send time (per recipient + link id).
  2) Replace `url` query param with `link_id` and look up the URL from the DB.
  3) Reject if no link matches the token.

#### 2) Session creation logs raw IP addresses
- Severity: Medium
- Category: Security
- Evidence: `apps/api/app/services/session_service.py:113-118` logs `ip_address` in clear text.
- Impact: Violates “Never log raw PII” policy and creates privacy risk in logs.
- Fix recommendation (exact steps):
  1) Replace the IP in logs with a hash or a masked form (e.g., `x.x.x.0/24`).
  2) Keep raw IP in DB if required for security, but exclude it from logs.

#### 3) Transcription error logging includes raw response body
- Severity: Medium
- Category: Security
- Evidence: `apps/api/app/services/transcription_service.py:135-136` logs `e.response.text` and re-raises with full text.
- Impact: Provider error bodies can include sensitive data (PII/PHI); the error text may be exposed in logs or API responses.
- Fix recommendation (exact steps):
  1) Log only status code and a stable error code; omit response body.
  2) Raise a sanitized error message without provider response content.

### Low

#### 4) X-Forwarded-For is trusted without a proxy-trust flag
- Severity: Low
- Category: Correctness
- Evidence: `apps/api/app/services/session_service.py:61-66` uses `X-Forwarded-For` unconditionally.
- Impact: Client IP can be spoofed in logs and audit trails if the service is not behind a trusted proxy.
- Fix recommendation (exact steps):
  1) Respect `settings.TRUST_PROXY_HEADERS` before trusting `X-Forwarded-For`.
  2) Use Starlette’s `ProxyHeadersMiddleware` when behind a proxy.

#### 5) Avatar/signature URLs are direct S3 paths
- Severity: Low
- Category: Security
- Evidence: `apps/api/app/routers/auth.py:492-496` and `apps/api/app/routers/auth.py:899-904` build public S3 URLs.
- Impact: Requires public bucket or yields broken links; public bucket allows unauthenticated access to user photos.
- Fix recommendation (exact steps):
  1) Store the object key only, not a public URL.
  2) Serve via a signed URL endpoint or a proxy download handler.

#### 6) docs/agents.md is missing
- Severity: Low
- Category: DX
- Evidence: `docs/agents.md` does not exist; root `agents.md` contains the rules.
- Impact: Onboarding and automation rules are ambiguous; README references a non-existent path.
- Fix recommendation (exact steps):
  1) Either move/copy root `agents.md` to `docs/agents.md` or update README to reference the root file.

## Redundancy Map

- Appointment type serializers duplicated in `apps/api/app/routers/appointments.py:61-77` and `apps/api/app/routers/booking.py:44-60`.
- Avatar/signature upload logic duplicated in `apps/api/app/routers/auth.py:371-511` and `apps/api/app/routers/auth.py:831-953` (S3 upload, resize, delete).
- OAuth state cookie creation/verification duplicated between `apps/api/app/routers/auth.py:56-103` and `apps/api/app/routers/integrations.py:132-205`.
- `get_form_logo` and `get_form_logo_by_id` in `apps/api/app/services/form_service.py:162-172` are identical wrappers.
- Org counter increments duplicated for surrogate/match in `apps/api/app/services/surrogate_service.py:93-118` and `apps/api/app/services/match_service.py:13-33`.

## Delete / Merge / Rewrite Recommendations

1) Merge appointment type mapping utilities
   - Delete `_type_to_read` in one router and move a single serializer to `apps/api/app/services/appointment_service.py`.
   - Update both routers to call the shared function.

2) Merge avatar/signature upload handling
   - Create a shared helper in `apps/api/app/services/storage_service.py` (or similar) that takes a storage prefix and returns a stored URL + key.
   - Replace duplicated S3 logic in `apps/api/app/routers/auth.py` with calls to the helper.

3) Rewrite AI entity_type handling
   - AI chat now normalizes `case` → `surrogate`; still standardize on `entity_type="surrogate"` across API, jobs, and DB records and drop the legacy alias after migration.

4) Delete redundant form logo helper
   - Remove `get_form_logo_by_id` or `get_form_logo` and update call sites to use the single remaining function.

5) Centralize org counter generation
   - Create a `counter_service.next_number(org_id, counter_type, prefix)` and replace duplicate SQL in surrogate/match services.
