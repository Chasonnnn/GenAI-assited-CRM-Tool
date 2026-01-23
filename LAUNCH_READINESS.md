# LAUNCH_READINESS

Date: 2026-01-23
Scope: Full-file audit with emphasis on tenant isolation, public attack surfaces, PII handling, and ops readiness.

## Open Launch Items (Do First)
- [ ] Run ZAP baseline scan against staging and triage findings (`zap-baseline.conf`).
- [ ] Run staging migration with idempotency check and log it (`docs/migration-runbook.md`).
- [ ] Execute quarterly restore test and record results (`docs/backup-restore-runbook.md`).
- [ ] Verify GCP alert routing and record results (`docs/monitoring-runbook.md`).

## Executive Summary (Blockers + Fix Order)
1) Blocker: ZAP baseline scan not run against staging (no report recorded).
2) Blocker: Staging migration idempotency check not logged in `docs/migration-runbook.md` (run log empty).
3) Blocker: Quarterly restore test not recorded in `docs/backup-restore-runbook.md` (restore test log empty).
4) Blocker: GCP alert routing verification not recorded in `docs/monitoring-runbook.md` (alert test log empty).

Recommended fix order: 1, then 2–4 (parallelizable).

## Launch Gates (Open Actions First)

| Gate | Status | Evidence | Required Action |
|---|---|---|---|
| ZAP baseline scan | FAIL | No recorded run; config exists (`zap-baseline.conf`) | Run ZAP against staging and fix findings. |
| Staging migration idempotency | FAIL | Runbook exists but run log is empty (`docs/migration-runbook.md`). | Run the staging migration + idempotency check and record it in `docs/migration-runbook.md`. |
| Monitoring/alerting | FAIL | Code enforcement exists (non-dev config requires Sentry or GCP monitoring in `apps/api/app/core/config.py`, Sentry initializes when configured in `apps/api/app/main.py:148-163`) but alert routing verification is not recorded (alert test log empty in `docs/monitoring-runbook.md`). | Verify alert routing and record results in `docs/monitoring-runbook.md`. |
| Backups/restore | FAIL | Runbook exists but restore test is not recorded (restore test log empty in `docs/backup-restore-runbook.md`). | Run a quarterly restore test and record results in `docs/backup-restore-runbook.md`. |
| Tenant isolation | PASS | Org-scoped lookups in `apps/api/app/services/status_change_request_service.py`, `apps/api/app/services/ai_chat_service.py`, `apps/api/app/services/ai_action_executor.py`, `apps/api/app/services/workflow_engine.py`, `apps/api/app/services/workflow_triggers.py`; cross-org tests added in `apps/api/tests/test_status_change_request_scoping.py`, `apps/api/tests/test_ai_action_executor_scoping.py`, `apps/api/tests/test_workflow_trigger_scoping.py`. | None. |
| Auth hardening | PASS | Membership is_active enforced (`apps/api/app/core/deps.py:152-169`); WebSocket uses cookie auth + Origin allowlist (`apps/api/app/routers/websocket.py:22-132`); dev bypass removed from frontend (`apps/web/lib/auth-context.tsx:1-122`). | None. |
| PII/secrets handling | PASS | IPs masked in logs (`apps/api/app/services/session_service.py`); transcription errors sanitized (`apps/api/app/services/transcription_service.py`). | None. |
| Public attack surface | PASS | Public GET endpoints rate-limited in `apps/api/app/routers/forms_public.py` and `apps/api/app/routers/booking.py` with `RATE_LIMIT_PUBLIC_READ`. | None. |
| Upload safety | PASS | Virus scanning enforced in non-dev config (`apps/api/app/core/config.py`). | None. |
| Rate limiting | PASS | Redis required in non-dev (`apps/api/app/core/rate_limit.py`). | None. |
| Integration idempotency | PASS | Gmail send retries + idempotency logging (`apps/api/app/services/gmail_service.py`), Zoom create retries + idempotency on meetings (`apps/api/app/services/zoom_service.py`), keys stored in `email_logs` + `zoom_meetings`. | None. |

## Public Attack Surfaces

### Public forms (apply)
- Surface: `GET /forms/public/{token}`, `POST /forms/public/{token}/submit` (`apps/api/app/routers/forms_public.py:51-110`).
- Protections: tokenized access, rate limit on submit.
- Gaps: None observed; GET endpoints rate-limited via `RATE_LIMIT_PUBLIC_READ`.

### Public booking
- Surface: `/book/{public_slug}`, `/book/{public_slug}/slots`, `/book/{public_slug}/book` (`apps/api/app/routers/booking.py:92-238`).
- Protections: random slug, rate limit on booking actions.
- Gaps: None observed; page/slots endpoints rate-limited via `RATE_LIMIT_PUBLIC_READ`.

### Email tracking
- Surface: `/tracking/open/{token}`, `/tracking/click/{token}` (`apps/api/app/routers/tracking.py:83-166`).
- Protections: token required.
- Gaps: None observed with signed URL validation.

### Webhooks
- Surface: `/webhooks/meta` (`apps/api/app/routers/webhooks.py:23-148`).
- Protections: HMAC signature, payload size limit, rate limiting.
- Gaps: None observed; `META_TEST_MODE` blocked in non-dev (`apps/api/app/core/config.py`).

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

- Tokens stored encrypted (good): `apps/api/app/services/oauth_service.py:88-170`, `apps/api/app/core/encryption.py`.
- Resolved: IPs masked in logs; transcription error messages sanitized.

## Ops Readiness

### Migrations
- Alembic commands present in `agents.md` and README.
- Required changes:
  1) Staging migration runbook added in `docs/migration-runbook.md` (includes `alembic upgrade head` idempotency check). Record the latest run in the log.

### Backups / Restore
- Runbook added in `docs/backup-restore-runbook.md`.
- Required changes:
  1) Execute a quarterly restore test and record results in `docs/backup-restore-runbook.md`.

### Monitoring & Alerting
- Enforced: non-dev requires Sentry DSN or GCP monitoring config (`apps/api/app/core/config.py`).
- Required changes:
  1) Use GCP monitoring: set `GCP_PROJECT_ID` or `GOOGLE_CLOUD_PROJECT` in staging/prod and verify alert routing (see `docs/monitoring-runbook.md`).

### Rate Limiting
- Resolved: Redis required in non-dev (`apps/api/app/core/rate_limit.py`).

### Retry/Idempotency for Integrations
- Meta lead fetch is idempotent; Meta CAPI uses event_id.
- Resolved: Gmail send uses retry + EmailLog idempotency; Zoom create uses retry + meeting idempotency.

### ZAP Baseline Scan Plan (Staging)
- Run against staging URL with config `zap-baseline.conf`.
- Required steps:
  1) Deploy staging with sample data.
  2) Run baseline scan and export report.
  3) Triage findings and re-run after fixes.

## Resolved Items (Historical)
1) Resolved: AI anonymization bypass (`entity_type=case`), PII can be sent unredacted.
2) Resolved: Missing org scoping in status change request service entity lookups.
3) Resolved: Missing org scoping in AI/workflow helpers (surrogate context, document triggers).
4) Resolved: Tracking click endpoint allows open redirect.
5) Resolved: PII in logs (session IP logging, transcription error body).
6) Resolved: Virus scanning not enforced by default for uploads (public forms/attachments).
7) Resolved: Redis-backed rate limiting is optional; in-memory fallback weakens production protection.
8) Resolved: Gmail/Zoom send paths now include retries + idempotency keys.
9) Resolved: Monitoring/alerting enforced in non-dev (Sentry or GCP required).

## Validation Results (Local)
- 2026-01-23: Backend `pytest` passed (467 tests); `ruff check` passed. Frontend `pnpm tsc --noEmit`, `pnpm test --run`, and `pnpm lint` passed.

## Validation Commands

### Backend
```bash
cd apps/api && uv run -m pytest -v
cd apps/api && ruff check . --fix && ruff format .
cd apps/api && uv run -m alembic upgrade head
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
