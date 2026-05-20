## 2024-05-20 - [idna CVE-2026-45409 vulnerability]
**Vulnerability:** The `idna` package version 3.11 is vulnerable to CVE-2026-45409. This vulnerability was flagged by `pip-audit`.
**Learning:** Security updates to standard libraries, such as `idna`, are critical and enforced by our `test_dependency_security.py` checks as well as our `pip_audit_guard.py` script.
**Prevention:** Pin the exact patched version (`==3.15`) in `pyproject.toml` using `uv add "idna==3.15"` and explicitly list it in `expected_exact_pins` in `tests/test_dependency_security.py`.
