## 2024-05-24 - N+1 optimization inside loop
**Learning:** Fixing N+1 queries in loop processing where each item requires fetching multiple related entities requires extracting keys, using bulk IN clauses for both tables, and caching lookups using tuples of foreign keys for precise matching.
**Action:** When finding multiple queries executed in a for-loop, fetch all relevant related entities beforehand into separate hash maps for O(1) in-loop lookup without querying the db.
