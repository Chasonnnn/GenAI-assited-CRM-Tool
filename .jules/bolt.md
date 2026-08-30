## 2024-12-07 - Fix N+1 query in meta_sync_service
**Learning:** Found an N+1 query inside a loop resolving MetaAd external IDs for surrogates. The codebase structure easily allows fixing this via bulk fetch and `ad_external_id` mapping.
**Action:** Replaced O(N) queries with single bulk fetch using `.in_()` operator, mapped results for O(1) lookup in loop.
