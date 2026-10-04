# Local QA environment

QA frontend/API/helper stopped, disposable database dropped, and private runtime files removed after browser verification. See [cleanup](cleanup.md). Historical setup details follow.

- Revision: `65bca746e` on `main`.
- Runtime: repository Mise Python 3.14.6 and uv 0.12.0; existing pinned API virtual environment.
- API: `http://localhost:8000`, loopback listener, PID `54968`, shell session `62800`.
- Public token helper: `http://localhost:8001`, loopback PID `55973`, shell session `18970`; redirects synthetic appointment IDs to existing manage/cancel token pages without logging tokens.
- Database: `crm_qa_20261004_b7f21d` on existing local PostgreSQL 18.1 port 5432. No shared database modified.
- Migration head: `20261004_1300_organization_logo`.
- Environment: `ENV=test`, `TESTING=1`; scheduling V2 and match expansion enabled. Tests bypass rate limiting; auth, session cookies, CSRF, tenancy, and role dependencies remain active.
- Authentication: loopback-only `/__qa` role picker invokes existing development login handler and its session/CSRF cookie creation. No OAuth provider is contacted.
- Provider state: synthetic Google Calendar integration and writable calendar; existing scheduling QA transport. All external HTTP and non-loopback socket connections blocked in the QA API process. No provider credentials loaded and no general worker started.
- Dispatch: email and messaging dispatcher flags disabled. Only explicit restricted scheduling drain can run; workflow decisions and notification email jobs remain queued.
- Initial data: 81 surrogates, 13 intended parents, 20 matches across six states, one scheduling egg donor, three scheduling appointments, templates and workflows.
- Added fixtures: five application roles, two medical donors, one medical surrogate with imported missing-name insurance plus past/current/future PCP history, one notification candidate, assigned/overdue/calendar tasks, workflow approve/deny tasks, action and update notifications.
- Generated private environment: `/private/tmp/crm-live-qa-20261004/environment.json`, mode 600.
- Metadata: `/private/tmp/crm-live-qa-20261004/metadata.json`, mode 600; synthetic IDs only.
- Harness and fixture scripts: `/private/tmp/crm-live-qa-20261004/harness.py`, `/private/tmp/crm-live-qa-20261004/extras.py`.
- API diagnostic restart: original PID `47796` exited cleanly at 20:04 UTC; current process has safe method/route-template/status logging in `requests.jsonl`.
- Additional independent primary admin: `ae8f1ffa-03c6-4e0d-9efb-2499c7cfb4df`, local picker role `review_admin`, used for two-actor match cancellation approval.
- Permission-policy version: primary and foreign organizations both version 1 (default); isolated V2 organization `db116dd1-242f-4e24-9b27-ecf3a7a6aeff` activated through normal reviewed service. Comparisons are in roles.md and roles-v2.md.
- Foreign tenant: `94b1b42a-0251-4b06-9f09-62ebe7e703c6`, synthetic foreign admin and surrogate, accessible through role picker for tenant-denial checks.
- Published browser-created form fixtures: pending, approved, rejected, ambiguous identity, and routing review; schema unchanged.
- Logs: `/private/tmp/crm-live-qa-20261004/api.log`, `migration.log`, `seed.log`, `extras.log`.

| Fixture | ID |
| --- | --- |
| Organization | `1df143a6-7faf-4207-b1cf-4d4dbe949dd7` |
| Admin | `1cf58bbf-e1a6-462f-8c24-add787bf97c5` |
| Scheduling surrogate | `364bf4bf-c2e9-4adf-8efe-f04e19383184` |
| Scheduling donor | `dcf68389-2e94-47c4-9f90-1de0d12e7663` |
| Scheduling intended parent | `04096775-f16f-4bd8-aeaf-422cc0d6d9cc` |
| Medical surrogate | `0a0c05ca-7535-4777-873a-0e50a5e3c201` |
| Medical egg donor | `f72a152a-5026-414c-bd73-18bee9d0514c` |
| Medical sperm donor | `3d95a286-2b99-4d0c-b37f-807a75936b46` |
| Notification candidate | `26b7710c-8c56-4fdf-9436-4d35af8ab01d` |
