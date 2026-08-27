## 2024-08-27 - Insufficient Site Isolation Against Spectre Vulnerability
**Vulnerability:** Missing Cross-Origin-Embedder-Policy header leaving the site vulnerable to Spectre attacks.
**Learning:** The application was missing COEP header, an important mitigation against Spectre.
**Prevention:** Ensure Cross-Origin-Embedder-Policy (COEP) along with COOP and CORP are configured globally in security middleware.
