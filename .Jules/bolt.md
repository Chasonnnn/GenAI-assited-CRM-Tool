
## 2024-05-24 - Vectorizing N+1 Role Permission Backfills
**Learning:** In the permission service, backfilling role defaults across organizations (`backfill-permissions` CLI) iterated through each organization and performed an isolated database lookup inside `seed_role_defaults` for existing permissions, leading to an N+1 query vulnerability when managing numerous organizations.
**Action:** Encapsulate vectorized data-fetching into a `_bulk` service method (e.g., `seed_role_defaults_bulk`) using the `.in_()` operator to fetch necessary context for all iterations simultaneously, then perform the data insertion loop using an in-memory matching structure. This eliminates the database loop while preserving the architectural boundaries of the service layer.
