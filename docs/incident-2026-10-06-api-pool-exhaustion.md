# CRM API connection-pool exhaustion, October 6, 2026

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

## Local verification

- All 15 existing match-work tests passed against a migrated, disposable PostgreSQL database.
- A temporary experiment inserted 20,000 audit records and 1,000 activity records.
- After ANALYZE, its match-activity query completed in 13.055 milliseconds.
- That experiment did not reproduce the incident and was removed rather than retained as a misleading regression test.
- The relevant deployed database, dependency, alert, and match-work files match the local versions inspected.

## Pending diagnosis

Pool exhaustion is confirmed. The reason match-work requests hold connections for minutes remains unconfirmed.
The query is a stronger investigation target than changing pool size without a database connection budget.
No application fix or production configuration change has been made.

The database has no public IP. Local Cloud SQL Auth Proxy attempts could not reach it.
Those task-owned proxies were stopped. No network access controls were changed.

`scripts/diagnose_db_contention.py` reports settings, query wait categories, blockers, and table statistics.
It enforces read-only transactions, five-second statements, and a one-second lock wait.
It does not print query text, credentials, or customer records.
Local execution verified these connection settings. Ruff passed.

A prepared temporary Cloud Run job uses the deployed API image and existing API service account/network.
It has one task, zero retries, a 60-second deadline, one CPU, and 512 MiB of memory.
It has no HTTP ingress or schedule and references the existing database secret.
Creating and executing that job requires explicit authorization under the repository deployment rule.
The job should be deleted after its sanitized output is collected.

## Checkout

The clean checkout was switched to `main` as requested.
Local `main` and `origin/main` have diverged: 23 local-only and five remote-only commits.
Neither history was reset, rebased, or merged.
An unrelated `apps/web/.e2e/` directory appeared during diagnosis and was preserved.
