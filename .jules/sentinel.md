## 2025-05-25 - Pinning exact vulnerable dependencies
**Vulnerability:** Found vulnerable dependencies idna and starlette. When using `uv add` to update starlette, it required updating fastapi to satisfy the constraints.
**Learning:** Using exact pins (`==`) is important in this project and enforced in `test_dependency_security.py`. When a parent dependency (like fastapi) restricts upgrading a child dependency (like starlette), both need to be pinned exactly.
**Prevention:** Use `uv add "fastapi==X.Y.Z" "starlette==A.B.C" ...` instead of trying to resolve them independently, and always update the exact pin in the test file.
