
## 2024-09-01 - Bulk fetching Campaign stages to resolve N+1 Queries
**Learning:** In SQLAlchemy 2.x, repeating single-entity lookups (such as `db.query(PipelineStage).filter(...)`) inside a loop over IDs introduces N+1 performance bottlenecks.
**Action:** Extract the keys into a list, perform a single bulk fetch using the `.in_()` operator outside the loop, and use an in-memory dictionary for O(1) lookups during iteration to reduce database CPU load and network chatter.
