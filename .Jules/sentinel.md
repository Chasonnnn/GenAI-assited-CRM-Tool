## 2026-10-02 - [SQL Wildcard Injection in Search Fallback]
**Vulnerability:** Found unescaped user input passed directly to `.ilike()` in the search fallback function.
**Learning:** Developer neglected to use the standard `escape_like_string` helper function on fallback lookup.
**Prevention:** Always escape user input when passed to `LIKE`/`ILIKE` and specify `escape='\'` in SQLAlchemy.
