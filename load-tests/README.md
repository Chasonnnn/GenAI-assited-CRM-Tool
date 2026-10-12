# Load Tests

Run k6 load tests for core workflows (surrogates, tasks, dashboard, automation, search).

## Match history under dashboard traffic

From `apps/api`:

```sh
mise exec -- uv run python -m scripts.benchmark_match_dashboard
```

Requires Docker and k6. The runner creates an isolated PostgreSQL 18.1 container,
applies migrations, and seeds four synthetic repeated matches with treatment attempts.
The dataset includes 400,000 unrelated audit rows, 3,200 previous-case events, and 512 participant events.
Bulk audit rows model legacy history without hash-chain entries, matching the existing query-plan regression fixture.
It starts two API workers with two connections each and no pool overflow.
Three match users run beside two dashboard users for two minutes.

The test checks current-case, previous-case, and attempt history. All requests must succeed,
history must be populated, and each flow must meet an 800 ms p95 budget.
The budget is an initial regression threshold, not a production capacity claim.
Authentication uses a temporary MFA-verified synthetic administrator session.
No worker process sends email or calls an AI provider.

```sh
mise exec -- uv run python -m scripts.benchmark_match_dashboard \
  --duration 5m --audit-rows 1000000 --match-vus 6 --dashboard-vus 4
```

`--workers`, `--pool-size`, and `--p95-ms` support controlled comparisons.
Keep the workload and database size fixed when comparing a query or index change.
This fixed-user test measures contention; it does not establish maximum sustainable arrival rate.
The small participant population targets audit-history contention, not high-cardinality dashboard aggregation.

Each run writes an ignored `load-tests/results/<timestamp>/` directory:

- `k6-summary.json`: latency, request failures, checks, and completed history requests by scope.
- `database.json`: query fingerprints, normalized SQL, execution time, calls, buffer activity, and temporary writes.
- `run.json`: workload, tool version, Git revision, pool settings, and pool timeout error count.

The runner enables `pg_stat_statements` only in its new container and resets counters after seeding.
Database execution time excludes application connection-pool waiting and response serialization.
HTTP latency and pool timeout counts expose contention; they do not measure pool wait duration directly.
The runner deletes its database, API processes, synthetic session, and temporary files after each run.
It does not use an inherited database URL or modify either existing development database.

For an existing synthetic staging fixture, run `k6-match-dashboard.js` directly with
`BASE_URL`, `AUTH_COOKIE`, and `FIXTURE_FILE`. The fixture is a JSON array with
`match_id`, `previous_match_id`, and `attempt_id` for each repeated match.
Use `ALLOW_FORBIDDEN=0`; authorization failures invalidate this benchmark.

## Local query adviser

pgAssistant 3.8.4 is pinned by image digest. From the repository root:

```sh
export PGASSISTANT_SECRET_KEY="$(openssl rand -hex 32)"
docker compose -f load-tests/compose.pgassistant.yml up -d
```

The UI is at `http://127.0.0.1:8088`. Connect to a synthetic development or staging database.
For a database on this Mac, use `host.docker.internal` as the database hostname.
AI-provider access is disabled in this configuration. Query and index analysis remains available.
Review suggested SQL before applying it. The benchmark database exists only while its runner is active.

```sh
docker compose -f load-tests/compose.pgassistant.yml down
unset PGASSISTANT_SECRET_KEY
```

## Prereqs
- `k6` installed (https://k6.io/docs/get-started/installation)
- API server running
- An authenticated session cookie (and CSRF cookie if you want to test mutations)

## Usage

Export cookies from your browser (DevTools -> Application/Storage -> Cookies):

```
export AUTH_COOKIE='crm_session=YOUR_SESSION_TOKEN; crm_csrf=YOUR_CSRF_TOKEN'
```

Run the core flow test:

```
k6 run load-tests/k6-core-flows.js
```

You can override base URL:

```
BASE_URL=http://localhost:8000 k6 run load-tests/k6-core-flows.js
```

## What This Script Covers

`load-tests/k6-core-flows.js` simulates:
- Surrogates browsing (list -> detail -> notes -> journey)
- Tasks (list -> detail)
- Dashboard load (parallel fetch of stats/tasks/upcoming/attention + optional analytics)
- Automation/workflows (list + stats) (optional)
- Global search (low-volume by default; /search is rate-limited)

## Environment Variables

Core:
- `BASE_URL` (default: `http://localhost:8000`)
- `AUTH_COOKIE` (required)
- `CSRF_TOKEN` (optional; if omitted we try to parse `crm_csrf` from `AUTH_COOKIE`)

Scenario toggles:
- `ENABLE_ANALYTICS=1` (default: 1)
- `ENABLE_WORKFLOWS=1` (default: 1)
- `ENABLE_SEARCH=1` (default: 1)
- `ENABLE_MUTATIONS=1` (default: 0) - enables creating/completing tasks (requires CSRF)

Load shape:
- `DURATION=2m`
- `VUS_SURROGATES=3`
- `VUS_TASKS=2`
- `VUS_DASHBOARD=2`
- `VUS_AUTOMATION=1`
- `VUS_MUTATIONS=1`

Permissions handling:
- `ALLOW_FORBIDDEN=1` (default: 1) - treat 403 as OK for analytics/workflows endpoints

## Notes

- Many endpoints write audit logs (even on GET). Run this against a dev/staging DB unless you intentionally want that write load.
- `/search` is rate-limited (default 30/min). The script keeps search volume low by default; if you want to stress search, increase your API's `RATE_LIMIT_SEARCH` first.
