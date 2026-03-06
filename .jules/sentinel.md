## 2024-05-24 - Rate Limiting on OAuth Integrations
**Vulnerability:** Meta OAuth integration connect and callback endpoints were missing explicit rate limits, making them vulnerable to DoS attacks and resource exhaustion.
**Learning:** Even though integration endpoints don't authenticate the main user session, they still initiate and receive OAuth flows. Just like primary auth endpoints, these must be protected against brute-force and DoS using rate limiting.
**Prevention:** Always apply explicit rate limiting (`@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")`) to ALL endpoints handling OAuth flows, including third-party integrations, not just primary login routes.
