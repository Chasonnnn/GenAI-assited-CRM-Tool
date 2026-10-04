# Backend audit ledger

Revision: `bef1a04161f9d5f78fffe9cc15a0db8143a9995f`.

This lane inspected selected match lifecycle, match cancellation, match approval, AI workflow, and import normalization candidates. Discovery was read-only; the parent subsequently authorized applying B1-B12 after the frontend baseline stopped. This is a selective audit, not a complete classification of the backend. Full execution and coverage results are recorded below.

Five match cases and seven AI workflow/action cases were removed or consolidated. The inspected surface did not justify a 20% backend reduction.

## Shared ownership and routing

- `apps/api/app/routers/matches.py` owns HTTP transport for detail, proposal, accept, decline, and cancellation requests. `get_match` delegates to `match_queries.get_detail`; mutations delegate to `match_lifecycle.propose/transition` through authenticated `match_access`.
- `apps/api/app/services/match_queries.py::get_detail` loads the scoped match, logs PHI access, commits, and assembles `MatchRead`. It performs no lifecycle transition.
- `apps/api/app/services/match_lifecycle.py::transition` locks match and parties, checks status and reason, applies changes plus activity/audit inside a savepoint, commits, refreshes, and dispatches effects. `_decline`, `_request_cancel`, `_approve_cancel`, and `_restore_accepted` own the audited contracts below.
- `apps/api/app/routers/status_change_requests.py` routes approval and rejection through `status_change_request_service`; the service resolves match requests through the lifecycle engine and atomically updates the request through `before_commit`.
- Non-test consumers include `apps/web/lib/api/matches.ts` detail/decline/cancellation APIs, `apps/web/lib/api/status-change-requests.ts` approval/rejection APIs, and `apps/api/scripts/seed_mock_data.py` lifecycle calls. None of these production APIs or seams is obsolete.
- The three match files run in the existing backend parallel-safe shards. They are not in the migration/outbox serial partition. Run the repository wrapper for local proof, not an inherited database.

## Applied match batch

### B1 — D: duplicate status row after status-model consolidation

- Exact case: `apps/api/tests/test_match_lifecycle_characterization.py:534::test_get_by_non_proposer_on_reviewing_or_accepted_match_writes_no_transition[under_review]`.
- Actual failure detected: GET by another admin changes an under-review match status/reviewer, acquires a row lock, writes party or stage history, or fails to write exactly one PHI-access audit event.
- Production owner/callers: `matches.get_match -> match_queries.get_detail`; frontend detail API calls this route. `match_access.load`, `to_read`, and action availability retain scoped access checks.
- Stronger keeper: `test_get_by_non_proposer_keeps_proposed_status` at line 467 in the same file. It uses the same new-admin helper and under-review match and checks status in both HTTP and refreshed DB state, null reviewer and timestamp, HTTP 200, no locks, and the exact same history delta.
- History: `e61a6619f` added characterization before refactoring. `5ea9a387f` removed the GET-induced review transition. `5e7a8ede9` folded the formerly distinct `proposed` and `reviewing` statuses into `under_review`, making this one parameter row identical in behavior to the keeper. `git log -L` confirms the former `reviewing` row became `under_review`.
- Removal unlocked: remove only the `under_review` case, then simplify the retained accepted-status test's single-value setup/parameter if desired. Keep `_set_reviewing` because other tests still use it. No production deletion.
- Risk: low; accepted status is distinct and must remain. Proposer, donor, archived-party, permissions, and tenant cases must remain.
- Focused proof: `apps/api/run_tests.sh tests/test_match_lifecycle_characterization.py -k get_by_non_proposer`.

### B2 — C/D: old cancellation-request smoke test

- Exact test: `apps/api/tests/test_match_cancel_request.py:125::test_match_cancel_request_creates_pending_request`.
- Actual failure detected: a valid surrogate cancellation request does not produce HTTP 200/cancellation_pending, a pending match request targeting cancelled, persisted match cancellation_pending, and intended-parent match_cancel_requested activity.
- Production owner/callers: `matches.request_cancel_match -> match_lifecycle.transition -> _request_cancel`; frontend cancellation dialog/API and status request resolution consume the result.
- Stronger keeper: `test_match_lifecycle_characterization.py:1013::test_cancel_request_sets_cancellation_pending_and_notifies` checks HTTP status, request entity/status/target, stripped reason, requester, unchanged matched party stages, lock order, exact audit and both party-activity deltas, and notification parameters. `test_match_approvals_characterization.py:707::test_cancel_request_notifies_every_member_with_approval_permission` retains real notification recipient coverage instead of relying only on spies. The committed-failure keeper `test_failing_cancel_request_notification_returns_success_after_request_is_committed` verifies persisted match/request statuses from a separate session.
- Carry before deletion: add `assert _match_row(db, created["id"]).status == "cancellation_pending"` to the primary cancellation keeper so its refreshed DB status assertion directly absorbs the old smoke assertion. This is one assertion at the canonical owner boundary, not a new case.
- History: `85b127c46` introduced the original cancellation workflow. `161b74650` added durable IP activity assertions. `e61a6619f` introduced the stronger lifecycle suite; `5ea9a387f` centralized transitions; `5e7a8ede9` migrated status names and required reasons.
- Removal unlocked: one repeated accepted-match HTTP setup and smoke body. Shared `_create_accepted_match` and `_ip_activity_types` still have keepers. No production deletion.
- Risk: low after carrying the persisted-state assertion; preserve real notification, failure, duplicate/stale request, malformed reason, authorization, and tenant tests.
- Focused proof: `apps/api/run_tests.sh tests/test_match_cancel_request.py tests/test_match_lifecycle_characterization.py tests/test_match_approvals_characterization.py -k cancel_request`.

### B3 — D: old approval smoke test

- Exact test: `apps/api/tests/test_match_cancel_request.py:154::test_match_cancel_request_approval_updates_statuses`.
- Actual failure detected: approval fails, leaves match non-cancelled, fails to restore surrogate/IP to ready_to_match, or omits intended-parent match_cancelled activity.
- Production owner/callers: approval router -> `status_change_request_service.approve_request` -> lifecycle `approve_cancel`/`_approve_cancel`; frontend approvals API and mock-data seeder call these paths.
- Stronger keeper: `test_match_approvals_characterization.py:102::test_approve_cancellation_cancels_match_and_returns_parties_to_ready` checks refreshed match status/closure metadata, both party stages, stage history actor/reason, exact audit and party-activity changes, request approval status/actor, locks, and actual requester notification. `test_approve_cancellation_closes_open_surrogate_attempts` preserves approval by the requester over a match created and accepted through HTTP; `test_failing_approval_effect_returns_success_and_runs_later_effects` verifies committed state independently.
- History: original `85b127c46` workflow smoke; IP timeline assertions added by `161b74650`; stronger characterization introduced in `e61a6619f`; lifecycle and stage semantics evolved in `5ea9a387f`, `5e7a8ede9`, and `d76049a40`. The keeper now uses `seed_surrogate_match` for prerequisites (`485b97aa4`) but exercises the real cancellation request and approval command.
- Removal unlocked: one repeated setup and smoke body; drop `IntendedParentStatus` import if no remaining use. No production deletion.
- Risk: low with the named requester/committed keepers retained. Do not remove rollback, progressed-party preservation, donor, permission-v2, concurrency, or missing-stage tests.
- Focused proof: `apps/api/run_tests.sh tests/test_match_cancel_request.py tests/test_match_approvals_characterization.py`.

### B4 — D: old rejection smoke test

- Exact test: `apps/api/tests/test_match_cancel_request.py:199::test_match_cancel_request_reject_restores_status`.
- Actual failure detected: rejecting with reason `Not yet` fails, leaves the match non-accepted, or omits intended-parent match_cancel_request_rejected activity.
- Production owner/callers: rejection router -> `status_change_request_service.reject_request/_resolve_match_request` -> lifecycle `reject_cancel`/`_restore_accepted`; frontend approvals API uses this route.
- Stronger keeper: `test_match_approvals_characterization.py:441::test_reject_cancellation_restores_accepted_with_match_history` checks HTTP/request status and actor, refreshed accepted match, null closure, both party stages, exact audit and party history, lock order, audit actor/request linkage, notification reason and actual notification. `test_reject_cancellation_without_body_is_allowed` and `test_resolving_already_resolved_request_returns_400[reject-reject-rejected]` preserve successful self-resolution and replay behavior.
- History: `85b127c46` original workflow; `161b74650` added activity; `5ea9a387f` corrected the rejection event and centralized transitions; `e61a6619f` introduced the stronger keeper.
- Removal unlocked: repeated accepted-match HTTP setup and smoke body; `MatchStatus` and `StatusChangeRequest` imports become removable from this old file if B2/B3/B4 all land. Shared helpers stay. No production deletion.
- Risk: low; donor, rejection without body, delivered-surrogate completion, permission, tenant, and stale-state tests remain.
- Focused proof: `apps/api/run_tests.sh tests/test_match_cancel_request.py tests/test_match_approvals_characterization.py tests/test_match_delivery_completion.py`.

### B5 — D: old reject-and-cancel test now invokes decline twice

- Exact test: `apps/api/tests/test_match_cancel_request.py:230::test_reject_and_cancel_match_are_mirrored_to_intended_parent_activity`.
- Actual failure detected: two successful decline commands omit intended-parent match_declined activity. Despite its name, it no longer invokes any cancellation command.
- Production owner/callers: `matches.decline_match -> match_lifecycle.transition -> _decline -> write_history`; frontend decline API and seed script consume the path.
- Stronger keeper: `test_match_lifecycle_characterization.py:874::test_decline_surrogate_match_writes_declined_status_without_stage_changes[under_review]` checks successful decline, stripped reason, closure/reviewer fields, notes, unchanged party stages, locks, and an exact activity delta containing one IP match_declined event. `test_decline_donor_match_fires_workflow_trigger` retains donor activity, and `test_repeat_proposal_after_closed_surrogate_pair_creates_new_match` retains reuse of a surrogate after a closed match.
- History: `161b74650` originally tested distinct reject and delete/cancel commands. `5e7a8ede9` replaced both operations with PUT decline after the status model removed those legacy commands; `git log -L` shows the second path now duplicates the first.
- Removal unlocked: two redundant proposal/decline scenarios, one collected test, no shared helper or production deletion.
- Risk: low; the actual cancellation activity contract remains in the approval keeper listed for B3.
- Focused proof: `apps/api/run_tests.sh tests/test_match_cancel_request.py tests/test_match_lifecycle_characterization.py tests/test_match_approvals_characterization.py`.

## Retained false positives

- The characterization filenames do not make the suites obsolete. Their exact lock order and callback order protect deadlock avoidance and after-commit behavior. Keep callback failures, transaction rollback, independent committed-session assertions, concurrent transitions, and no-cross-tenant changes.
- Keep `test_match_cancel_request_requires_accepted_match`: no inspected keeper independently makes the same valid-reason cancellation request from under_review and expects 400.
- Keep renamed matched-stage checks and manual-stage refusal: they protect configurable stage semantics, independent of lifecycle happy paths.
- Keep distinct donor/surrogate kinds, permission versions, malformed reason values, requester/proposer identities, and foreign-party sides even when executed lines overlap.
- Keep import-transformer tests. The superficially similar strings exercise independent parsing branches: whitespace, feet/inches labels, curly quotes, plural abbreviations, fractional rounding, and malformed fractions. They are not interchangeable coverage probes.
- Keep AI workflow permission mappings pending owner-boundary evidence; security configuration checks are not automatically junk. Valid workflow trigger/action tests often have different negative-control or alias contracts.

## Follow-up discrepancy

`apps/api/tests/test_ai_workflow.py:619::test_validate_update_status_action_normalizes` is nested inside `test_save_workflow_respects_personal_scope`; it is not a collected pytest case. Do not count removal of this declaration toward the target. A separate review should decide whether a current independent normalization regression needs to be restored at the canonical owner boundary. No changes were made.

## Validation criteria

1. Complete the pinned full baseline; retain failures as defects, not deletion evidence.
2. Replay B1-B5 exact exclusions and inspect collective per-file line/branch deltas. Enforce each backend metric's two-percentage-point maximum separately.
3. Carry B2's refreshed status assertion, remove only the approved cases/imports, and rerun the listed keeper suites plus affected Ruff and `git diff --check`.
4. Independent preservation review must compare removed assertions with the keeper assertions, including actor/setup distinctions.
5. Report actual counts, timings, coverage, and test/support LOC. No production LOC savings are claimed for this batch.

## Second lane: AI workflow validation and approved actions

The complete `test_ai_workflow.py`, `ai_action_executor.py`, `ai_action_approval_service.py`, and `routers/ai_actions.py` were read. The retained approval-retry test, its fixture and no-domain-write assertions, executor scoping tests, relevant permission-v2 tests, and workflow validator/save owner were inspected. All proposed cases run in the backend parallel-safe partition.

`ai_actions.approve_action` calls `ai_action_approval_service.approve_action_for_session`, which executes through the real `get_executor` registry and `validate` method before committing the domain mutation and audit together. `test_ai_action_transactions.py:359::test_unexpected_executor_failure_is_retryable` has separate `add_note`, `create_task`, and `update_status` rows. Its first attempt injects a failure after the real executor writes, proves rollback from a separate session, restores the actual method, approves again, and verifies persisted note content, task title/date, or stage/history plus activity and audit. Its successful second call uses the real registry and validation. `39e4b9541` added this boundary proof when making AI approvals atomic. The older direct executor tests originated in `ca36f109a`.

### B6 — D: weak valid-trigger smoke

- Exact test: `apps/api/tests/test_ai_workflow.py:327::TestWorkflowValidation::test_validate_valid_trigger_type`.
- Actual failure detected: `surrogate_created` yields an error containing `Invalid trigger type`; other errors do not fail this test.
- Owner/callers: `ai_workflow_service.validate_workflow`, used by generated workflow validation and `save_workflow`, which is called by AI workflow routes. Trigger validation precedes conditions and actions and does not depend on whether conditions exist.
- Stronger keeper: `TestWorkflowValidation::test_validate_in_list_operator_normalizes` at line 428 uses the same `surrogate_created`/`add_note` trigger-action pair and `assert result.valid`; it fails for any validation error and additionally verifies normalization. `test_save_workflow_respects_personal_scope` exercises that valid pair through persistence.
- History: `ca36f109a` added the validation/action suite. The original simple acceptance smoke became redundant beside success asserted through the richer validator and save cases; no distinct regression is documented for the weaker assertion.
- Deletion unlocked: one repeated database fixture and workflow construction; no production/test-support seam.
- Risk: low. Keep invalid triggers, inactivity/scheduled requirements, all malformed actions, conditions, and scope/default template cases.
- Focused proof: `apps/api/run_tests.sh tests/test_ai_workflow.py`.

### B7 — D: add-note registry class identity

- Exact test: `apps/api/tests/test_ai_workflow.py:817::TestExecutorRegistry::test_get_executor_add_note`.
- Actual failure detected: `get_executor("add_note")` is None or is not an `AddNoteExecutor` instance; it also fails a behavior-preserving registry implementation change.
- Owner/callers: `ai_action_executor.get_executor` is called by `execute_action`, whose production caller is `approve_action_for_session`; the HTTP approval route consumes that result.
- Stronger keeper: `test_ai_action_transactions.py::test_unexpected_executor_failure_is_retryable[add_note]` performs actual approved-note execution through the registry and verifies exactly one persisted note with expected content after rollback/retry. `TestAddNoteExecutor::test_execute_creates_note` remains for its returned note-id association.
- History: older direct suite `ca36f109a`; owner-boundary proof `39e4b9541`.
- Deletion unlocked: one implementation-class assertion; no production deletion because the registry remains used.
- Risk: low; keep missing content, body alias, foreign-org rejection, human approval, and permission tests.
- Focused proof: `apps/api/run_tests.sh tests/test_ai_workflow.py tests/test_ai_action_transactions.py -k 'executor or invalid_action'`.

### B8 — D: create-task registry class identity

- Exact test: `apps/api/tests/test_ai_workflow.py:823::TestExecutorRegistry::test_get_executor_create_task`.
- Actual failure detected: `get_executor("create_task")` is None or is not a `CreateTaskExecutor` instance.
- Owner/callers: same real `execute_action`/approval/HTTP registry path as B7.
- Stronger keeper: `test_ai_action_transactions.py::test_unexpected_executor_failure_is_retryable[create_task]` verifies persisted task title, date, surrogate link, activity, and audit after a real retry. `TestCreateTaskExecutor::test_execute_creates_task` remains for a title/description payload without due_date and its returned task-id association.
- History: `ca36f109a` direct suite, `39e4b9541` atomic approval proof.
- Deletion unlocked: one implementation-class assertion; no production/support deletion.
- Risk: low; retain missing-title, title-only, cross-org, and permission contracts.
- Focused proof: `apps/api/run_tests.sh tests/test_ai_workflow.py tests/test_ai_action_transactions.py -k executor`.

### B9 — D: update-status registry class identity

- Exact test: `apps/api/tests/test_ai_workflow.py:829::TestExecutorRegistry::test_get_executor_update_status`.
- Actual failure detected: `get_executor("update_status")` is None or is not an `UpdateStatusExecutor` instance.
- Owner/callers: same real `execute_action`/approval/HTTP registry path; production also distinguishes this executor when collecting v2 after-commit callbacks.
- Stronger keeper: `test_ai_action_transactions.py::test_unexpected_executor_failure_is_retryable[update_status]` verifies target stage and history through the registry. `test_ai_actions_permission_v2.py::test_ai_approval_retains_intake_and_moves_to_pool_once` verifies the special v2 stage path and single execution. Direct stage execution remains for its progress-stage/status-label contract.
- History: `ca36f109a` direct suite; `39e4b9541` real transaction proof; permission-v2 behavior evolved independently and its tests remain.
- Deletion unlocked: one implementation-class assertion; no production/support deletion.
- Risk: low with all v2/approval/handoff and direct status-label keepers retained.
- Focused proof: `apps/api/run_tests.sh tests/test_ai_workflow.py tests/test_ai_action_transactions.py tests/test_ai_actions_permission_v2.py`.

### B10 — C: positive note validation into the note execution case

- Exact removed test: `apps/api/tests/test_ai_workflow.py:647::TestAddNoteExecutor::test_validate_with_content`.
- Actual failure detected: valid content produces false validation or a non-null error.
- Owner/callers: `AddNoteExecutor.validate` is called by real `execute_action` before note writes. The approval path's retry keeper also requires validation to succeed.
- Canonical absorbing case: `TestAddNoteExecutor::test_execute_creates_note` at line 660. Before execute, call the same instance's `validate({"content": "test note"}, db, test_user.id, test_org.id)` and retain both `assert valid` and `assert error is None`; leave the existing execute payload/id/content assertions intact.
- History: both tests originate in `ca36f109a`; they are consecutive steps of the same valid note command with repeated database setup. The boundary approval suite was added in `39e4b9541`.
- Deletion unlocked: one database fixture invocation, one duplicated executor construction, one collected case. No production/support seam.
- Risk: low after carrying both assertions; missing-content and body-alias cases remain independent.
- Focused proof: `apps/api/run_tests.sh tests/test_ai_workflow.py -k AddNoteExecutor`.

### B11 — C: positive task validation into the task execution case

- Exact removed test: `apps/api/tests/test_ai_workflow.py:702::TestCreateTaskExecutor::test_validate_with_title`.
- Actual failure detected: a title-only task payload fails validation.
- Owner/callers: `CreateTaskExecutor.validate` is used by `execute_action` before task writes.
- Canonical absorbing case: `TestCreateTaskExecutor::test_execute_creates_task` at line 708. Add `valid, error = executor.validate({"title": "Follow up"}, db, test_user.id, test_org.id)` and its existing `assert valid` before execute. Keep the direct title/description/no-due-date execution and returned task-id assertions.
- History: both direct tests originate in `ca36f109a`; the real approval retry suite in `39e4b9541` uses a dated task, so it alone is not an equivalent title-only acceptance keeper.
- Deletion unlocked: one repeated database fixture/executor setup and one collected case. No production/support deletion.
- Risk: low after carrying the exact title-only input. Do not delete the direct no-due-date execution based on the dated task keeper.
- Focused proof: `apps/api/run_tests.sh tests/test_ai_workflow.py -k CreateTaskExecutor`.

### B12 — C: positive stage validation into the stage execution case

- Exact removed test: `apps/api/tests/test_ai_workflow.py:755::TestUpdateStatusExecutor::test_validate_with_valid_stage`.
- Actual failure detected: validating the existing active default_stage UUID fails.
- Owner/callers: `UpdateStatusExecutor.validate` is used by `execute_action` before stage writes.
- Canonical absorbing case: `TestUpdateStatusExecutor::test_execute_updates_status` at line 763. Before its existing execution, call `validate({"stage_id": str(default_stage.id)}, db, test_user.id, test_org.id)` and carry `assert valid`. Keep its new progress-stage target, returned stage-id, in-memory stage-id, and status-label assertions.
- History: both direct tests originate in `ca36f109a`; later transaction proof uses an intake target, so the older progress-stage execution remains meaningful.
- Deletion unlocked: one repeated database fixture/executor setup and one collected case. No production/support deletion.
- Risk: low after carrying the exact default-stage input. Keep missing stage, out-of-org/pipeline, inactive stage, approval, and v2 handoff tests.
- Focused proof: `apps/api/run_tests.sh tests/test_ai_workflow.py -k UpdateStatusExecutor`.

### Additional retained second-lane false positives

- Keep `TestExecutorRegistry::test_get_executor_unknown`: no inspected owner-boundary test submits an unknown action. `test_invalid_action_is_terminal_and_audited` actually submits whitespace note content, so it is not a keeper for unknown actions.
- Keep all four `TestActionPermissions` tests. The inspected denied-action boundary only removes every action-specific grant for an add-note proposal; it does not independently prove each permission mapping, especially legacy send-email versus v2 send_email permission.
- Keep default-scope versus explicit org-scope template acceptance tests. Their inputs exercise different `scope` values; coverage overlap alone cannot retire the default contract.
- Keep direct executor cross-org tests because approved-action guards and direct executor guards have different denial boundaries.
- Portal slug unit/API duplicates are mostly false positives: `CreateOrgRequest.validate_slug` rejects short/invalid strings and lowercases before `org_service.validate_slug` is reached. The service also serves the CLI, org schemas, create/update services, so the API tests do not independently prove those service guards.
- Resend settings encryption/masking, rate-limit identity, webhook lookup, and campaign-provider policy tests protect distinct secrets/storage/default/dispatch contracts. No justified removal from that file was found in this pass.

## Applied state

B1-B12 are applied in three test files. B1 retains and renames the accepted-state case to `test_get_by_non_proposer_on_accepted_match_writes_no_transition`. B2's refreshed persisted-state assertion and B10-B12's exact validation inputs/assertions are carried. All named retained negatives and direct executor happy paths remain.

| File | Added lines | Removed lines |
|---|---:|---:|
| `apps/api/tests/test_ai_workflow.py` | 12 | 50 |
| `apps/api/tests/test_match_cancel_request.py` | 1 | 140 |
| `apps/api/tests/test_match_lifecycle_characterization.py` | 5 | 8 |
| Total tests | 18 | 198 |

Expected collected reduction: 12 cases (11 declarations and one parameter row). Net test LOC: -180. Production/tooling LOC: 0. Removed unused imports only in the old cancellation file. No shared support seams were retired. Python AST parsing and scoped `git diff --check` pass; no tests or Ruff were run by this lane. Full validation, exact collection count, coverage, and independent preservation review remain parent-owned. No commit, push, PR, merge, or deployment was performed by this lane.

## Executed validation

Baseline: 5,574 collected cases plus 503 subtests passed. Candidate: 5,562 cases plus 503 subtests passed. Both used Python 3.14.6, branch coverage over the same 79,567 lines and 25,712 branches, and separate migrated disposable PostgreSQL databases. No per-file coverage loss. Line coverage: 81.65697% to 81.65948%. Branch coverage: 65.97698% to 65.98475%. The same pre-existing SQLite ResourceWarning occurred in both runs. Changed Python files passed Ruff and formatting checks. Independent preservation review found no gaps. Full-suite timings are not a performance comparison because frontend work ran concurrently.
