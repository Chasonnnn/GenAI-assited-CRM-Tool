## 2025-02-28 - Avoid NameError with Missing SQLAlchemy Import
**Learning:** When using `db.execute(select(...))` to eliminate N+1 queries, verify that `select` is explicitly imported from `sqlalchemy`. Relying only on `Session` imports is insufficient and causes critical runtime `NameError` exceptions on API endpoints.
**Action:** Always verify imports (using `ruff check` or AST-based searches) when refactoring repository code to use the `select()` pattern.
