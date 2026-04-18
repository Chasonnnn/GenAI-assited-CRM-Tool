## 2024-05-18 - [Eliminated Unnecessary Database Counts in Pagination]
**Learning:** Found multiple instances where `total = query.count()` was blindly called before fetching pagination results, even if the result size was known (e.g. less than the limit, meaning we're on the last page or the only page). This led to an N+1 issue for counts across many services.
**Action:** Implemented a pagination optimization pattern (`if len(items) < limit...`) that conditionally calculates the total count from the fetched items length, skipping the expensive `COUNT(*)` query when unnecessary.
