## 2024-03-01 - Missing rate limiting on MFA endpoints
**Vulnerability:** Several sensitive MFA-related endpoints (like setup, disable, and regeneration) were missing rate limiting. This allowed brute-force requests and increased vulnerability to DoS attacks.
**Learning:** In FastAPI, `slowapi` rate limiting decorators require the `request: Request` parameter in the endpoint function signature. Omitting this decorator or argument leaves critical endpoints un-throttled.
**Prevention:** Always ensure that any endpoint handling sensitive configuration or authentication actions has the `@limiter.limit()` decorator applied and that `request: Request` is injected into its parameters.
