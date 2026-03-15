## 2026-03-15 - [High] Dependency vulnerabilities in PyJWT and PyPDF
**Vulnerability:** Detected CVE-2026-32597 in pyjwt 2.11.0 and CVE-2026-31826 in pypdf 6.7.5 during `pip-audit`.
**Learning:** Outdated dependencies with known vulnerabilities can lead to severe security risks like authentication bypass or arbitrary code execution.
**Prevention:** Regularly update dependencies and enforce automated vulnerability scanning (like `pip-audit` or `pnpm audit`) in CI/CD pipelines.
