# Permission V2 implementation — 2026-10-05

## Behavior

- Default Case Manager surrogate visibility starts at Under Review. Creator access and explicit custom scopes remain.
- Approved and later surrogates belong to the shared Surrogate Pool. Paused and terminal records use their canonical effective phase.
- Migration and future handoffs retain the current active Intake assignee as a collaborator. Earlier ownership alone grants no access.
- A record that returns to preapproval can be assigned normally. Existing collaboration remains until explicitly removed.
- Claim, assignment, and release cannot remove a postapproval surrogate from the pool. The UI hides those controls.
- The activation preview lists pool transfers and retained Intake collaborators. Its digest binds ownership, membership eligibility, and pool state.
- Activation commits policy changes, transfers, collaboration, and audit records atomically. Changed evidence requires a fresh preview.
- Imports, restores, workflow writes, and pipeline edits preserve shared ownership. Pipeline changes include reordering, remapping, and rollback.
- Mutations serialize with activation before taking record locks. A workflow paused during activation cannot run its next action.
- Ordinary Intake receives no IP or Matches access. Match collaboration remains deferred. Donor ownership and phase defaults remain unchanged.

## Schema and release boundary

Migration `20261005_0100_under_review_scope` adds a surrogate-only `under_review_onward` scope value. It preserves stored rules. Downgrade refuses to discard active Under Review scope rules.

Release does not activate V1 organizations or bulk-convert existing V2 data. Existing V2 records normalize through relevant mutation paths. Bulk conversion outside reviewed V1-to-V2 activation requires a separate reviewed operation.

The saved EWI decisions remain unapplied. Production permissions, workflows, and campaigns were not changed. No message was sent or replayed.

## Validation

Application validation ends at local commit `f80f72f4b`. Final results and source fingerprints are recorded in [checks.json](checks.json).

| Check | Result |
| --- | --- |
| Complete API suite | 5,725 passed; 503 subtests passed; zero failures |
| API parallel-safe selection | 5,504 passed with four workers |
| API serial migration, outbox, and OPS selection | 221 passed |
| Frontend type checks, ESLint, and Vitest | Passed; 385 files, 3,055 tests |
| Ruff | Passed across all 41 changed Python files |
| Generated stage and surrogate contracts | Synchronized |
| React Doctor 0.9.14 | No errors; six maintainability warnings |
| Whitespace checks | Passed |

React Doctor reported five complex functions and one non-component export. These are maintainability suggestions, without a reproduced behavior defect. Remote scoring and supply-chain checks were disabled.

Regressions failed before their fixes. Coverage includes denied actions, tenant isolation, stale previews, retained Intake access, atomic rollback, pipeline remapping, imports, and activation races. Nine race tests use real PostgreSQL sessions. The workflow test checks denial and zero notes after activation pauses the workflow.

The broad run caught pending contact fields discarded by refresh. Mutations now flush after acquiring the organization lock and before refreshing. Existing appointment assertions remain unchanged.

Existing test changes preserve their behavioral checks. The general authorization matrix uses Under Review because approved records now reject exclusive assignment. Lock tests retain ordering and lock-strength assertions. The scheduling preparation assertion selects its exact organization, calendar binding, and event. Pipeline query limits remain unchanged.

API checks use disposable local databases and the repository's CI split. Migration, outbox, and OPS tests run serially. Other API tests use four workers with `loadscope`.

## Browser rehearsal

The browser used three disposable organizations and synthetic users and records. The application used real local authentication and CSRF protection, without provider credentials or workers.

| Journey | Observed result |
| --- | --- |
| Case Manager list | Under Review, Approved, later, and paused-postapproval records visible; earlier control records absent |
| Shared-pool detail and bulk controls | Pool label visible; Claim, Assign, and Release absent |
| Advance approved record | Ready to Match saved; shared ownership and Intake access retained |
| Intake navigation | Intended Parents and Matches absent |
| Retained Intake access | Migrated pooled record opens with normal information-edit controls |
| Unrelated pooled record | Intake receives the denied-access screen |
| Migration preview | Three transfers listed; current Intake retention shown; unresolved reviews block activation |
| Synthetic activation | Review, refresh, confirmation, and activation completed; Case Manager scope shows Under Review and later |
| V1 control | Ordinary queue claiming succeeds and persists after restart |
| Browser console | No captured warnings or errors |
| Local API requests | No 5xx responses during the browser rehearsal |

Evidence: [pool detail](shared-pool-detail.jpg), [activation confirmation](activation-confirmation.jpg), [scope](under-review-scope.jpg), [retained Intake](migrated-intake-access.jpg), [denied access](intake-denied.jpg), [V1 claiming](v1-claim-preserved.jpg), and [console](browser-console.json).

## Cleanup and remaining release steps

Task-owned API and frontend processes exited. Ports 8000 and 3000 closed. The synthetic QA database, copied frontend, and temporary keys were removed. Existing PostgreSQL containers were preserved.

Push, CI, deployment, fresh EWI review, and production activation remain separate gates. After release, reconcile the saved handoff decisions against current ownership and fingerprints. Recheck workflow configuration, pending executions, campaigns, and permission differences before activation.
