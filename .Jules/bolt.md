## 2024-05-23 - SQLAlchemy Count Optimization
**Learning:** When using SQLAlchemy's `joinedload` for eager loading relationships, `query.count()` might still include the joins in the count query, leading to unnecessary overhead. Always construct a separate count query using `with_entities(func.count(Model.id))` on the base query *before* applying eager loading options or sorting.
**Action:** Review other list endpoints for similar patterns where `count()` is called on a query with heavy `joinedload` options.
