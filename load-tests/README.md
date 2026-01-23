# Load Tests

Run k6 load tests for core workflows (surrogates, tasks, dashboard, automation, search).

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
