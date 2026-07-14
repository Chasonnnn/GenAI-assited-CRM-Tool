# Advisory load tests

The k6 suite exercises core API workflows, but laptop wall-clock results are **advisory only**. Merge gates use deterministic query counts, structured plans, buffers, scanned rows, temporary blocks, and related database-work metrics. See [Query-performance validation](../docs/performance-validation.md) for the complete operating model.

## Supported base-versus-candidate comparison

Prerequisites are Docker Compose, k6, `uv`, and `curl`. PostgreSQL 18 runs in
the isolated Compose project. Run from the API directory:

```bash
cd apps/api && uv run python -m scripts.performance compare --base origin/main --candidate HEAD --mode load
```

The comparison runner creates isolated base and candidate worktrees, databases, and API processes. It uses deterministic synthetic data and cleans up all resources when the run completes or is interrupted. Reports are stored under `apps/api/performance/artifacts/` and must not be committed.

The report includes p50, p95, p99, throughput, error rate, and available database-work deltas. No latency percentile or throughput delta from this command can block a merge.

## Manual single-target run

Manual mode is useful while developing a scenario. It requires an API server and a non-production authenticated session:

```bash
BASE_URL=http://localhost:8000 \
AUTH_COOKIE='crm_session=LOCAL_DEV_VALUE; crm_csrf=LOCAL_DEV_VALUE' \
k6 run load-tests/k6-core-flows.js
```

Never paste a production cookie into the shell. Do not use production rows or point this suite at production. Shell history, k6 output, reports, and application logs must not contain cookies, bind values, tokens, or PII.

## What This Script Covers

`load-tests/k6-core-flows.js` simulates:

- Surrogates browsing (list -> detail -> notes -> journey)
- Tasks (list -> detail)
- Dashboard load (parallel fetch of stats/tasks/upcoming/attention/intelligent suggestions + optional analytics)
- Automation/workflows (list + stats) (optional)
- Global search (low-volume by default; /search is rate-limited)
- Representative task mutations (disabled by default)

## Environment Variables

Core:

- `BASE_URL` (default: `http://localhost:8000`)
- `AUTH_COOKIE` (required for manual mode; local/dev values only)
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

- Many endpoints write audit logs, including some GETs. Run only against the isolated local comparison databases or an explicitly authorized non-production environment.
- `/search` is rate-limited (default 30/min). The script keeps search volume low by default; if you want to stress search, increase your API's `RATE_LIMIT_SEARCH` first.
- `auto_explain` is benchmark-only. Parameter logging is disabled and node timing is off; never copy bind values into a report.
- Absolute latency budgets live in Cloud Monitoring production SLOs and the 10% Cloud Run canary process, not in k6 laptop thresholds.
