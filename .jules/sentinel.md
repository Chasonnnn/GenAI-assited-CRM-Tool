## 2026-08-31 - Insufficient Site Isolation Against Spectre Vulnerability
**Vulnerability:** Missing Cross-Origin-Embedder-Policy (COEP) response header.
**Learning:** The application was missing COEP header, leaving it potentially vulnerable to Spectre attacks.
**Prevention:** Ensure security headers middleware includes COEP set to 'require-corp' to mitigate Spectre vulnerabilities.
