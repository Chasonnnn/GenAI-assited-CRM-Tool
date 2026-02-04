## 2025-01-30 - Insecure File Upload via Extension Spoofing

**Vulnerability:** Public form submissions allowed uploading executable files (e.g., `.exe`) if the `Content-Type` header was spoofed to a permitted type (e.g., `application/pdf`). The `_validate_file` function only checked the user-provided `Content-Type` against the allowlist, ignoring the file extension.

**Learning:** Trusting user-provided `Content-Type` headers without cross-referencing file extensions or magic numbers is a critical security gap. It enables attackers to bypass MIME type restrictions and upload malware.

**Prevention:**
1. Always validate file extensions against a blocklist of executable types (`.exe`, `.sh`, `.php`, etc.).
2. Cross-reference the file extension with the allowed MIME types using `mimetypes.guess_type`. If they mismatch (e.g., `.exe` maps to `application/x-msdownload` but allowlist is `application/pdf`), reject the upload.
3. Use a "defense in depth" approach: Block dangerous extensions AND enforce MIME type consistency.
