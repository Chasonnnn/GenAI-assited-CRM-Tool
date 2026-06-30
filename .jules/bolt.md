## 2024-06-30 - SQLAlchemy Pagination Counts
**Learning:** Using .count() directly on generic queries can generate inefficient subqueries or include sorting overhead. Replacing it with .order_by(None).count() safely strips sorting overhead.
**Action:** Use query.order_by(None).count() when resolving totals for pagination.
