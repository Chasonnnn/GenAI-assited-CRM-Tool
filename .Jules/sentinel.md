## 2026-09-27 - Unescaped SQLAlchemy ilike Vulnerability
**Vulnerability:** SQL injection via unescaped LIKE wildcard characters in SQLAlchemy ilike calls.
**Learning:** The SQLAlchemy ilike method requires explicitly escaping wildcard characters (%, _) via escape_like_string and passing escape='\\', otherwise user input can act as wildcards, causing full table scans or logic bypasses.
**Prevention:** Always use escape_like_string on user input and add escape='\\' when using ilike or like in SQLAlchemy queries.
