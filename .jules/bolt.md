## 2024-04-02 - Eliminate Redundant Count Queries
**Learning:** In backend service endpoints that need both a total count and group-by statistics (like `get_match_stats`), executing a separate `.count()` query alongside the `GROUP BY` query is an unnecessary database round-trip.
**Action:** Always compute the overall total by summing the results of the `GROUP BY` query in memory (`sum(counts.values())`) instead of querying the database twice.
