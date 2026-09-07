# Match and record integration rollout

## Local scope

- Existing match IDs, numbers, table, side-by-side party profiles, work tabs, and Calendar remain.
- Each case contains one IP and either one surrogate or one donor. IPs and donors can overlap across cases; a surrogate has one accepted or cancellation-pending case.
- Cases support completion and multiple attempts. Another relationship after closure uses a new case.
- New tasks, notes, files, and appointments persist exact case and optional attempt IDs. Participant attribution stays within that case.
- IP and donor pages share Related Matches, Appointments, and Correspondence cards within their existing light layouts.
- Correspondence includes explicitly linked conversations and recorded outbound email. Current email addresses never infer historical ownership.
- AI and SMS integration, shared donor collections, and migration of clinical progress fields are excluded.

## Schema and history

The Alembic chain adds `20260905_1400_match_cases`, `20260905_1500_match_work`, and `20260905_1600_record_integrations` after `20260830_0100`.

Existing cases keep their identifiers and default to surrogate cases. New context columns are nullable. Historical participant-only work remains attached to its record and is shown with record attribution in the case workspace. It is not automatically assigned to a match or attempt; attempt-filtered views show only that attempt's work. Existing match proposal notes remain visible in case work. Assigning other historical work requires a separate reviewed migration with reliable provenance.

Composite foreign keys enforce organization and attempt ownership. Database constraints reserve surrogate commitments and prevent mismatched participants on case tasks, files, and appointments. Lifecycle writes, participant stage changes, and audit records share one transaction. New work and lifecycle operations use the same lock order.

Each migration sets a three-second lock acquisition timeout and a 60-second per-statement timeout. Locks can remain held through the whole migration transaction; these limits do not bound total interruption. Constraints and indexes still scan existing tables. Downgrade locks all affected tables before checking for new case, closure, attempt, work, or correspondence data. Once new data exists, use a compatible application rollback or forward fix.

## Production release gates

1. Verify the deployed revision, production table sizes, long transactions, and cancellation-pending surrogate conflicts. Reconcile conflicts before changing the active-case constraint.
2. Rehearse the exact migration and application revision on a representative sanitized copy. Record lock duration, upgrade duration, row counts, preserved links, and query latency. Retain the normal database recovery backup.
3. Use the explicit expansion release path below. It preflights the schema before changing services, opens a temporary exact-head readiness compatibility window for old binaries, then migrates and updates workers/API with new case writes disabled. The old application cannot safely read donor or completed cases. Do not activate new writes while old API or worker revisions still serve or process work.
4. Validate an internal tenant: surrogate and donor proposals, concurrent acceptance, cancellation approval, completion, repeat pairs, attempts, scoped work, appointment changes, and record correspondence.
5. Activate new case writes only after API/worker verification, then roll out the frontend. Monitor errors, database waits, case counts, and record visibility. Existing record-wide history remains available from participant profiles and the case workspace.
6. Retain the expanded schema for rollback. Do not run the guarded downgrade against new production data.

No deployment, production database inspection, external message delivery, or production zero-interruption validation has been performed in this pass.

## Explicit expansion release

`MATCH_CASE_EXPANSION_ENABLED` defaults to `false`. Normal first-time surrogate proposals, acceptance, rejection, cancellation, and reads remain available. Donor cases, repeated pairs, parallel IP commitments, attempts, completion, and new case-scoped work require activation. Test fixtures enable the flag explicitly.

`cloudbuild/api.yaml` uses `python -m app.db.release_migration` for preflight and migration. An ordinary release refuses to cross the match expansion boundary. Known starting revisions are `20260830_0100`, `20260905_1400_match_cases`, and `20260905_1500_match_work`; older or unknown baselines require their own reviewed migration plan. Existing commitment conflicts abort with a count and no automatic record changes. The migration itself repeats the check under a write-blocking lock.

For the rehearsed expansion release, set `_MATCH_EXPANSION_ROLLOUT=true` and `_MATCH_EXPANSION_REHEARSED_SHA` to the exact source commit being deployed. The default is `false`; the source SHA check records the operator's rehearsal assertion, not independent proof of a rehearsal.

The expansion build executes these steps:

1. Build and resolve immutable API/worker image digests.
2. Run read-only migration preflight. Failure stops before service configuration changes.
3. Set old API/worker `DB_MIGRATION_CHECK=false`, `DB_AUTO_MIGRATE=false`, and `MATCH_CASE_EXPANSION_ENABLED=false`. The exact-head check is temporarily disabled because old code cannot recognize the expanded Alembic head. Database connectivity checks remain enabled.
4. Run the checked migration job. Lock or statement timeout rolls back rather than discarding records.
5. Update the scan job, worker, and API. New service revisions restore `DB_MIGRATION_CHECK=true`, keep auto-migration disabled, and keep expansion writes disabled.
6. Verify service readiness, image digests, traffic allocation, drained old requests/workers, existing lead/case operations, and migration head. Keep only compatible revisions available for rollback.
7. Set `MATCH_CASE_EXPANSION_ENABLED=true` on compatible workers and then compatible APIs. Verify new workflows in an internal tenant, then deploy the frontend. The build never activates the flag automatically.

Do not use expansion mode for ordinary releases after activation: it intentionally disables new writes. Ordinary releases preserve the activation flag and restore migration checks with auto-migration disabled, including retries after an interrupted expansion release.

## Failed release recovery

- Preflight failure: no service configuration or schema has changed. Reconcile conflicts without deleting cases, or review the actual baseline.
- Failure during the compatibility-window updates: schema has not changed. Restore exact-head checks on affected old services after confirming the database remains at their expected revision.
- Migration failure: confirm transaction rollback and the database revision. Old code can continue with auto-migration off. Restore exact-head checks only if that code recognizes the current revision. Do not blindly restore a database backup over newer writes.
- Migration success followed by service-update failure: retain the expanded schema and keep new writes disabled. Old binaries need the temporary exact-head-check exception; complete the compatible worker/API rollout or use a rehearsed bridge revision. Restore checks as each compatible service becomes ready.
- Failure after activation: disable new feature writes if needed, but do not route readers back to pre-expansion binaries. Retain all records and schema; use a compatible application rollback or forward fix.

Retention preserves open cases, unknown legacy closure dates, recent closures, and matches with dependent history. Parent hard deletion returns a conflict while matches remain. Donor/IP/surrogate, case, attempt, and work holds protect case history. Hold changes, purge, and hard deletion share an organization-scoped transaction lock so a committed hold cannot be missed by a waiting destructive operation.

## Preservation fix verification

- API suite: 2,934 non-migration tests passed against disposable PostgreSQL 18.1.
- Migration suite: all 67 tests passed in a separate disposable database. Full-chain comparison covers every old column, surrogate/IP/donor records and work, appointments, and surrogate/egg-donor/sperm-donor Meta and intake leads.
- Frontend: typecheck, ESLint, and all 1,503 tests across 266 files passed, including rendered history attribution and Calendar behavior.
- Release controls: disabled-write and readable-history checks, migration-lock contention, failed-DDL rollback, deployment configuration checks, and an idempotent checked migration smoke test passed.
- Ruff and diff checks passed. No production resources were accessed or changed. These checks do not replace a production-copy rehearsal or live cutover verification.

## Production-copy database rehearsal — September 6, 2026

A private Cloud SQL clone of the deployed PostgreSQL 18 database started at `20260830_0100`. The full migration preserved every existing value across 171 tables and 1,594,137 rows, including all 8,759 surrogates, 25 intended parents, 27 matches, and the intake and Meta lead tables. No donor records existed in this snapshot.

Upgrade took 0.604 seconds on the idle clone. An intentionally blocked upgrade aborted with SQLSTATE `55P03` and preserved the original revision and data. Downgrade (0.398 seconds) and re-upgrade (0.453 seconds) also preserved every original value. Aggregate evidence and the submitted source manifest are in `output/production-preservation-audit-2026-09-06/rehearsal/`.

Both actual production source and current code passed isolated schema-read and health probes against the expanded clone. Under a synthetic 1.25-second metrics-table lock, old liveness took 1,259.90 ms and new liveness took 5.25 ms. Probe startup and workers were disabled, and metrics writes were rolled back.

The tested source includes uncommitted preservation fixes, so this result does not supply `_MATCH_EXPANSION_REHEARSED_SHA`. Production was not migrated or deployed. The deployed source `6b617131ba41979c0cf40c2aa4def91b8f76ce15` predates database-independent liveness handling; disabling migration-head checks alone does not remove that dependency. Idle-clone timings do not establish a zero-interruption production rollout. Full service cutover, concurrent workload, and authenticated staging workflows remain release gates.

## Earlier integration verification

- Final frontend check: typecheck, ESLint, and all 1,500 tests across 266 files passed.
- Final API suite: 2,923 tests passed against disposable PostgreSQL 18.1. Includes permission and cross-organization negatives, atomic rollback, concurrent surrogate acceptance, case/attempt isolation, and existing appointment/status/notification suites.
- Migration rehearsal: upgraded the complete chain from an existing surrogate-case fixture; original IDs and work survived. Guarded downgrade and schema invariants passed.
- Live browser: IP, donor, surrogate match, donor match, and existing match table rendered against the local API with synthetic records. Desktop kept right-hand Activity and the side-by-side match workspace; narrow layouts stacked the same content. Light and dark themes were checked.
- Live interactions: donor filtering, case/attempt appointment creation, explicit correspondence linking, attempt creation/editing, scoped notes and Calendar, completion error for open attempts, successful completion, and closed-case read-only creation controls.
- Live QA found a missing task-filter URL serialization and visible creation controls on closed cases. Both have regression tests and were verified after correction.
- Ruff and diff checks passed. React Doctor scored 90/100 with five reviewed warnings; no actionable new correctness finding remained.
- Temporary API, frontend, browser tab, and database container were removed. No service is intentionally left running.
