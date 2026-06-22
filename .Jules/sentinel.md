## 2026-06-20 - Security vulnerabilities in js-yaml, markdown-it, dompurify, and @babel/core
**Vulnerability:** Several frontend dependencies had vulnerabilities that failed the CI security scan. `js-yaml` (<=4.1.1, GHSA-h67p-54hq-rp68), `markdown-it` (<=14.1.1, GHSA-6v5v-wf23-fmfq), `dompurify` (<=3.4.10, GHSA-cmwh-pvxp-8882, GHSA-vxr8-fq34-vvx9, GHSA-gvmj-g25r-r7wr), and `@babel/core` (<=7.29.0, GHSA-4x5r-pxfx-6jf8).
**Learning:** We need to keep frontend packages updated and explicitly patch transitive dependencies in `pnpm.overrides` when necessary. Specifically, `markdown-it` was overridden to `14.1.1` in `package.json`, which was vulnerable. It had to be explicitly overridden to `14.2.0`.
**Prevention:** Regularly run `pnpm audit` and ensure `pnpm.overrides` does not pin packages to vulnerable versions.

## 2026-06-20 - Security vulnerabilities in pydantic-settings and pypdf
**Vulnerability:** `pydantic-settings` (<=2.13.0) had a vulnerability (GHSA-4xgf-cpjx-pc3j) and `pypdf` (<=6.13.2) had a vulnerability (GHSA-jm82-fx9c-mx94). These were failing the CI security scan.
**Learning:** `pip-audit` detects vulnerabilities and fails the CI. We need to explicitly bump versions and add exact pins in `test_dependency_security.py` for resolution to pass tests and the CI.
**Prevention:** Monitor dependency versions and respond to pip-audit failures by appropriately bumping and pinning versions.
