## 2026-11-01 - Fix Path Traversal in Form Logo Local Path
**Vulnerability:** The get_form_logo_local_path function directly concatenated an untrusted storage_key without enforcing directory boundaries.
**Learning:** In python, os.path.join does not protect against path traversal (../), leading to arbitrary file read.
**Prevention:** Always use a safe path resolution utility like resolve_local_storage_path that enforces base directory boundaries using os.path.commonpath.
