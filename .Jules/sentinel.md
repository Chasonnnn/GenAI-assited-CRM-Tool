## 2024-05-09 - [Rate Limiting Session Revocation]
**Vulnerability:** The `logout` endpoint in `apps/api/app/routers/auth.py` is rate-limited, preventing users from quickly logging out.
**Learning:** Rate limiting session revocation (like logout) is a security anti-pattern because it prevents users from rapidly securing their accounts in an emergency.
**Prevention:** Always use `@limiter.exempt` on session revocation endpoints.
