# API timeout investigation — September 11, 2026

## Finding

Google Tasks synchronization can deadlock the API event loop when task-list requests for the same user overlap. The mechanism was reproduced against PostgreSQL with the deployed source. Production logs identify the same membership lock and connect all nine September 10 timeouts to requests that remained open until September 11.

The precise lock owner and process stacks were not captured during the incident. The evidence supports this mechanism; it does not establish the origin of the later database connection reset.

## Production evidence

- Project: `probable-dream-484923-n7`; region: `us-central1`.
- API revision: `crm-api-00238-rdc`; request timeout: 300 seconds; four Uvicorn processes; one observed container instance across the incident windows.
- Image digest: `sha256:214818f5b8428dc898a5ebb7e55986ac87415fbe2f601d0d809a1c24006876e7`.
- Cloud Build `3d2b5203-fb38-4bba-907c-1efabebd27d1` maps that image to commit `3abe0c1a446308bd6d81dce2e1fde966dea42615`, tag `surrogacy-crm-platform-v0.91.62`.
- All nine requests belong to one authenticated user and organization. No identity or request payload is included here.

| Request start, September 10, UTC | Requests | Cloud Run response | Application completion, September 11, UTC |
| --- | ---: | --- | --- |
| 16:47:55 | 2 | 504 after approximately 300 seconds | 11:09:40–11:09:50 |
| 19:39:03 | 5 | 504 after approximately 300 seconds | 11:09:40 |
| 22:31:59 | 2 | 504 after approximately 300 seconds | 11:09:40–11:09:50 |

Trace identifiers match each timeout to a later `api_request_completed` event. Application durations range from 45,461,316 to 66,115,505 milliseconds: approximately 12.6–18.4 hours. Four task-list requests ended with application status 500; the other five ended with application status 200, too late to reach the original client.

At 11:09:22–11:09:24 UTC, three Google Tasks synchronization warnings contain `OperationalError`, `server closed the connection unexpectedly`, and a `memberships ... FOR UPDATE` query. A fourth synchronization warning follows at 11:09:30. Cloud SQL recorded lost client connections beginning at 11:09:21. The later permission-query stack frames describe where task processing failed after synchronization returned; they do not identify the original wait.

Other requests continued succeeding during all three timeout windows. The 706 non-WebSocket request logs in those windows contain these nine failures and successful requests with observed latencies below 2.1 seconds. This was a partial failure, not a complete service outage.

## Mechanism in deployed code

1. `task_service.list_tasks` pulls Google Tasks before reading the task list.
2. `sync_google_tasks_for_user` calls `run_async(..., timeout=45)` from a FastAPI worker thread.
3. `run_async` uses `anyio.from_thread.run`, placing the coroutine on the API event loop.
4. `_sync_google_tasks_for_user_async` executes a synchronous membership `SELECT FOR UPDATE`, then awaits provider I/O while the transaction retains that lock.
5. A concurrent synchronization for the same membership runs its synchronous lock query on the same event loop. It waits for the first transaction, but the first coroutine cannot resume to complete and release the lock while that loop is blocked.

The cooperative 45-second timeout cannot interrupt a synchronous database wait on its own event loop. The request database engine has no configured statement or lock timeout. Cloud Run's 300-second timeout closes the external request but does not terminate the application operation. [Cloud Run timeout behavior](https://docs.cloud.google.com/run/docs/configuring/request-timeout)

## Local reproduction

- Used an archive of the deployed commit, the existing Python 3.14.6 environment, and a disposable PostgreSQL 18.1 container bound only to localhost.
- Created synthetic users and memberships. Used the actual sync wrapper, membership authorization query, row lock, SQLAlchemy session, and AnyIO bridge.
- Mocked only integration/provider access. The provider coroutine waited 150 milliseconds and returned without making an external call.
- Started two sync requests through AnyIO worker threads, 30 milliseconds apart. Each request owned a separate database session and transaction.
- An independent watchdog inspected `pg_stat_activity` and canceled only the blocked synthetic query after 1.5 seconds, preventing an indefinite test hang.

| Case | Total duration | Largest event-loop heartbeat gap | Database lock wait | Watchdog cancellation |
| --- | ---: | ---: | --- | --- |
| Different users | 0.275 s | 0.112 s | No | No |
| Same user | 1.534 s | 1.490 s | Yes | Yes |

The relevant AnyIO, SQLAlchemy, psycopg, and FastAPI dependency pins match the deployed manifest. The local Google SDK and grpc versions differ; provider calls were mocked and those SDK paths were not exercised. The reproduction validates the concurrency failure, not the complete production deployment or the source of the connection reset.

## Proposed correction

1. Remove Google Tasks synchronization from task-list reads. Return the persisted CRM task list and use the existing `GOOGLE_TASKS_SYNC` job scheduled in five-minute buckets. This changes Google-to-CRM refresh from page-load synchronization to background synchronization.
2. Keep synchronous database work off the event loop in the background sync path. The existing job handler also acquires the membership lock before awaiting synchronization, so moving work to that handler alone is insufficient.
3. Bound lock waits within the sync operation and preserve active-membership authorization, transaction ownership, rollback, and retry behavior. Avoid applying an unreviewed global timeout to imports, exports, migrations, or unrelated jobs.
4. Add PostgreSQL concurrency regressions for same-user sync, different-user sync, and membership revocation during sync. Verify that the API heartbeat remains responsive and failed or skipped work is retried safely.

Application changes, deployment, and post-deployment verification remain pending.

## Query coverage

The main window was `[2026-09-10T15:51:27Z, 2026-09-11T15:51:27Z)`. Queries used `resource.type="cloud_run_revision"`, the CRM service names, and separate request/application streams. The full request query returned 8,777 records below its 100,000-record cap. The 5xx query returned nine records below its 1,000-record cap. Correlation used the nine request traces and application `trace_id` fields within that window.

Detailed comparison windows were `[16:45,16:55)`, `[19:36,19:47)`, and `[22:29,22:39)` UTC on September 10. The non-WebSocket request query returned 706 records below its 10,000-record cap. A broad four-minute application-log sample around recovery hit its 1,500-record cap and was used only for exploration; it does not support absence-of-event claims. The focused recovery warning query returned 14 records below its 1,000-record cap.

Counts describe records returned by Cloud Logging. Logging exclusions, retention, or ingestion gaps can limit coverage. Raw messages, query parameters, provider credentials, and personal identifiers were not saved to this report. No production configuration or data was changed. The disposable database and temporary reproduction files were removed after verification.
