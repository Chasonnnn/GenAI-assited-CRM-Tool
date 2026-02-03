## 2026-01-29 - Missing Frontend Security Headers
**Vulnerability:** The Next.js frontend (`apps/web`) was missing critical security headers like `X-Frame-Options`, `X-Content-Type-Options`, and `Strict-Transport-Security`.
**Learning:** While the backend API had security headers configured, the frontend serving the HTML did not. Next.js does not add these by default.
**Prevention:** Always verify `middleware.ts` or `next.config.js` in Next.js applications to ensure security headers are explicitly configured.
