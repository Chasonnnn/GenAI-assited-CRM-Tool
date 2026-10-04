# Post-Deployment Checklist

- If you add new build artifacts or tooling, update `.dockerignore` so they don’t bloat context.
- If you change build steps (new scripts or dependencies), verify the “copy deps first, install, then copy code” pattern still holds.
- Periodically bump pinned base images (monthly/quarterly) and run the docker hygiene tests.
- Keep the `/health` route stable so probes don’t break.
- To force a fresh build (no cached layers), bump `_CACHE_BUST` in the Cloud Build trigger (e.g., set it to a timestamp) for api/web builds.

## Organization square logo

- Apply `20261004_0900_organization_logo` before rolling out the API.
- Roll out the worker with the API so `storage_delete` jobs accept organization logo keys.
- Existing organizations keep `logo_url = NULL`; email signature logos are not copied or changed.
- Verify upload, replacement, deletion, sidebar initials fallback, and journey export branding.

## Module routing rollout

Before migrating, run this read-only timezone preflight and fix any organization rows it returns:

```sql
SELECT DISTINCT timezone
FROM organizations
WHERE COALESCE(NULLIF(timezone, ''), 'UTC') NOT IN (SELECT name FROM pg_timezone_names);
```

Migration 1400 uses PostgreSQL `AT TIME ZONE`; an unrecognized organization timezone aborts the migration.

Migration 1400 takes organization and workflow row locks with `lock_timeout = '3s'` in the same transaction as migration 1300's `ACCESS EXCLUSIVE` locks. Run `migrate-release` at low traffic and retry on lock timeout.

After all API and worker instances use module routing, run the organization-scoped inventory from `apps/api`:

```sh
mise exec -- uv run python scripts/repair_form_routing.py --organization-id ORG_UUID --window-start 2026-10-03T17:30:00Z --released-at 2026-10-03T18:00:00Z
```

Set `--window-start` to the migration start minus the job queue's maximum lag, and `--released-at` to the completed rollout time. An old worker can process a pre-migration submission's job after migration, so the window must cover that lag. Both timestamps must include a timezone; the start cannot follow the release. The dry run reports workflow, submission, and execution IDs and counts without PII or writes.

After separate production authorization, repeat with `--apply`. The command strips retired workflow actions and makes surviving generated automations ordinary visible workflows. Empty, disabled generated remnants remain hidden with their history intact. It cancels executions paused at retired actions within the inclusive window and completes their open approval tasks as the system actor. It routes unlinked shared submissions submitted within that window that remain `pending_review`/`workflow_pending` and have no completed routing job since `--released-at`. Older submissions are excluded. It uses current form settings and does not replay Application Submitted workflows. Run it for each organization; reruns skip completed repairs.
