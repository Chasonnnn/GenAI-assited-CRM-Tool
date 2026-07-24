## 2025-05-15 - [Dependency Security Update]
**Vulnerability:** pypdf versions prior to 6.14.0 were vulnerable to multiple CVEs (CVE-2026-59935 through CVE-2026-59938).
**Learning:** `test_dependency_security.py` strictly enforces explicit pinned versions (`==`) for dependencies rather than semantic version ranges, meaning dependency updates in `pyproject.toml` and `uv.lock` require synchronized updates to the security assertions in the test file.
**Prevention:** Always verify dependency version constraints and corresponding test assertions using `uv run --with pip-audit -- python -m pip_audit` and `pytest tests/test_dependency_security.py` when upgrading packages.
