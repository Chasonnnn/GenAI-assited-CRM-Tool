## 2024-03-24 - SQL LIKE Injection in Search Queries
**Vulnerability:** User input was directly used in SQL `LIKE` and `ILIKE` queries without escaping wildcard characters (`%` and `_`). This allows users to craft search queries that perform expensive full-table scans (DoS vector) or return unexpected results by manipulating the wildcard pattern.
**Learning:** SQLAlchemy's parameter binding protects against SQL injection (changing query structure) but does NOT automatically escape wildcard characters within the bound string.
**Prevention:** Always sanitize user input intended for `LIKE`/`ILIKE` queries using a dedicated escaping function (e.g., `escape_like_string`) that escapes `%`, `_`, and the escape character itself (default `\`).
