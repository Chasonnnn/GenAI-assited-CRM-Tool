## Performance Journal
## 2025-05-15 - Redundant count queries in SQLAlchemy pagination
**Learning:** Found manual `.count()` queries running sequentially prior to `.offset().limit().all()` in list endpoints (like `list_tasks`). These always issue a `SELECT count(*)` regardless of whether the current page fetch satisfies the limit boundary, causing a redundant database round-trip on sparse queries or the final page.
**Action:** Always utilize the existing helper `paginate_query_by_offset` inside `app.utils.pagination` because it resolves the total programmatically (using `len(items) < limit`) before falling back to the expensive DB count query, eliminating ~50% of the DB load on sparse pages.
