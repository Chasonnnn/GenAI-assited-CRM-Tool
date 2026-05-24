
## 2025-05-20 - Sub-Dependency Vulnerability Pinning
**Vulnerability:** CVE-2026-45409 (idna) and PYSEC-2026-161 (starlette)
**Learning:** `pip-audit` detected vulnerabilities in `idna` and `starlette` (a subdependency of FastAPI). Upgrading `starlette` via `uv add` failed initially because the existing pinned `fastapi` version had a strict bound (`starlette<0.51.0`).
**Prevention:** When upgrading sub-dependencies of strict frameworks like FastAPI, always check if the parent framework needs a version bump to support the newer, patched sub-dependency. In this case, `fastapi` needed to be updated to `0.136.3` to permit `starlette==1.0.1`.
