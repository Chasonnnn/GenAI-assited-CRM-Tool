# Bolt's Journal

## 2025-05-27 - [Bulk Operations N+1 Optimization]
**Learning:** Bulk operations like `bulk_assign_surrogates` iterate over IDs and perform individual `get_surrogate` queries, causing N+1 issues.
**Action:** Always fetch entities in bulk using `id.in_()` at the start of the loop and map them by ID for O(1) access.
