## 2024-05-23 - Avoiding N+1 Queries with Scalar Subqueries
**Learning:** Using `get_last_activity_map` to fetch related data for a list of items introduces an N+1 (or 1+1) query pattern. While better than N+1 loop, it still requires an extra database round-trip.
**Action:** Use a correlated scalar subquery (`db.query(func.max(...)).correlate(Parent).scalar_subquery()`) within the main query to fetch the aggregate value in a single round-trip. Use `add_columns` to include this value in the result set.
