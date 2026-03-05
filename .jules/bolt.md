## 2024-05-18 - [Optimizing global search query performance]
**Learning:** Found an opportunity to improve the global search performance by utilizing the 'Performance Pattern' regarding `UNION ALL` with global searches.
**Action:** When performing global searches using `UNION ALL` across multiple tables, apply `ORDER BY` and `LIMIT` (specifically `limit + offset`) to each subquery to prevent materializing excessive intermediate rows before the final sort.

## 2024-05-18 - [Optimizing data overfetching for aggregate statistics]
**Learning:** Found that multiple redundant `useMatches` queries filtering by status were used to compute stats on a page, causing data overfetching.
**Action:** Replace filtered list queries with a dedicated stats hook (`useMatchStats`) backed by an optimized `GROUP BY` endpoint to retrieve aggregate values.
