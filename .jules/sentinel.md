## 2025-05-18 - [Dependency Fix]
**Vulnerability:** urllib3 2.6.3 had CVEs and Next.js had high and moderate vulnerabilities.
**Learning:** Found these by running `uv run --with pip-audit -- python scripts/pip_audit_guard.py` in `apps/api` and `pnpm audit` in `apps/web`.
**Prevention:** Always pin securely or use `.overrides` to block vulnerable sub-dependencies in `package.json`.
