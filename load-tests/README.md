# Load Tests

Run k6 load tests for core workflows (cases, tasks, dashboard, automation).

## Prereqs
- k6 installed (https://k6.io/docs/get-started/installation)
- API server running and authenticated session available

## Usage

Export a session cookie (replace with your own):

```
export AUTH_COOKIE='crm_session=YOUR_SESSION_COOKIE'
```

Run the core flow test:

```
k6 run load-tests/k6-core-flows.js
```

You can override base URL:

```
BASE_URL=http://localhost:8000 k6 run load-tests/k6-core-flows.js
```
