## 2026-10-25 - Fix Critical/High Dependencies in apps/web
**Vulnerability:** Found 3 CRITICAL vulnerabilities in Next.js/DOMPurify and 5 HIGH vulnerabilities in zod, happy-dom, undici in the apps/web dependencies.
**Learning:** These can expose the application to RCE, XSS, and DoS attacks.
**Prevention:** Regularly audit dependencies and ensure automated update bots are running and correctly monitoring high and critical vulnerabilities. Use `pnpm-workspace.yaml` overrides when deep transitive dependencies are vulnerable but not explicitly declared in `package.json`.

## 2026-10-25 - Fix High Vulnerabilities in apps/api dependencies
**Vulnerability:** Found vulnerabilities in `opentelemetry-api` (CVE-2026-114603) and `pypdf` (CVE-2026-115572, CVE-2026-115585, CVE-2026-115580).
**Learning:** These impact tracing security and pdf rendering safety.
**Prevention:** Monitor dependencies regularly using `pip-audit` to catch API and SDK vulnerability issues early in backend packages.

## 2026-10-25 - Fix High Vulnerability in apps/ops-cli dependencies
**Vulnerability:** Found vulnerability in `certifi` (PYSEC-2026-4320).
**Learning:** This impacts SSL/TLS verification.
**Prevention:** Monitor dependencies regularly using `pip-audit` to catch vulnerability issues early in ops-cli packages.
