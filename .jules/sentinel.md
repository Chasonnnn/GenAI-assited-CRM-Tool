## 2025-05-20 - Missing COEP Header for Spectre Mitigation
**Vulnerability:** Missing `Cross-Origin-Embedder-Policy` (COEP) response header.
**Learning:** While COOP and CORP headers were set to mitigate Spectre vulnerabilities, COEP was missing. COEP requires the browser to only load cross-origin resources that explicitly grant permission, forming a complete defense when combined with COOP.
**Prevention:** Ensure all three headers (COOP, CORP, COEP) are set together for full Spectre mitigation in FastAPI's security headers middleware.
