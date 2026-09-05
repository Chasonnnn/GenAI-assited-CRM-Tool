## 2026-09-05 - Added COEP header for Spectre protection
**Vulnerability:** Insufficient Site Isolation Against Spectre Vulnerability (missing Cross-Origin-Embedder-Policy header).
**Learning:** The application was missing a required header for strong site isolation against side-channel attacks.
**Prevention:** Ensure new applications strictly define `Cross-Origin-Embedder-Policy: require-corp` in their base security headers middleware.
