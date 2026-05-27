## 2024-05-27 - [Eliminate redundant count queries]
**Learning:** In `analytics_surrogate_service.py`'s `get_summary_kpis`, there are 4 separate `.count()` queries on the `Surrogate` table to get current period, previous period, total active, and needs attention metrics. This creates unnecessary DB round trips.
**Action:** Use a single aggregation query with conditional logic (`case`) to retrieve all counts in one round trip for dashboard performance improvements.
