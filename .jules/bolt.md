## 2024-05-24 - Conditional Aggregation for Multiple Counts
**Learning:** In SQLAlchemy, executing multiple `.count()` queries or raw SQL `COUNT(*)` queries on the same table with different conditions causes redundant database round-trips.
**Action:** Use conditional aggregation by combining them into a single query using `func.count(Model.id).filter(condition)` (which compiles to `COUNT(*) FILTER(WHERE ...)`) to fetch multiple counts efficiently in one round-trip.
## 2024-05-24 - CI Pip Audit Error Resolved
**Learning:** CI pip-audit checks can block performance optimizations.
**Action:** When a PR triggers a `pip-audit` failure, fix the dependency version exactly in `pyproject.toml` using `uv add` and update the test mappings in `apps/api/tests/test_dependency_security.py` to match the exact newly pinned versions.
