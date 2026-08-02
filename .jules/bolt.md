## 2024-08-02 - Optimize SQLAlchemy Count Queries
**Learning:** In SQLAlchemy, calling `.count()` on filtered query objects (e.g. `db.query(Model).filter(...).count()`) wraps the query in a subquery `SELECT count(*) FROM (SELECT ...)`, which is inefficient. Using `db.scalar(select(func.count(Model.id)).where(...))` directly computes the aggregate, preventing this overhead.
**Action:** When implementing or optimizing scalar aggregates for simple filtered queries, replace `db.query(...).count()` with `db.scalar(select(func.count(Model.id)).where(...))`.
