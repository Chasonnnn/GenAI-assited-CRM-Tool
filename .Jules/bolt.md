# Bolt's Journal

## Daily Optimizations

## 2025-02-17 - [Optimizing intermediate materialization in UNION ALL queries]
**Learning:** In SQLAlchemy 2.0, when constructing a `UNION ALL` query using multiple `select()` statements across different tables, you can use `stmt.selected_columns` to order by newly selected aliases or aggregates (like rank or score) within the inner queries *before* wrapping them in a subquery or passing them to the union. By pushing down `.order_by(...).limit(...)` to the inner `stmt` instead of wrapping the entire inner select in a `subquery()` and ordering/limiting the outer select, you avoid forcing the database engine to materialize thousands of text search rows in memory before applying the limit.
**Action:** When working on paginated or bounded global search services that aggregate data with `UNION` or `UNION ALL`, apply sorting and limits (using `limit + offset`) directly to the base `select` branch before performing union operations to drastically improve speed.
