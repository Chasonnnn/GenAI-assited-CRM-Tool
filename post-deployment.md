# Post-Deployment Checklist

- If you add new build artifacts or tooling, update `.dockerignore` so they don’t bloat context.
- If you change build steps (new scripts or dependencies), verify the “copy deps first, install, then copy code” pattern still holds.
- Periodically bump pinned base images (monthly/quarterly) and run the docker hygiene tests.
- Keep the `/health` route stable so probes don’t break.
- To force a fresh build (no cached layers), bump `_CACHE_BUST` in the Cloud Build trigger (e.g., set it to a timestamp) for api/web builds.

## Module routing rollout

Before migrating, run this read-only timezone preflight and fix any organization rows it returns:

```sql
SELECT DISTINCT timezone
FROM organizations
WHERE COALESCE(NULLIF(timezone, ''), 'UTC') NOT IN (SELECT name FROM pg_timezone_names);
```

Migration 1400 uses PostgreSQL `AT TIME ZONE`; an unrecognized organization timezone aborts the migration.

Migration 1400 takes organization and workflow row locks with `lock_timeout = '3s'` in the same transaction as migration 1300's `ACCESS EXCLUSIVE` locks. Run `migrate-release` at low traffic and retry on lock timeout.

Migration `20261003_1800_timezone_aware_form_timestamps` converts 34 UTC timestamp columns to `timestamptz` on: `forms`, `form_logos`, `form_field_mappings`, `form_submissions`, `form_submission_drafts`, `form_submission_files`, `form_intake_links`, `published_intake_versions`, `intake_leads`, `lead_attribution`, `consent_records`, `embed_sessions`, `tracking_event_logs`, `form_submission_match_candidates`, `form_intake_drafts`, and `pipeline_stages`. With the session zone set to UTC the conversion changes metadata only, but each table still takes a brief `ACCESS EXCLUSIVE` lock and rebuilds its indexes on these columns. Run at low traffic; it uses a 3-second lock timeout and a 120-second statement timeout. Retry after a lock timeout. Migration `20261003_1200_repair_seeded_system_workflows` repairs only seeded workflows that still match their original configuration exactly; on the Cloud SQL clone, compare each system_key's row count with its exact-match count to see how many rows it will repair.

After all API and worker instances use module routing, run the organization-scoped inventory from `apps/api`:

```sh
mise exec -- uv run python scripts/repair_form_routing.py --organization-id ORG_UUID --window-start 2026-10-03T17:30:00Z --released-at 2026-10-03T18:00:00Z
```

Set `--window-start` to the migration start minus the job queue's maximum lag, and `--released-at` to the completed rollout time. An old worker can process a pre-migration submission's job after migration, so the window must cover that lag. Both timestamps must include a timezone; the start cannot follow the release. The dry run reports workflow, submission, and execution IDs and counts without PII or writes.

After separate production authorization, repeat with `--apply`. The command strips retired workflow actions and makes surviving generated automations ordinary visible workflows. Empty, disabled generated remnants remain hidden with their history intact. It cancels executions paused at retired actions within the inclusive window and completes their open approval tasks as the system actor. It routes unlinked shared submissions submitted within that window that remain `pending_review`/`workflow_pending` and have no completed routing job since `--released-at`. Older submissions are excluded. It uses current form settings and does not replay Application Submitted workflows. Run it for each organization; reruns skip completed repairs.
