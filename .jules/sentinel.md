## 2026-05-27 - [Bump dependencies]
**Vulnerability:** CVE-2026-45409 in `idna`, PYSEC-2026-161 in `starlette`, GHSA-39q2-94rc-95cp and multiple others in `dompurify`, XSS in `postcss` and others.
**Learning:** Security updates triggered an audit failure during CI on the previous check-in. The backend required bumping `idna`, `starlette`, and updating the `fastapi` compatibility pin. The frontend required pinning overrides for `postcss`, `brace-expansion`, `ws`, and upgrading `dompurify`.
**Prevention:** Regularly check `uv run --with pip-audit -- python scripts/pip_audit_guard.py` and `pnpm audit` before committing to avoid CI failures from vulnerable dependencies. Update test dependencies dict accordingly.
**Amendment:** When pinning pnpm overrides to resolve audit failures, use exact versions (e.g. `5.0.6`) instead of ranges (`>=5.0.6`). The frontend `test_dependency_security.ts` test compares the exact string with `compareVersions` which crashes with `NaN` when parsing ranges.
