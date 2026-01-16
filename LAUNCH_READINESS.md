# LAUNCH_READINESS

Date: 2026-01-15
Scope: Full-file audit with emphasis on tenant isolation, public attack surfaces, PII handling, and ops readiness.

## Executive Summary (Top 10 Launch Blockers + Fix Order)
1) Resolved: AI anonymization bypass (`entity_type=case`), PII can be sent unredacted.
2) Resolved: Missing org scoping in status change request service entity lookups.
3) Resolved: Missing org scoping in AI/workflow helpers (surrogate context, document triggers).
4) Blocker: Tracking click endpoint allows open redirect.
5) Blocker: PII in logs (session IP logging, transcription error body).
6) Blocker: Virus scanning not enforced by default for uploads (public forms/attachments).
7) Blocker: Redis-backed rate limiting is optional; in-memory fallback weakens production protection.
8) Blocker: Public GET endpoints lack rate limits (forms/booking).
9) Blocker: No documented backups/restore procedure.
10) Blocker: `META_TEST_MODE` bypasses webhook signature without a prod guard.

Recommended fix order: 4 → 5 → 6 → 7 → 8 → 9 → 10.

## Launch Gates (Pass/Fail)

| Gate | Status | Evidence | Required Action |
|---|---|---|---|
| Tenant isolation | PASS | Org-scoped lookups in `apps/api/app/services/status_change_request_service.py`, `apps/api/app/services/ai_chat_service.py`, `apps/api/app/services/ai_action_executor.py`, `apps/api/app/services/workflow_engine.py`, `apps/api/app/services/workflow_triggers.py`; cross-org tests added in `apps/api/tests/test_status_change_request_scoping.py`, `apps/api/tests/test_ai_action_executor_scoping.py`, `apps/api/tests/test_workflow_trigger_scoping.py`. | None. |
| Auth hardening | PASS | Membership is_active enforced (`apps/api/app/core/deps.py:152-169`); WebSocket uses cookie auth + Origin allowlist (`apps/api/app/routers/websocket.py:22-132`); dev bypass removed from frontend (`apps/web/lib/auth-context.tsx:1-122`). | None. |
| PII/secrets handling | FAIL | Raw IP logging (`apps/api/app/services/session_service.py:113-118`); transcription error logs (`apps/api/app/services/transcription_service.py:135-136`). | Mask IPs; sanitize error logs. |
| Public attack surface | FAIL | Open redirect in tracking (`apps/api/app/routers/tracking.py:126-166`, `apps/api/app/services/tracking_service.py:168-211`) | Replace URL param with stored link id or signed URL validation. |
| Upload safety | FAIL | Virus scanning default off (`apps/api/app/core/config.py:214`, `apps/api/app/services/form_service.py:916-940`) | Enforce scanning in prod; document ClamAV deployment. |
| Rate limiting | FAIL | Redis fallback to in-memory (`apps/api/app/core/rate_limit.py:16-50`) | Require Redis in prod; fail fast if unavailable. |
| Monitoring/alerting | PARTIAL | Sentry and GCP monitoring optional (`apps/api/app/main.py:148-163`, `apps/api/app/core/gcp_monitoring.py`) | Enable in staging/prod with alert routing. |
| Backups/restore | FAIL | No documented restore procedure found | Create runbook and test restore. |
| Integration idempotency | PARTIAL | Meta jobs idempotent; Gmail/Zoom send lacks retries/idempotency (`apps/api/app/services/gmail_service.py:22-100`) | Add retry policy and idempotency keys. |
| ZAP baseline scan | FAIL | No recorded run; config exists (`zap-baseline.conf`) | Run ZAP against staging and fix findings. |

## Public Attack Surfaces

### Public forms (apply)
- Surface: `GET /forms/public/{token}`, `POST /forms/public/{token}/submit` (`apps/api/app/routers/forms_public.py:51-110`).
- Protections: tokenized access, rate limit on submit.
- Gaps: no explicit rate limit on GET; virus scanning optional.
- Required changes:
  1) Enforce `ATTACHMENT_SCAN_ENABLED=true` in production.
  2) Add rate limiting on GET endpoints for token brute-force protection.

### Public booking
- Surface: `/book/{public_slug}`, `/book/{public_slug}/slots`, `/book/{public_slug}/book` (`apps/api/app/routers/booking.py:92-238`).
- Protections: random slug, rate limit on booking actions.
- Gaps: no rate limit on page/slots; potential enumeration load.
- Required changes:
  1) Add rate limits to page + slots endpoints.
  2) Add abuse protection (IP throttling + basic bot detection headers).

### Email tracking
- Surface: `/tracking/open/{token}`, `/tracking/click/{token}` (`apps/api/app/routers/tracking.py:83-166`).
- Protections: token required.
- Gaps: open redirect on click; no validation on url param.
- Required changes:
  1) Replace `url` param with server-stored link id, or sign URL with HMAC and verify.

### Webhooks
- Surface: `/webhooks/meta` (`apps/api/app/routers/webhooks.py:23-148`).
- Protections: HMAC signature, payload size limit, rate limiting.
- Gaps: `META_TEST_MODE` bypasses signature; no prod guard.
- Required changes:
  1) Add config validation to prevent `META_TEST_MODE=true` in non-dev.

### Auth/OAuth
- Surface: Google OAuth, integration callbacks (`apps/api/app/routers/auth.py`, `apps/api/app/routers/integrations.py`).
- Protections: state+nonce cookies, UA binding, secure cookies in non-dev.
- Gaps: None observed in current auth flow.

## Multi-Tenancy Audit

### Org scoping risks
- Resolved: org-scoped lookups in `apps/api/app/services/status_change_request_service.py`, `apps/api/app/services/ai_chat_service.py`, `apps/api/app/services/ai_action_executor.py`, `apps/api/app/services/workflow_engine.py`, `apps/api/app/services/workflow_triggers.py`.

### Missing tests
- Resolved: cross-org coverage added in `apps/api/tests/test_status_change_request_scoping.py`, `apps/api/tests/test_ai_action_executor_scoping.py`, `apps/api/tests/test_workflow_trigger_scoping.py`.

## Auth/RBAC Audit

- WebSocket auth uses cookie-based sessions with Origin allowlist (`apps/api/app/routers/websocket.py:22-132`).
- Membership is_active enforced in session dependency (`apps/api/app/core/deps.py:152-169`).
- Public endpoints appear intentional: forms_public, booking, tracking, webhooks; no other unauthenticated routes found.

## PII/Secrets Audit

- Raw IP logging in sessions (`apps/api/app/services/session_service.py:113-118`).
- Transcription error logs include provider response body (`apps/api/app/services/transcription_service.py:135-136`).
- Tokens stored encrypted (good): `apps/api/app/services/oauth_service.py:88-170`, `apps/api/app/core/encryption.py`.
- Required changes:
  1) Mask IPs in logs.
  2) Sanitize provider error logging to exclude bodies.

## Ops Readiness

### Migrations
- Alembic commands present in `agents.md` and README.
- Required changes:
  1) Add a staging migration runbook that includes verification of `alembic upgrade head` idempotency.

### Backups / Restore
- No restore procedure documented.
- Required changes:
  1) Add a restore runbook for Postgres and S3/local storage.
  2) Execute a quarterly restore test and record results.

### Monitoring & Alerting
- Sentry and GCP monitoring are optional (`apps/api/app/main.py:148-163`).
- Required changes:
  1) Enable one error tracking path (Sentry or GCP) in staging and prod; verify alert routing.

### Rate Limiting
- Redis fallback to in-memory in production (`apps/api/app/core/rate_limit.py:16-50`).
- Required changes:
  1) Require Redis in prod; fail startup if unavailable.

### Retry/Idempotency for Integrations
- Meta lead fetch is idempotent; Meta CAPI uses event_id.
- Gmail/Zoom send lacks retries/idempotency (`apps/api/app/services/gmail_service.py:22-100`).
- Required changes:
  1) Add retry policy with exponential backoff for Gmail/Zoom API calls.
  2) Add idempotency keys for send operations where possible.

### ZAP Baseline Scan Plan (Staging)
- Run against staging URL with config `zap-baseline.conf`.
- Required steps:
  1) Deploy staging with sample data.
  2) Run baseline scan and export report.
  3) Triage findings and re-run after fixes.

## Validation Commands

### Backend
```bash
cd apps/api && .venv/bin/python -m pytest -v
cd apps/api && ruff check . --fix && ruff format .
cd apps/api && alembic upgrade head
```

### Frontend
```bash
cd apps/web && pnpm tsc --noEmit
cd apps/web && pnpm test --run
cd apps/web && pnpm lint
```

### Security Scan (ZAP baseline)
```bash
# Replace https://staging.example.com with your staging URL
# The config file is already in the repo root

docker run -t owasp/zap2docker-stable \
  zap-baseline.py \
  -t https://staging.example.com \
  -c zap-baseline.conf \
  -x zap-baseline-report.xml
```
