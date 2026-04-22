
## 2024-05-24 - [Performance] Deferring Paginated Count Queries
**Learning:** Performing a naive `.count()` before fetching paginated records is an inefficient anti-pattern, particularly on expensive analytical or heavily filtered queries.
**Action:** Replace `total = query.count()` followed by `.limit().offset().all()` with the centralized `paginate_query_by_offset(query, offset=offset, limit=limit)` utility, which calculates total intelligently and avoids executing the `.count()` round-trip to the database entirely if the fetched result set is smaller than the limit (e.g. on partial last pages or small tables).
