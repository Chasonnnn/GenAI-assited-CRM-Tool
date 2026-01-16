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

### 2) WebSocket auth uses query tokens and lacks Origin checks
- Evidence: `apps/api/app/routers/websocket.py:22-77` accepts `?token=...` and does not validate Origin.
- Risk: Token leakage via logs/referrers; cross-site WebSocket connections are possible.
- Modern replacement:
  1) Remove query tokens; use session cookies or a short-lived signed WS token.
  2) Validate `Origin` header against `settings.FRONTEND_URL` allowlist.
- Exact refactor steps:
  1) Add `/ws/token` endpoint that returns a short-lived token tied to the session.
  2) Pass that token via `Sec-WebSocket-Protocol` or `Authorization` header.
  3) Validate Origin in the WS handler before accepting.

### 3) Avoid `asyncio.run` in request threads
- Evidence: `apps/api/app/services/ai_chat_service.py:736-756` and `apps/api/app/services/appointment_service.py:48-74` call `asyncio.run` from sync code.
- Risk: Nested event loops and thread pool usage can cause unexpected behavior and performance issues.
- Modern replacement:
  1) Convert affected endpoints to `async def` and `await` the async calls.
  2) If sync is required, use background tasks or `anyio.to_thread.run_sync`.
- Exact refactor steps:
  1) Update the FastAPI route handlers that call `ai_chat_service.chat` to be async.
  2) Replace `ai_chat_service.chat` wrapper with direct `await chat_async`.
  3) Remove `_run_async` in `appointment_service` and move integrations to background jobs.

### 4) Public S3 URLs for avatars/signatures
- Evidence: `apps/api/app/routers/auth.py:492-496` and `apps/api/app/routers/auth.py:899-904` return direct S3 URLs.
- Risk: Requires public buckets or breaks access; public buckets expose user photos.
- Modern replacement:
  1) Store object keys in DB and generate signed URLs on demand.
- Exact refactor steps:
  1) Add `apps/api/app/services/storage_service.py` to generate signed URLs.
  2) Replace URL construction in auth router with signed URL generation.

### 5) Manual proxy IP handling
- Evidence: `apps/api/app/services/session_service.py:61-66` uses `X-Forwarded-For` directly.
- Risk: Spoofed IPs; inconsistent with proxy trust settings.
- Modern replacement:
  1) Use Starlette `ProxyHeadersMiddleware` and trust settings.
- Exact refactor steps:
  1) Add `ProxyHeadersMiddleware` in `apps/api/app/main.py` when `TRUST_PROXY_HEADERS` is true.
  2) Update `get_client_ip` to rely on `request.client.host` only.

## Frontend

### 6) Client-side auth redirect instead of server-side gating
- Evidence: `apps/web/lib/auth-context.tsx:104-120` redirects on the client after rendering.
- Risk: Flash of protected content and inconsistent auth UX; no server-side enforcement.
- Modern replacement:
  1) Use Next.js middleware to enforce authentication at the edge.
  2) Use server components/layouts to redirect before render.
- Exact refactor steps:
  1) Add `apps/web/middleware.ts` to check session cookie and redirect to `/login`.
  2) Move auth gating logic into `apps/web/app/(app)/layout.tsx` server component if needed.

## Infra / Ops

### 7) Rate limiting fallback to in-memory in production
- Evidence: `apps/api/app/core/rate_limit.py:16-50` falls back to `memory://` if Redis is down.
- Risk: Weak rate limiting in multi-instance production; can be bypassed.
- Modern replacement:
  1) Require Redis in production or offload to API gateway (Cloudflare/Envoy).
- Exact refactor steps:
  1) Add a startup check that fails if Redis is unreachable when `ENV != dev/test`.
  2) Document Redis as a required production dependency.
