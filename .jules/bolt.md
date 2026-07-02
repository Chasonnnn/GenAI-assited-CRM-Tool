## 2024-07-02 - SQLAlchemy Count Query Optimization
**Learning:** Using `db.query(Model).filter(...).count()` generates inefficient subqueries (e.g., `SELECT count(*) FROM (SELECT ...)`). Using `db.scalar(select(func.count(Model.id)).where(...))` produces a direct, optimized aggregate count, significantly reducing database CPU load and query execution time.
**Action:** Replace `db.query(...).count()` with `db.scalar(select(func.count(...)))` for performance-critical count queries to optimize database performance.
