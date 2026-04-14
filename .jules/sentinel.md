## 2025-02-28 - Attachment Service Path Traversal
**Vulnerability:** Path Traversal in Local Storage Resolution
**Learning:** `os.path.join` does not prevent path traversal if the second argument is an absolute path or contains `../`. Local storage implementations for file attachments passed user-controlled `storage_key` strings directly to `os.path.join` with the base directory, making it possible to read, delete, or write files outside the intended attachment storage directory.
**Prevention:** Use a dedicated resolution function leveraging `os.path.abspath` and `os.path.commonpath` to enforce boundary constraints. Ensure paths resolved from user inputs never escape the designated base directory.
