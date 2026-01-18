# MODERNIZATION_AUDIT

Date: 2026-01-16
Scope: Backend + frontend + infra modernization opportunities with concrete refactor steps.

## Backend

### 1) Replace X-Requested-With CSRF with per-request tokens (Resolved)
- Status: Resolved.
- Evidence: `apps/api/app/core/csrf.py:1-52`, `apps/api/app/core/deps.py:289-300`, `apps/api/app/main.py:284-305`, `apps/web/lib/csrf.ts:1-15`, `apps/web/lib/api.ts:21-38`.
- Migration plan:
  1) No further migration. `X-Requested-With` is removed and `X-CSRF-Token` is required.
- Effort estimate: Done.

### 2) WebSocket auth hardening (Resolved)
- Status: Resolved.
- Evidence: `apps/api/app/routers/websocket.py:24-132` enforces cookie auth, MFA, membership active, and Origin allowlist.
- Migration plan:
  1) No further migration. Keep regression tests to cover Origin allowlist + membership enforcement.
- Effort estimate: Done.

### 3) Avoid `asyncio.run` in request threads (Resolved)
- Status: Resolved.
- Evidence: `apps/api/app/core/async_utils.py:1-36`, `apps/api/app/services/appointment_service.py:27-78`, `apps/api/app/services/oauth_service.py:400-448`, `apps/api/app/services/ai_workflow_service.py:367-414`, `apps/api/app/services/ai_action_executor.py:345-411`, `apps/api/app/services/ai_chat_service.py:880-909`, `apps/api/app/services/dashboard_service.py:160-201`, `apps/api/app/services/notification_service.py:285-330`, `apps/api/tests/test_async_utils.py:1-23`.
- Migration plan:
  1) No further migration. Request-thread async calls use AnyIO bridge; worker loop still uses `asyncio.run` as intended.
- Effort estimate: Done.

### 4) Public S3 URLs for avatars/signatures (Resolved)
- Status: Resolved.
- Evidence: `apps/api/app/services/media_service.py:1-49`, `apps/api/app/routers/auth.py:241-790`, `apps/api/app/routers/settings.py:295-661`, `apps/api/app/services/signature_template_service.py:95-168`, `apps/api/app/routers/booking.py:124-134`, `apps/api/app/routers/appointments.py:399-409`.
- Migration plan:
  1) No further migration. Signed URLs are returned and public-read ACLs removed.
- Effort estimate: Done.

### 5) Manual proxy IP handling (Resolved)
- Status: Resolved.
- Evidence: `apps/api/app/main.py:184-201`, `apps/api/app/services/session_service.py:63-74`, `apps/api/tests/test_proxy_headers.py:1-32`.
- Migration plan:
  1) No further migration. Set `TRUST_PROXY_HEADERS=true` behind Cloud Run/LB.
- Effort estimate: Done.

### 6) In-memory idempotency cache for AI bulk tasks (Resolved)
- Status: Resolved.
- Evidence: `apps/api/app/db/models.py:2365-2406`, `apps/api/alembic/versions/20260116_1400_add_ai_bulk_task_requests.py:1-63`, `apps/api/app/routers/ai.py:1918-2089`, `apps/api/tests/test_ai_bulk_tasks.py:198-256`.
- Migration plan:
  1) No further migration. DB-backed idempotency is active.
- Effort estimate: Done.

## Frontend

### 7) Client-side auth redirect instead of server-side gating (Resolved)
- Status: Resolved.
- Evidence: `apps/web/middleware.ts:1-28`, `apps/web/app/(app)/layout.tsx:1-49`.
- Migration plan:
  1) No further migration. Middleware enforces auth before render.
- Effort estimate: Done.

## Infra / Ops

### 8) Rate limiting fallback to in-memory in production (Resolved)
- Status: Resolved.
- Evidence: `apps/api/app/core/rate_limit.py:33-53` requires Redis in non-dev and raises on failure.
- Migration plan:
  1) No further migration. Ensure Redis health checks and alerts in staging/prod.
- Effort estimate: Done.
