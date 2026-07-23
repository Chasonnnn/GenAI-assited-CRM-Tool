## 2024-07-23 - Efficient Database Count Queries
**Learning:** In SQLAlchemy, `db.query(Model).filter(...).count()` can generate inefficient subqueries (e.g., `SELECT count(*) FROM (SELECT ...)`) compared to using direct aggregate counting.
**Action:** Replace `db.query(...).count()` with `db.scalar(select(func.count(Model.id)).where(...))` to reduce database CPU load and query execution time for generic count statistics.
