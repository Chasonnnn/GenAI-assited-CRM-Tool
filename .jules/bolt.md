## 2024-06-13 - Optimize SQLAlchemy count queries
**Learning:** In SQLAlchemy, `db.query(Model).filter(...).count()` generates inefficient subqueries (e.g., `SELECT count(*) FROM (SELECT ...)`). Using `db.scalar(select(func.count(Model.id)).where(...))` produces a direct, optimized aggregate count, significantly reducing database CPU load and query execution time.
**Action:** When performing count queries, avoid `db.query(Model).count()` and instead use `db.scalar(select(func.count(Model.id)).where(...))`.
