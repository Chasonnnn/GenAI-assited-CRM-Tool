## 2024-06-28 - Optimize SQLAlchemy Count Queries
**Learning:** In SQLAlchemy, calling `.count()` directly on a query object (`db.query(Model).filter(...).count()`) wraps the main query in a subquery (e.g., `SELECT count(*) FROM (SELECT ...)`) which is inefficient.
**Action:** Use `db.scalar(select(func.count(Model.id)).where(...))` instead to generate a direct `COUNT` aggregate.
