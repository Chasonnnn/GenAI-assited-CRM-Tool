## 2026-08-25 - Missing Spectre Mitigation Header
**Vulnerability:** Missing `Cross-Origin-Embedder-Policy` (COEP) header, leading to Insufficient Site Isolation Against Spectre vulnerability (ZAP baseline report ID 90004).
**Learning:** While `Cross-Origin-Opener-Policy` and `Cross-Origin-Resource-Policy` were set, COEP was missing. COEP is required to prevent a document from loading cross-origin resources that don't explicitly grant permission.
**Prevention:** Ensure COEP is included alongside COOP and CORP for complete Spectre mitigation.
