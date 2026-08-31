## 2025-03-01 - Add Cross-Origin-Embedder-Policy Header
**Vulnerability:** Insufficient Site Isolation Against Spectre Vulnerability found by ZAP baseline scan.
**Learning:** The application was missing the `Cross-Origin-Embedder-Policy` (COEP) security header to prevent documents from loading cross-origin resources that don't explicitly grant permission.
**Prevention:** Always configure modern web applications with comprehensive security headers (including HSTS, COOP, and COEP) to mitigate browser-level vulnerabilities like side-channel attacks.
## 2025-03-01 - Update nanoid frontend dependency
**Vulnerability:** nanoid version < 3.3.18 is vulnerable to a custom generator infinite loop issue.
**Learning:** Found via `pnpm audit`. When addressing frontend dependency vulnerabilities, the fix must explicitly override the package version in `pnpm-workspace.yaml`, as Next.js/PostCSS may use an older version transitively.
**Prevention:** Regularly run `pnpm audit --audit-level=high` and use `overrides` in the workspace to pin secure versions for deeply nested transitive dependencies.
