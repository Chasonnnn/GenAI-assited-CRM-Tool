## 2024-05-24 - Fix Insufficient Site Isolation
**Vulnerability:** Missing Cross-Origin-Embedder-Policy header.
**Learning:** API lacked complete Spectre mitigations. CORP was implemented but COEP was missing.
**Prevention:** Ensure new security headers (like COEP) are implemented together with related headers (COOP, CORP).
