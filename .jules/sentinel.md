## 2024-05-18 - Pin pillow dependency to fix CVE-2026-40192
**Vulnerability:** CVE-2026-40192 flagged by `pip-audit` for `pillow` version 12.1.1.
**Learning:** `pillow` dependency needs to be pinned exactly using `==` to fix security vulnerabilities, rather than relying on `>=`, as checked by `apps/api/tests/test_dependency_security.py` and `scripts/pip_audit_guard.py`.
**Prevention:** When upgrading vulnerable dependencies in `apps/api`, always pin the fixed version exactly (e.g., `uv add "pillow==12.2.0"`) and update the `expected_minimums` dictionary in `apps/api/tests/test_dependency_security.py`.
