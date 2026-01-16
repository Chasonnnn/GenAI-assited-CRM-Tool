# MODERNIZATION_AUDIT

Date: 2026-01-15
Scope: Backend + frontend + infra modernization opportunities with concrete refactor steps.

## Backend

### 1) Replace X-Requested-With CSRF with per-request tokens
- Evidence: `apps/api/app/core/deps.py:298-312` and `apps/api/app/main.py:284-296` use a static `X-Requested-With` header.
- Risk: Static headers are weaker than real CSRF tokens and can be replayed if CORS is misconfigured; does not meet modern CSRF best practices.
- Modern replacement:
  1) Add a CSRF token cookie (`csrf_token`) with a random value per session.
  2) Require `X-CSRF-Token` header to match the cookie for all mutations.
  3) Rotate the token on login and optionally on logout.
- Exact refactor steps:
  1) Create `apps/api/app/core/csrf.py` with token generation + verification helpers.
  2) Add middleware that sets `csrf_token` cookie on first request.
  3) Replace `require_csrf_header` to validate `X-CSRF-Token`.
  4) Update `apps/web/lib/api.ts` to read the cookie and send `X-CSRF-Token`.
- Migration plan:
  1) Implement token issuance + validation and keep accepting `X-Requested-With` for one release.
  2) Update frontend client to send `X-CSRF-Token` and add tests for missing/invalid token.
  3) Remove the legacy header requirement and update docs/examples.
- Effort estimate: 3-5 days (M).

### 2) WebSocket auth hardening (Resolved)
- Status: Resolved.
- Evidence: `apps/api/app/routers/websocket.py:24-132` enforces cookie auth, MFA, membership active, and Origin allowlist.
- Migration plan:
  1) No further migration. Keep regression tests to cover Origin allowlist + membership enforcement.
- Effort estimate: Done.

### 3) Avoid `asyncio.run` in request threads
- Evidence: `apps/api/app/services/ai_chat_service.py:786`, `apps/api/app/services/appointment_service.py:67-71`, `apps/api/app/services/oauth_service.py:394-397`, `apps/api/app/services/ai_action_executor.py:370`, `apps/api/app/services/ai_workflow_service.py:380-382`, `apps/api/app/services/dashboard_service.py:166`, `apps/api/app/services/notification_service.py:297`.
- Risk: Nested event loops and thread pool usage can cause unexpected behavior and performance issues in request/approval flows.
- Modern replacement:
  1) Convert affected endpoints to `async def` and `await` the async calls.
  2) If sync is required, use background tasks or `anyio.to_thread.run_sync`.
- Exact refactor steps:
  1) Make AI approval and Gmail/Zoom send routes async and call async helpers directly.
  2) Replace `asyncio.run` in services with `await` or `anyio.to_thread.run_sync` where blocking is required.
  3) Move long-running external API calls into jobs to keep HTTP handlers fast.
- Migration plan:
  1) Inventory all `asyncio.run` sites and classify into request path vs background jobs.
  2) Convert request handlers to `async def` and add async service entry points.
  3) Route external API calls through jobs where appropriate, add retries and timeouts.
  4) Add performance and regression tests, then remove legacy sync wrappers.
- Effort estimate: 5-10 days (L).

### 4) Public S3 URLs for avatars/signatures
- Evidence: `apps/api/app/routers/auth.py:492-496` and `apps/api/app/routers/auth.py:899-904` return direct S3 URLs.
- Risk: Requires public buckets or breaks access; public buckets expose user photos.
- Modern replacement:
  1) Store object keys in DB and generate signed URLs on demand.
- Exact refactor steps:
  1) Add `apps/api/app/services/storage_service.py` to generate signed URLs.
  2) Replace URL construction in auth router with signed URL generation.
- Migration plan:
  1) Add object-key fields (if missing) and backfill from existing URLs.
  2) Serve avatars/signatures via signed URL endpoint; keep old URL fields for one release.
  3) Remove public URL usage and enforce private buckets.
- Effort estimate: 3-6 days (M-L).

### 5) Manual proxy IP handling
- Evidence: `apps/api/app/services/session_service.py:61-66` uses `X-Forwarded-For` directly.
- Risk: Spoofed IPs; inconsistent with proxy trust settings.
- Modern replacement:
  1) Use Starlette `ProxyHeadersMiddleware` and trust settings.
- Exact refactor steps:
  1) Add `ProxyHeadersMiddleware` in `apps/api/app/main.py` when `TRUST_PROXY_HEADERS` is true.
  2) Update `get_client_ip` to rely on `request.client.host` only.
- Migration plan:
  1) Add `TRUST_PROXY_HEADERS` setting and enable in staging behind the proxy.
  2) Verify logged IPs match ingress headers; roll out to production.
  3) Remove direct `X-Forwarded-For` reads.
- Effort estimate: 1-2 days (S).

### 6) In-memory idempotency cache for AI bulk tasks
- Evidence: `apps/api/app/routers/ai.py:1909-1939` uses a module-level dict for `request_id` caching.
- Risk: Not shared across workers, lost on restart, unbounded memory growth under load.
- Modern replacement:
  1) Persist idempotency responses in DB or Redis with TTL.
- Exact refactor steps:
  1) Add a `bulk_task_idempotency` table (`org_id`, `user_id`, `request_id`, `response_json`, `created_at`, `expires_at`) with a unique constraint on `(org_id, user_id, request_id)`.
  2) On request, look up an existing response by key and return it if present.
  3) On success, insert the response and set a TTL (cleanup job or DB scheduled deletion).
- Migration plan:
  1) Add the new idempotency table and backfill nothing (new only).
  2) Update the endpoint to read/write idempotency records; add a cleanup job.
  3) Remove the in-memory cache once DB-backed idempotency is confirmed.
- Effort estimate: 2-4 days (M).

## Frontend

### 7) Client-side auth redirect instead of server-side gating
- Evidence: `apps/web/lib/auth-context.tsx:104-120` redirects on the client after rendering.
- Risk: Flash of protected content and inconsistent auth UX; no server-side enforcement.
- Modern replacement:
  1) Use Next.js middleware to enforce authentication at the edge.
  2) Use server components/layouts to redirect before render.
- Exact refactor steps:
  1) Add `apps/web/middleware.ts` to check session cookie and redirect to `/login`.
  2) Move auth gating logic into `apps/web/app/(app)/layout.tsx` server component if needed.
- Migration plan:
  1) Implement middleware gating for `/app` routes and keep client redirects as fallback.
  2) Move protected data fetching into server components where possible.
  3) Remove client-side redirect once middleware is validated in staging.
- Effort estimate: 2-4 days (M).

## Infra / Ops

### 8) Rate limiting fallback to in-memory in production (Resolved)
- Status: Resolved.
- Evidence: `apps/api/app/core/rate_limit.py:33-53` requires Redis in non-dev and raises on failure.
- Migration plan:
  1) No further migration. Ensure Redis health checks and alerts in staging/prod.
- Effort estimate: Done.
