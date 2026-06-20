## 2026-05-29 - Rate limit bypass for session revocation
**Vulnerability:** Session revocation endpoints (`/me/sessions/{session_id}` and `/me/sessions`) were implicitly rate-limited, preventing users from quickly revoking multiple sessions in an emergency.
**Learning:** Security actions (like logging out or revoking sessions) should not be subject to general API rate limits, as this can block legitimate security responses.
**Prevention:** Always use `@limiter.exempt` on session revocation endpoints.
