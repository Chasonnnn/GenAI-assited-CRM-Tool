## 2024-05-24 - Conditional Aggregation for Multiple Counts
**Learning:** In SQLAlchemy, executing multiple `.count()` queries or raw SQL `COUNT(*)` queries on the same table with different conditions causes redundant database round-trips.
**Action:** Use conditional aggregation by combining them into a single query using `func.count(Model.id).filter(condition)` (which compiles to `COUNT(*) FILTER(WHERE ...)`) to fetch multiple counts efficiently in one round-trip.
