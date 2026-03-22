## 2024-06-11 - [Security Pattern - Rate Limiting on Session Revocation]
**Vulnerability:** Missing rate limiting on session revocation endpoints in `apps/api/app/routers/auth.py`. Specifically `revoke_session` and `revoke_all_sessions`.
**Learning:** While `/logout` was rate limited, the specific session management endpoints (`/me/sessions/{session_id}` and `/me/sessions`) were not. This could allow an attacker to attempt to enumerate session IDs or cause a denial of service. The pattern is that sensitive authentication endpoints must explicitly include the rate limiter.
**Prevention:** Make sure `request: Request` is added to the function signature and `@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")` is added above all sensitive session-modifying endpoints.
