## 2023-10-24 - N+1 Query in Bulk Lease Recovery
**Learning:** Found an N+1 query pattern in `recover_expired_delivery_leases` where attempting to recover leased deliveries fetched attempts and reconciliation cases one by one inside a loop.
**Action:** Replaced iterative queries with single O(1) bulk fetch queries and `.in_()` filtering, using dictionaries to map the attempts and cases for fast lookup during the loop, turning O(N) database time into O(1).
