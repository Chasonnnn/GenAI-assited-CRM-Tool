## 2025-02-27 - Rate Limit Secondary OAuth Callbacks
**Vulnerability:** Found missing rate limiting on secondary Journal Mailbox OAuth flow endpoints (`/journal/gmail/oauth/start` and `/journal/gmail/oauth/callback`) in `apps/api/app/routers/mailboxes.py`, despite primary integrations having it.
**Learning:** Even when primary paths (like those in `integrations.py`) are secured against abuse/brute-force via rate limiting, secondary or newer OAuth implementation paths in other router files (like `mailboxes.py`) can be missed.
**Prevention:** Ensure all OAuth, authentication, and integration connect/callback routes, regardless of which domain/router file they belong to, use the standard `@limiter.limit` decorators.
## 2025-02-27 - Backend Dependency Security Fixes
**Vulnerability:** Known CVEs found by pip-audit in backend dependencies `cryptography` (CVE-2026-39892) and `pypdf` (CVE-2026-40260). Also fixed Next.js CVE-GHSA-q4gf-8mx6-v5v3 in frontend.
**Learning:** Security updates require modifying two files in the backend: `pyproject.toml` (implicitly via `uv add`) to update the package version, and `tests/test_dependency_security.py` to update the expected minimum versions.
**Prevention:** Regularly audit and enforce secure versions. Always run `pnpm audit` and `pip-audit` locally, verify fixes in frontend (`pnpm install <package>@<version>`) and backend (`uv add <package>==<version>`), and update corresponding explicit test assertions.
