## 2024-04-06 - Missing Rate Limit on Secondary OAuth Endpoints
**Vulnerability:** Secondary OAuth routes (e.g., Journal Mailbox integration in `apps/api/app/routers/mailboxes.py`) lacked the rate limiting that was correctly applied to primary integrations.
**Learning:** Security patterns applied to primary modules (like `integrations.py`) are often overlooked when similar functionality is implemented in secondary or specialized modules.
**Prevention:** Whenever adding or reviewing OAuth or authentication flows, ensure that explicit rate limiting (e.g., `@limiter.limit`) is universally applied across all integration and callback endpoints to prevent abuse.
