# Production preservation audit

Decision: hold release until the preservation and compatibility findings below are resolved.

Subsequent remediation: [fix verification](./fix-verification.md). This report records the pre-fix audit.

Audited source: `930cd7b2` through `7fcf13e8`. The base is a source comparison point, not a verified production revision. Database expansion: `20260830_0100` through `20260905_1600_record_integrations`. No production database, deployed service, backup, or provider was accessed. Application code and migrations were not changed. Audit artifacts are uncommitted.

## Executed checks

| Check | Result | Evidence and limit |
|---|---|---|
| Clean source checkout before audit | PASS | HEAD `7fcf13e8`; no pending changes at start. |
| Fresh disposable PostgreSQL 18.1 upgrade to head | PASS | Local container `crm-preservation-audit-0906`, database `crm_preservation_audit`, bound only to localhost port 55439. |
| Historical record preservation through all three migrations, then repeated upgrade | PASS | Compared every old column in 171 tables; 15 tables were nonempty. Synthetic fixture includes two surrogate records, one IP, one accepted match, a task, note, attachment metadata, and appointment, plus seeded platform/pipeline records. All compared values were identical, including encrypted values, IDs, timestamps, and relationship fields. This is a small fixture, not 171 populated production tables. |
| Historical case association after expansion | CONFIRMED GAP | The old task, note, attachment, and appointment all retain NULL `match_id`. New case-only queries exclude them. |
| Closure-only downgrade | REPRODUCED DEFECT | A cancelled surrogate case with closure date, actor, and reason passes the guard; downgrade drops the closure columns while retaining the match. |
| Concurrent downgrade write | REPRODUCED DATA LOSS | A second connection commits an attempt after revision 1400's empty guard query; the downgrade then drops the attempt table. |
| Existing accepted plus cancellation-pending cases | REPRODUCED CONFLICT | Old schema accepts both for one surrogate. Expansion fails on `uq_one_accepted_match_per_surrogate`; rollback retains both rows and old revision. No automatic conflict cleanup occurred. |
| Starting revision 1600 from revision 1500 | REPRODUCED GAP | With both session timeouts initially zero, both remain zero after the migration. Earlier revisions are not required to execute in the same invocation. |
| Donor legal hold in match retention selection | REPRODUCED DEFECT | Passing a donor hold to the actual retention query still selects its match. Deleting the selected match cascades deletion of its attempt. This exercised selection and database deletion, not the full scheduled purge job. |
| Unrelated surrogate legal hold | REPRODUCED DEFECT | The actual retention query excludes the donor case when an unrelated surrogate hold exists. |
| Case work during match deletion | REPRODUCED INTEGRITY BLOCK | A match with a case note cannot be bulk-deleted: `fk_entity_notes_match_id`. Rows are preserved; callers must handle this deliberately. |
| Focused existing regression suites | PASS | 127 tests passed in 10.12 seconds: migration, match cases, match work, record integrations, shared notes, workflow capabilities, compliance, form submission, and Meta lead-kind snapshots. |
| Production scale, live role configuration, backups, deployed revision | NOT VERIFIED | Requires the actual release baseline and a representative sanitized production-copy rehearsal. |

Machine results: [probe-results.json](./probe-results.json). Reproduction source: [probe.py](./probe.py). Test output: [pytest.txt](./pytest.txt).

## Release findings

### P1: Existing match workspace loses access to historical work

The old match screen combined participant histories. New notes/files queries require `match_id`; tasks and appointments in Calendar do too. Migration 1500 leaves old associations NULL. Existing rows survive on participant profiles, but a previously useful case workspace can look empty. Proposal notes are a separate preserved path.

Evidence: [case work query](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/match_work_service.py:97), [Calendar queries](/Users/chason/GenAI-assited-CRM-Tool/apps/web/components/matches/MatchTasksCalendar.tsx:389), [migration](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/versions/20260905_1500_match_work.py:65).

Required correction: keep historical participant work accessible from the existing case workspace with clear record attribution. Do not guess a case or attempt assignment from a shared participant. Verify old populated cases, repeated pairs, parallel IP cases, and permission boundaries.

### P1: Downgrade can discard closure history

Revision 1400 protects attempts, donor cases, completed cases, and repeated pairs. It does not protect populated `closed_at`, `closed_by_user_id`, `closure_reason`, or `outcome`. A cancelled or rejected surrogate case can pass the guard and lose those fields. Reproduced with populated closure date, actor, and reason.

Evidence: [guard and dropped columns](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/versions/20260905_1400_match_cases.py:154).

Required correction: refuse every downgrade that would discard populated new data. Retain the expanded schema during production application rollback. A database backup restoration alone would also discard writes made since that backup unless recovery includes those writes.

### P1: Donor legal holds do not protect match and attempt history

The match retention query checks surrogate and direct match holds, but not donor holds. A donor-held match can be selected and deleted; attempts cascade with the match. This is a new relationship type reaching an unchanged retention consumer. A donor record surviving its hold is insufficient if its case history is removed.

Evidence: [retention query](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/compliance_service.py:951), [bulk deletion](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/compliance_service.py:2165), [attempt relationship](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/versions/20260905_1400_match_cases.py:95).

Required correction: carry legal-hold protection through donor matches, attempts, and associated work. Test direct and inherited holds, mixed organizations, and the complete purge transaction.

### P1: Downgrade guards have a concurrent-write window

All three guards read for incompatible data before obtaining write-blocking locks on all affected tables. An empty check does not prevent a writer from committing new data before subsequent destructive DDL. A two-connection probe reproduced committed attempt loss in revision 1400; results are recorded in `probe-results.json`. The corresponding 1500/1600 interleavings remain source-reviewed, not individually executed.

Evidence: [1400 guard](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/versions/20260905_1400_match_cases.py:157), [1500 guard](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/versions/20260905_1500_match_work.py:97), [1600 guard](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/versions/20260905_1600_record_integrations.py:141).

Required correction: use an enforceable writer-drain/locking protocol before checks and destructive DDL, or refuse these production downgrades. Test deterministic concurrent writes.

### P1 release gate: Existing commitments can block expansion

The commitment index now covers accepted and cancellation-pending cases. The old accepted-only index permits combinations that violate the new rule. Local reproduction confirms migration failure with preservation after rollback; production occurrence is unknown.

Evidence: [stronger index](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/versions/20260905_1400_match_cases.py:78).

Required correction: preflight the real data before deployment. Resolve conflicting commitments through an approved business transition that retains every case and its history. Do not delete, merge, or silently close records to make the migration pass.

### P1 release gate: Mixed revisions and migration readiness need an explicit cutover

Old code assumes surrogate matches and cannot safely read donor cases with NULL `surrogate_id`, or fully support new lifecycle and repeated-pair behavior. There is no enforced matching activation gate. Cloud Build runs migrations before updating the scan job, worker, and API. The old readiness check compares database and code migration heads for exact equality; after expansion the old application can report 503 until cutover. Actual production probe configuration and resulting traffic impact are unknown.

Evidence: [release sequencing](/Users/chason/GenAI-assited-CRM-Tool/cloudbuild/api.yaml:133), [exact migration-head comparison](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/migrations.py:69), [readiness response](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py:875), [existing rollout warning](/Users/chason/GenAI-assited-CRM-Tool/docs/match-integration-rollout.md:27).

Required correction: rehearse a compatibility release and cutover, including readiness, old in-flight requests, worker draining, new-write activation, and application rollback. Do not assume frontend deployment order alone controls API writes.

### P2: Retention and hard deletion conflict with new dependencies

New RESTRICT relationships preserve recent case work when an old match is deleted, but the existing retention path bulk-deletes without reconciling those dependencies. The resulting integrity error can abort the purge. An archived IP hard-delete can encounter the same dependency graph. The safe response is not to weaken RESTRICT or cascade away recent history.

Evidence: [case work constraints](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/versions/20260905_1500_match_work.py:21), [purge deletion](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/compliance_service.py:2165), [IP hard delete](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/ip_service.py:829).

Required correction: define dependency-aware retention and explicit blocked-deletion responses; test complete purge and hard-delete operations with populated cases.

### P2: Surrogate hold filtering mishandles donor NULL values

`surrogate_id NOT IN (...)` excludes donor cases because their surrogate ID is NULL. Any unrelated surrogate hold therefore changes donor retention eligibility. Reproduced using the actual retention query.

Evidence: [predicate](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/compliance_service.py:957).

Required correction: make party-specific hold filtering explicit and cover all party types together.

### P2: Staff visibility and appointment actions can change

Match access now checks IP and participant access, and nonadmin lists hide archived-surrogate matches. Appointment lists still return owner appointments, while detail and actions check linked-record access; mutations require edit access. An owner can see an appointment but receive 403 after record handoff/archive or without IP permissions. These are stronger access boundaries, not evidence of row loss, but existing operational roles need verification.

Evidence: [match access](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/match_service.py:1016), [archived match filtering](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/match_service.py:1352), [appointment list](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/appointment_service.py:1877), [cancellation access](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/appointments.py:799).

Required correction: verify real role workflows and make list/action behavior consistent without bypassing tenant or record authorization.

### P2: Migration timeout and locking claims are incomplete

Revision 1600 sets neither lock nor statement timeout when run alone. Ordinary index builds and validated constraints can retain earlier ALTER TABLE locks until the whole invocation commits. A three-second lock acquisition timeout and per-statement timeout do not bound the entire interruption window.

Evidence: [1600 upgrade](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/versions/20260905_1600_record_integrations.py:18), [Alembic transaction](/Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/env.py:123).

Required correction: give each independently executable migration explicit budgets, and measure blocking on a representative copy under concurrent application traffic. Choose online DDL or a planned window from those results.

## Existing leads and shared behavior

- No upgrade statement in these three migrations directly deletes or rewrites historical rows.
- Existing surrogate/IP CRUD and lead submission/promotion modules have no diff in the audited change range. Shared callers still warrant regression testing.
- The selected form-submission and Meta lead-kind tests passed. This does not verify live provider ingestion or production lead contents.
- Shared note and workflow tests passed, including legacy surrogate queued-email compatibility. Donor lifecycle automation remains separate unsupported integration rather than an existing-surrogate regression.
- Donor beta navigation gating was accepted by the user and is not a release finding in this audit. Tenant isolation remains required.

## Evidence required before release approval

1. Confirm deployed API, frontend, worker, and Alembic revisions; compare the actual release range.
2. Run read-only conflict, dependency, role, table-size, and long-transaction preflight against the release source data.
3. Resolve findings with focused regressions, then run full affected suites.
4. Restore a representative sanitized production copy and verify backup recovery. Compare row identities, old field values, relationships, attachment storage references, statuses, and historical visibility before and after the full migration chain.
5. Exercise lead intake/promotion, existing surrogate/IP cases, parallel and repeated cases, scheduling, history, holds, and retention with representative roles. Validate tenant-negative cases.
6. Rehearse migration locking, readiness, API/worker cutover, and a compatible application rollback while preserving writes made after release.

Production data preservation and uninterrupted rollout remain unverified until these gates pass.

## Audit cleanup

The disposable PostgreSQL container was stopped after verification. No API server, frontend server, worker, or provider integration was started. No service is intentionally left running. Synthetic reproduction code and results are retained in this audit folder; production application code is unchanged.
