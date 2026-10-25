## 2026-10-25 - Fix Critical/High Dependencies in apps/web
**Vulnerability:** Found 3 CRITICAL vulnerabilities in Next.js/DOMPurify and 5 HIGH vulnerabilities in zod, happy-dom, undici in the apps/web dependencies.
**Learning:** These can expose the application to RCE, XSS, and DoS attacks.
**Prevention:** Regularly audit dependencies and ensure automated update bots are running and correctly monitoring high and critical vulnerabilities. Use `pnpm-workspace.yaml` overrides when deep transitive dependencies are vulnerable but not explicitly declared in `package.json`.
