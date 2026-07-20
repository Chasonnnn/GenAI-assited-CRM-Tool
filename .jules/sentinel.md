## 2024-05-15 - [Session Revocation Missing Rate Limit Exemption]
**Vulnerability:** A session revocation endpoint (`revoke_support_session` in `platform.py`) was protected by rate limiting.
**Learning:** Session revocation endpoints (e.g., logout, revoking other sessions, or revoking support sessions) must explicitly be marked as `@limiter.exempt`. Rate limiting these endpoints is a security anti-pattern because it prevents users from rapidly securing their accounts (e.g., terminating sessions on a compromised device) during an emergency.
**Prevention:** Always verify that newly added or modified session revocation endpoints explicitly include the `@limiter.exempt` decorator and add corresponding tests to `test_auth.py` (or similar) to enforce this policy.
