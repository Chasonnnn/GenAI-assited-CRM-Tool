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

Existing cases keep their identifiers and default to surrogate cases. New context columns are nullable. Historical participant-only work remains accessible on the corresponding record; it is not automatically assigned to a match or attempt. Existing match proposal notes remain visible in case work. Assigning other historical work requires a separate reviewed migration with reliable provenance.

Composite foreign keys enforce organization and attempt ownership. Database constraints reserve surrogate commitments and prevent mismatched participants on case tasks, files, and appointments. Lifecycle writes, participant stage changes, and audit records share one transaction. New work and lifecycle operations use the same lock order.

The upgrade uses bounded locks. Constraints and indexes still scan existing tables; this is not evidence that production-scale migration will be interruption-free. Downgrade refuses to discard new case, attempt, work, or correspondence data. Once new data exists, use a compatible application rollback or forward fix.

## Production release gates

1. Verify the deployed revision, production table sizes, long transactions, and cancellation-pending surrogate conflicts. Reconcile conflicts before changing the active-case constraint.
2. Rehearse the exact migration and application revision on a representative sanitized copy. Record lock duration, upgrade duration, row counts, preserved links, and query latency. Retain the normal database recovery backup.
3. Apply the expansion while old APIs remain available. The old application cannot safely read donor cases or completed cases. Route traffic to the new API and worker revision before enabling new case writes in the new frontend. Do not run old and new writers against newly created donor cases.
4. Validate an internal tenant: surrogate and donor proposals, concurrent acceptance, cancellation approval, completion, repeat pairs, attempts, scoped work, appointment changes, and record correspondence.
5. Roll out the frontend after API and worker readiness. Monitor errors, database waits, case counts, and record visibility. Existing record-wide history remains available from participant profiles.
6. Retain the expanded schema for rollback. Do not run the guarded downgrade against new production data.

No deployment, production database inspection, external message delivery, or production zero-interruption validation has been performed in this pass.

## Verification

- Final frontend check: typecheck, ESLint, and all 1,500 tests across 266 files passed.
- Final API suite: 2,923 tests passed against disposable PostgreSQL 18.1. Includes permission and cross-organization negatives, atomic rollback, concurrent surrogate acceptance, case/attempt isolation, and existing appointment/status/notification suites.
- Migration rehearsal: upgraded the complete chain from an existing surrogate-case fixture; original IDs and work survived. Guarded downgrade and schema invariants passed.
- Live browser: IP, donor, surrogate match, donor match, and existing match table rendered against the local API with synthetic records. Desktop kept right-hand Activity and the side-by-side match workspace; narrow layouts stacked the same content. Light and dark themes were checked.
- Live interactions: donor filtering, case/attempt appointment creation, explicit correspondence linking, attempt creation/editing, scoped notes and Calendar, completion error for open attempts, successful completion, and closed-case read-only creation controls.
- Live QA found a missing task-filter URL serialization and visible creation controls on closed cases. Both have regression tests and were verified after correction.
- Ruff and diff checks passed. React Doctor scored 90/100 with five reviewed warnings; no actionable new correctness finding remained.
- Temporary API, frontend, browser tab, and database container were removed. No service is intentionally left running.
