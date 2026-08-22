## 2025-03-09 - N+1 query optimized in messaging_delivery_service.py
**Learning:** Found an N+1 query loop when resolving expired delivery leases where attempts and reconciliation cases were checked individually per lease.
**Action:** Bulk pre-fetched items matching the delivery ID batch and used in-memory dictionary/set lookups. Note: `db.execute(select(...).where(...)).scalars()` was used to materialize the query into Python iterables.
