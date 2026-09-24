# Scheduling V2 local QA

Use only a disposable local database. Do not use a Google account, OAuth credential, email provider credential, or production database.

Create the private environment file. The command generates a local Fernet key, writes mode `600`, and does not print credentials:

```bash
cd apps/api
mise exec -- uv run -m tests.support.scheduling_v2_qa setup
```

The environment has the test crypto setting names from `apps/api/tests/conftest.py`, blank provider credentials, disabled fallback syncs, and API/web URLs `8017`/`3047`. Loading it overrides values from any repository `.env` file.

From `apps/api`, load the file into the current shell, migrate the disposable database, reset the synthetic provider, and seed the fixtures:

```bash
set -a; source /private/tmp/crm-scheduling-v2-qa.env; set +a
mise exec -- uv run alembic upgrade head
mise exec -- uv run -m tests.support.scheduling_v2_qa reset-google
mise exec -- uv run -m tests.support.scheduling_v2_qa seed
```

The private metadata file `/private/tmp/crm-scheduling-v2-qa.json` contains the synthetic organization and admin IDs, test appointment type slugs, and explicit calendar ID. It has no credential values.

Start the API in one terminal and the web app in another:

```bash
cd apps/api
set -a; source /private/tmp/crm-scheduling-v2-qa.env; set +a
mise exec -- uv run -m tests.support.scheduling_v2_qa api --port 8017
```

```bash
cd apps/web
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8017 mise exec -- pnpm dev --port 3047
```

Open [http://localhost:8017/__qa/login](http://localhost:8017/__qa/login) in the QA browser to set the synthetic admin session cookie, then continue to the web app. This GET route exists only in the loopback `ENV=test` harness process and redirects to `/appointments`. Browser API mutations still use the `csrf_token` cookie value in `X-CSRF-Token`.

The seed creates one test organization, the existing development admin, phone and Google Meet appointment types, weekday availability, a non-expiring fake Google Calendar integration, and one explicit writable calendar binding in `America/New_York`. It also creates synthetic surrogate, egg donor, and intended-parent records with linked appointments, and writes exact record URLs into the private metadata file. Domain notification intents use normal application code; the restricted drain accepts only `appointment_google_sync` and `google_calendar_sync` jobs, so it never delivers email.

The API and restricted worker block all non-loopback HTTP. Google Calendar discovery and exact-calendar checks use the synthetic transport. Google Tasks reports unavailable for the synthetic integration.

Drain queued scheduling work through the production dispatcher without starting the general worker:

```bash
cd apps/api
set -a; source /private/tmp/crm-scheduling-v2-qa.env; set +a
mise exec -- uv run -m tests.support.scheduling_v2_qa drain
```

While the provider mode is `provider_failure`, exhaust retries for one known appointment without claiming other appointments' jobs:

```bash
cd apps/api
set -a; source /private/tmp/crm-scheduling-v2-qa.env; set +a
mise exec -- uv run -m tests.support.scheduling_v2_qa exhaust-appointment-failures APPOINTMENT_UUID --limit 50
```

The command finds the appointment's `appointment_google_sync` job through `job_service`, claims and fails it through the production dispatcher, and stops only when its standard job status becomes `failed`. It does not edit appointment rows or run email jobs.

Open `http://localhost:8017/__qa/manage/APPOINTMENT_UUID` to enter the matching synthetic appointment's self-service manage page. The loopback test-only route looks up the seeded organization and redirects with the stored reschedule token; it never prints the token.

Change synthetic provider behavior without clearing events:

```bash
mise exec -- uv run -m tests.support.scheduling_v2_qa mode conference_pending
```

Use `reset-google --mode normal` only to discard synthetic events. `remote-edit EVENT_ID --start 2026-10-01T10:00:00-04:00 --end 2026-10-01T10:30:00-04:00` and `remote-cancel EVENT_ID` retain the state file and simulate inbound changes. Supported modes are `normal`, `conference_pending`, `conference_failure`, `create_collision`, `precondition_conflict`, `provider_failure`, and `sync_token_expired`. The transport handles calendar discovery, exact-calendar lookup, event create/get/patch/delete, and incremental reads. It accepts only the fake token; the harness blocks every external HTTP destination.
