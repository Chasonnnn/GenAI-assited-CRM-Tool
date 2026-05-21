## 2024-05-21 - [Batching count queries with filters]
**Learning:** When retrieving multiple count statistics with different conditions on the same base table (e.g., pending tasks vs overdue tasks), executing separate `.count()` queries results in redundant database round-trips.
**Action:** Use conditional aggregation in a single SQLAlchemy query (e.g., `db.query(func.count(Model.id), func.count(Model.id).filter(condition))`) to retrieve all counts in one round-trip.
