## 2025-02-27 - Rate Limit Secondary OAuth Callbacks
**Vulnerability:** Found missing rate limiting on secondary Journal Mailbox OAuth flow endpoints (`/journal/gmail/oauth/start` and `/journal/gmail/oauth/callback`) in `apps/api/app/routers/mailboxes.py`, despite primary integrations having it.
**Learning:** Even when primary paths (like those in `integrations.py`) are secured against abuse/brute-force via rate limiting, secondary or newer OAuth implementation paths in other router files (like `mailboxes.py`) can be missed.
**Prevention:** Ensure all OAuth, authentication, and integration connect/callback routes, regardless of which domain/router file they belong to, use the standard `@limiter.limit` decorators.
