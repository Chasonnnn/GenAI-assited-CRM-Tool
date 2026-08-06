## 2025-05-24 - Optimized task_service N+1 query
**Learning:** Found an N+1 query in `task_service.py` (`invalidate_pending_approvals_for_surrogate`) where `db.query(WorkflowExecution)` was being called inside a loop over `pending_tasks`.
**Action:** Bulk fetched the `WorkflowExecution` models and mapped them in memory before iterating over the `pending_tasks`. Used a set to deduplicate IDs before the query, and added comments documenting the O(N) to O(1) impact.
