## 2024-08-29 - Missing COEP Header for Spectre Mitigation
**Vulnerability:** The application was missing the `Cross-Origin-Embedder-Policy` (COEP) header, leaving it partially vulnerable to Spectre-style side-channel attacks when embedding cross-origin resources.
**Learning:** While the application had implemented `Cross-Origin-Opener-Policy` (COOP) and `Cross-Origin-Resource-Policy` (CORP), the full site isolation strategy was incomplete without COEP (`require-corp`). The centralized `security_headers_middleware` in FastAPI makes it easy to add such headers globally.
**Prevention:** Ensure new security header implementations consider the full suite of related headers (e.g., COOP, COEP, and CORP together) for complete protection against modern browser-based attack vectors.
