## 2025-02-19 - FastAPI UploadFile Memory DoS
**Vulnerability:** Reading `UploadFile` content using `await file.read()` loads the entire file into memory, causing potential memory exhaustion (DoS) with large files.
**Learning:** `UploadFile` wraps `SpooledTemporaryFile`. While it spools to disk, `read()` returns bytes in memory.
**Prevention:** Use `await run_in_threadpool(file.file.seek, 0, 2)` to check the file size from the underlying file object without loading content. Pass `file.file` (file-like object) to services instead of bytes.
