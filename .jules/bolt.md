## 2024-05-18 - Replacing SQLAlchemy .count() with db.scalar
**Learning:** Legacy SQLAlchemy `.count()` generates inefficient subqueries (e.g. `SELECT count(*) FROM (SELECT ...)`). Using `db.scalar(select(func.count(Model.id)).where(...))` natively in SQLAlchemy 2.0 avoids this subquery and performs better.
**Action:** Always prefer `db.scalar(select(func.count(Model.id)))` for simple counted queries to reduce database CPU load and query execution time. Remember to add comments explaining the performance optimization.
