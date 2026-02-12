## 2025-02-14 - Fix DoS vulnerability in file upload
**Vulnerability:** Unrestricted file upload memory consumption. `await file.read()` reads the entire file content into memory, allowing attackers to cause a Denial of Service (DoS) by uploading large files.
**Learning:** `UploadFile` in FastAPI/Starlette exposes a `SpooledTemporaryFile` via `file.file`. This object supports `seek` and `tell`, allowing size validation without reading content. Using `shutil.copyfileobj` streams the file to disk/storage, keeping memory usage constant.
**Prevention:** Always validate file size using `seek(0, 2)` and `tell()` before processing uploads. Use streaming methods (`shutil.copyfileobj`) instead of reading entire files into memory.
