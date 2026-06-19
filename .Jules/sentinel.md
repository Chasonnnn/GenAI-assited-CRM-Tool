## 2025-05-20 - Dependency Security Version Pinning
**Vulnerability:** Vulnerable packages in `pyproject.toml`
**Learning:** The codebase enforces strict version pinning (`==`) in `apps/api/pyproject.toml` for critical dependencies, validated by `test_dependency_security.py`. When bumping a vulnerable dependency, you must explicitly update both the `pyproject.toml` constraint and the `expected_exact_pins` dictionary within the test file.
**Prevention:** Always check for related tests asserting version numbers when resolving dependency vulnerabilities.
