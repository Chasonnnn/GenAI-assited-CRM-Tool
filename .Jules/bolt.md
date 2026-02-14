## 2025-05-23 - Avoiding JoinedLoad in Count Queries
**Learning:** `base_query.count()` in SQLAlchemy inherits `joinedload` options from the base query, causing unnecessary LEFT JOINs and data fetching even for simple COUNT operations.
**Action:** For pagination, always construct a separate count query using `db.query(func.count(Model.id)).filter(*filters).scalar()` to ensure efficiency. Collecting filters in a list makes this reusable for both main and count queries.
