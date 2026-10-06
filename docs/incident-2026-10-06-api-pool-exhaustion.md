# CRM API connection-pool exhaustion, October 6, 2026

The match activity query repeatedly scanned the audit table, holding API connections and exhausting the small request pool.
The local correction materializes the authenticated tenant's case-audit lookup once per request.
The corrected SELECT completed in 369.92 milliseconds against production data under a read-only diagnostic session.
The original SELECT exceeded the same five-second statement limit.
The application fix has not been deployed.

## Confirmed evidence

- Project: `probable-dream-484923-n7`; region: `us-central1`.
- Revision `crm-api-00263-4qg` receives 100% of API traffic.
- Its image digest is `sha256:77423bd8d273bc2f1d3d07da6ac5aa48027d698217205f1753a6292104a74be7`.
- Cloud Build `3c99225b-1813-44fa-974b-96ed03a8d654` maps that image to commit `7fddce14a5653340281ac2b97a86d81901556c81`, release `0.91.82`.
- Each API process permits two database connections, zero overflow, and a five-second pool wait.
- Each instance runs two API processes. Cloud Run permits 80 concurrent requests and at most two instances.
- Cloud SQL has one `db-g1-small` instance, `crm-db`, containing `crm` and the default `postgres` database.

Cloud Logging application errors were queried from `19:30:00Z` through, but excluding, `20:15:00Z`.
The query selected this API revision, severity ERROR or higher, and excluded request logs.
It returned 669 entries with a 10,000-entry limit; the limit was not reached.
Of these, 423 contained the two-connection QueuePool timeout fingerprint.
These are log entries, not distinct failed requests.
Authentication lookup and isolated system-alert persistence dominate the exception frames.

Request logs from `19:50:00Z` through, but excluding, `20:18:00Z` contained 261 HTTP 500s and three HTTP 504s.
The 10,000-entry limit was not reached.
All three HTTP 504s were GET requests to `/matches/{match_id}/work`, lasting approximately 300 seconds.
Other completed GET requests to that route took 36.49, 299.54, 119.27, and 192.11 seconds.

The last request-log query covered `20:25:00Z` through, but excluding, `20:31:00Z`.
At retrieval, it contained 216 entries, including 104 HTTP 500s; the latest entry was `20:30:28Z`.
This window was not complete at retrieval and does not establish recovery.

Monitoring covered `19:30:00Z`–`20:25:00Z`, with available samples through `20:22:00Z`.
CPU utilization peaked at 86.85%; memory utilization ranged from 49.85% to 55.06%.
CPU remained near 50% during many failures.
These readings do not distinguish a CPU-heavy query, lock contention, or a poor query plan.

## Query-plan evidence

The approved diagnostic job ran inside the existing API network using the deployed image and service account.
It enforced read-only transactions, five-second statements, and a one-second lock wait.
Outputs excluded query text, credentials, record identifiers, and customer records.

| Execution | Observation |
| --- | --- |
| `crm-db-diagnostic-20261006-ztmrx` | Database limit: 50 connections. Approximately 407,858 audit rows. Seven idle connections; no blockers at sampling. |
| `crm-db-diagnostic-20261006-vbjgs` | Original query: seven audit scan nodes, including scans nested beneath participant activity loops. EXPLAIN ANALYZE stopped with SQLSTATE `57014` after five seconds. |
| `crm-db-diagnostic-20261006-ncqrm` | Corrected query: one parallel audit scan; EXPLAIN ANALYZE completed in 369.92 milliseconds. |

The plan samples selected three surrogate matches with the largest participant histories: 128, 128, and 125 activity rows.
Only the first sample executed EXPLAIN ANALYZE; the other samples used EXPLAIN without execution.
The original planner estimated one participant row and chose repeated nested-loop anti-joins against the much larger audit table.
The corrected plan materializes tenant-scoped match audits and reuses that result for case activity and deleted-work provenance checks.
The executions were sequential, not simultaneous; this is a bounded query benchmark, not an endpoint load test.
Cloud Logging retrieval returned all 20 diagnostic entries without pagination.

The observed connection limit and memory readings do not justify increasing the API pool without a connection budget.
The query defect should be released before reassessing capacity under normal traffic.
No database migration, index creation, network change, or capacity change is required for this correction.

## Local verification

- The regression fixture contains 400,000 unrelated audits, 800 case audits, and 128 participant activity rows.
- Before the fix, the request's SELECT plans visited approximately 103.8 million audit rows and failed the bounded-work assertion.
- After the fix, the measured work fell to approximately 0.8 million audit rows across the request's SELECTs.
- The regression measures executed plan work rather than machine-dependent elapsed time.
- All 31 tests in `test_match_work.py`, `test_match_cases.py`, and `test_tasks_match_scope.py` passed.
- Coverage includes repeated cases, attempts, deleted-work provenance, cross-tenant references, denied operations, and CSRF.
- Ruff lint and formatting checks passed for all changed Python files.
- The initial 20,000-row experiment did not reproduce the incident and was removed.

Each test invocation created, migrated, and dropped a disposable local PostgreSQL database.
Existing local database containers were preserved.

## Operational status

Only the diagnostic job ran in production. The API revision and traffic allocation remain unchanged.
The corrected SQL ran as a read-only benchmark; this does not establish deployed application recovery.
The diagnostic job was deleted after its results were collected.
No task-owned servers or proxies remain running.

The installed gcloud version failed to decode mixed nested arrays in structured log output.
The diagnostic helper now emits named row objects; deeply nested plan output was parsed from JSON stdout through the Logging API.
Cloud authentication remained guarded by the repository's authmux context.

## Checkout

The clean checkout was switched to `main` as requested.
Local `main` and `origin/main` have diverged: 23 local-only and five remote-only commits.
Neither history was reset, rebased, or merged.
An unrelated `apps/web/.e2e/` directory appeared during diagnosis and was preserved.
