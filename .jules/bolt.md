## 2025-02-20 - [Performance] Optimizing SQLAlchemy count queries
**Learning:** In SQLAlchemy, using `.count()` on filtered query objects (e.g., `db.query(Model).filter(...).count()`) generates inefficient subqueries (e.g., `SELECT count(*) FROM (SELECT ...)`).
**Action:** Replace `.count()` calls on simple filtered queries with `db.scalar(select(func.count(Model.id)).where(...))` to directly generate an optimized aggregate count query (`SELECT count(id) FROM ... WHERE ...`).
