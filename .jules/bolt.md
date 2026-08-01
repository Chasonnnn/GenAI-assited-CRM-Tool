## 2024-05-18 - SQLAlchemy `.count()` Overhead
**Learning:** Using `query.count()` in SQLAlchemy 2.x wraps the original query in a subquery `SELECT count(*) FROM (SELECT ...)`, adding overhead to query compilation and execution. For simple filtered queries, using `db.scalar(select(func.count(Model.id)).where(...))` directly executes a targeted count without subquery wrapping.
**Action:** Replace `.count()` with `.scalar(select(func.count(Model.id)))` for standard model filtering queries to avoid unnecessary subquery overhead.
