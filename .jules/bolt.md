
## 2026-03-12 - [Optimize global search limits]
**Learning:** In SQLAlchemy 2.0, applying `order_by` and `limit` to a `select` without wrapping it properly can cause it to be compiled as a subquery when placed inside a `UNION ALL`.
**Action:** Use `stmt.with_only_columns(*stmt.selected_columns)` before the `order_by().limit()` step inside `_apply_branch_limit()` to prevent the query builder from creating unnecessary outer SELECT queries. This improves the PostgreSQL planner's ability to natively optimize top-N sorts within a `UNION ALL` statement without materializing intermediate results.
