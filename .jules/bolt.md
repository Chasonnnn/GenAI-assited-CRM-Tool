## 2024-05-15 - [Database Count Elimination in Pagination]
**Learning:** Found a classic N+1-like issue where `paginate_query` was unnecessarily running `.count()` queries on small or final pages.
**Action:** Always verify if a secondary count query can be inferred from the limit/offset of the primary fetched page, especially in standard paginator utilities.
