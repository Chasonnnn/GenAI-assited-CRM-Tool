## 2024-07-24 - SQLAlchemy Count Query Optimization
**Learning:** Using `db.query(Model).filter(...).count()` in SQLAlchemy generates inefficient subqueries (e.g., `SELECT count(*) FROM (SELECT ...)`).
**Action:** Replace `.count()` with `db.scalar(select(func.count(Model.id)).where(...))` for direct, optimized aggregate counts. This significantly reduces database CPU load and query execution time.
