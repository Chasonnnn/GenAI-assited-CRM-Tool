
## 2024-06-24 - Optimize SQLAlchemy count queries
**Learning:** In SQLAlchemy, calling `query.count()` executes an inefficient subquery (`SELECT count(*) FROM (SELECT ...)`). Using `db.scalar(select(func.count(Model.id)).where(...))` emits a more efficient, direct `SELECT count(id)` query. The PR review noted that I should always add a code comment explaining the performance optimization, even for small refactors.
**Action:** Replace legacy `query.count()` with `select(func.count())` when aggregating counts, and ensure that a comment documenting the optimization reason is added directly in the code above the change.
