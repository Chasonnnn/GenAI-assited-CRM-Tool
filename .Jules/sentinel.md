## 2026-01-11 - Content-Type Spoofing via Mismatched Extensions
**Vulnerability:** File upload validation relied on independent whitelists for extensions and MIME types, allowing mismatched pairs (e.g. `.jpg` file with `application/pdf` MIME type).
**Learning:** Checking Extension and MIME type independently is insufficient. Attackers can bypass one check or confuse systems by mixing them.
**Prevention:** Always enforce a strict mapping between allowed MIME types and their corresponding extensions.
