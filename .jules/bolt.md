## 2024-05-18 - Avoid redundant count queries in pagination
**Learning:** In the `apps/api` SQLAlchemy endpoints, calculating both total counts and paginated results simultaneously by manually calling `.count()` on the base table results in a redundant database round-trip.
**Action:** When performing pagination, use the `paginate_query_by_offset` utility from `app.utils.pagination` to automatically eliminate the redundant `.count()` query when the fetched items list length is less than the requested limit.
