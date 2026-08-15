## 2025-03-01 - Add Cross-Origin-Embedder-Policy Header
**Vulnerability:** Insufficient Site Isolation Against Spectre Vulnerability found by ZAP baseline scan.
**Learning:** The application was missing the `Cross-Origin-Embedder-Policy` (COEP) security header to prevent documents from loading cross-origin resources that don't explicitly grant permission.
**Prevention:** Always configure modern web applications with comprehensive security headers (including HSTS, COOP, and COEP) to mitigate browser-level vulnerabilities like side-channel attacks.
