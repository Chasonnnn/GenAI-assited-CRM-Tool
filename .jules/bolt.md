## 2024-05-20 - N+1 in campaign stage filter normalization
**Learning:** Found O(N) database query operations in the `normalize_filter_criteria` function where it fetches pipeline stages via `pipeline_service.get_stage_by_id(db, stage_id)` and inline queries in multiple loops.
**Action:** Used bulk `in_` queries before the loops, creating an in-memory dictionary cache to dramatically speed up stage validation when there are multiple stages.
