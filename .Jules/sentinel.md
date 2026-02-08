## 2026-02-08 - [DoS Vulnerability in File Upload]
**Vulnerability:** Unrestricted file upload size in CSV import preview endpoint allowed potential Denial of Service (DoS) via Out-Of-Memory (OOM) attacks. `await file.read()` loads the entire file into memory without checking size first.
**Learning:** Always validate file size *before* reading content into memory, especially for public or authenticated endpoints that accept file uploads. `UploadFile` in FastAPI/Starlette exposes `file.seek(0, 2)` and `file.tell()` to check size efficiently (if spooled).
**Prevention:** Enforce a maximum file size limit using `Content-Length` header (fast fail) and actual file size check (slow fail) before processing uploads. Use `MAX_IMPORT_SIZE` constants.
