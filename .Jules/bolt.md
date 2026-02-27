# Bolt's Journal

## 2024-05-22 - [Example Entry]
**Learning:** [Insight]
**Action:** [How to apply next time]

## 2025-05-23 - Search Performance
**Learning:** The global search implementation uses `UNION ALL` across multiple tables (surrogates, notes, attachments, intended parents) but applies `LIMIT` and `OFFSET` *after* the union. This causes the database to materialize all matching rows from all subqueries before sorting and limiting, which is inefficient for broad queries.
**Action:** Push `LIMIT` (specifically `limit + offset`) down into each subquery to reduce the intermediate result set size before the final merge and sort. This is a classic "top-N" optimization pattern for distributed or union-based queries.
