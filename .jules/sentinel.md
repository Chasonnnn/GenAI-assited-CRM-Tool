## 2026-09-05 - Added COEP header for Spectre protection
**Vulnerability:** Insufficient Site Isolation Against Spectre Vulnerability (missing Cross-Origin-Embedder-Policy header).
**Learning:** The application was missing a required header for strong site isolation against side-channel attacks.
**Prevention:** Ensure new applications strictly define `Cross-Origin-Embedder-Policy: require-corp` in their base security headers middleware.
## 2026-09-05 - Bumped pypdf to fix CVEs
**Vulnerability:** pypdf 6.15.0 had known vulnerabilities (CVE-2026-84309, CVE-2026-84310, CVE-2026-84311).
**Learning:** CI pip-audit pipeline successfully identified a vulnerable package.
**Prevention:** Keep dependencies up to date and rely on automated vulnerability scanning tools.
