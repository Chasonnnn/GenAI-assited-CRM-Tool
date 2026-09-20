# Repository audit remediation workplan

Audit and plan: 2026-09-19

## Review checkpoint (2026-09-20)

The current batch is closed to further scope expansion. The 63-function backend
cleanup is already committed in `bd7a466f`; notification transport, ZAP, Terraform,
reusable browser QA, and the deferred reliability work remain separate backlog.

Independent review covered all 131 changed paths against `c6095f2d` and the relevant
callers. No blocking code finding was identified. The source-map references to
removed modules and the new AI approval/email services were corrected after review.
`git diff --check` passed for the documentation correction. No application code
changed in this review checkpoint, and no tests were rerun for the documentation.

All 14 hosted checks passed on `bd7a466f`. That result predates this local documentation
correction; the owner authorized publication of the reviewed changes on 2026-09-20.
Keep the PR draft pending fresh CI and the separate merge decision. Nothing was
merged or deployed.

## Scope correction (2026-09-20)

The user clarified that this work should remove slop, not expand product workflows.
The completed local-approval and Gmail-delivery changes below are retained for review;
the user authorized committing, pushing, and opening a PR after verification. That
authorization does not include merging, deployment, or production/provider effects.

Further implementation of slices 2, 3, and 7 is deferred. The remaining sections
record the original findings, not an instruction to implement the reliability backlog.
The active audit covers dead code, pass-through wrappers, redundant abstractions,
low-value tests, unused dependencies, measured performance waste, and verification
friction. Preserve product behavior; report larger correctness issues separately.
Fable completed the independent audit and one comparison round. The agreed cleanup
constraints and acceptance checks below govern the next implementation slice.

## Draft implementation checkpoint (2026-09-20)

The user requested an immediate commit and push with this workplan, with PR #718
kept as a draft while implementation continues. The initial checkpoint below preceded
full validation; the completed checks are recorded under resumed implementation.
The PR remains a draft because the broader audit workplan is not complete.

- At publication, implemented but pending verification: remove six unused frontend dependencies
  and their optimizer entries, four re-export modules, and the notification facade;
  redirect actual callers and monkeypatch targets to the owning modules.
- Removed historical UI-copy bookkeeping, the redundant pipeline source scan, and
  exact service-callee spelling assertions. Retained seven safety/recovery-copy
  assertions, executed-SQL coverage, and negative router boundary checks.
- Coverage migration was in progress: keep the two dead components and their old tests
  until useful donor-assignment and timeline assertions pass on live components.
- Checkpoint validation: dependency removal completed and the lockfile diff was
  inspected. Full frontend/backend suites and production build were pending.
- Fable's deeper API audit was in progress, excluding these active edits. Its completed
  recheck appears in section E. No performance win is claimed for this cleanup.

### Resumed implementation

- Removed the two test-only components after 137 focused tests passed. Assignment
  payloads, owner labels, loading/retry/error behavior, permission/archive gates, and
  timeline stage changes are now covered on live components. Existing SSR, collapse,
  task, and layout assertions remain on the shared timeline and intended-parent page.
- Removed two Next adoption tests that duplicate package pins and agent-document
  spelling. Kept the actual Next configuration checks, including `agentRules: false`,
  experimental feature defaults, generated-route validation, and cache safeguards.
- The CI Lint job now runs the already-pinned Ruff and ESLint commands. The frontend
  build job retains type checking; the duplicate Lint typecheck is gone. Temporary
  fixtures passed syntax/type checking but failed Ruff (`F401`) and ESLint
  (`no-explicit-any`) with exit 1. Those fixtures were removed, not committed.
- Backend validation after the remote OPS CLI merge: 3,111 parallel-safe tests and
  90 serial migration/outbox tests passed (3,201 total). Full API Ruff passed.
- Final checks for this slice:
  - `apps/api/run_tests.sh -n 4 --dist loadscope --ignore=tests/test_email_delivery_outbox.py --ignore-glob='tests/test_migration_*.py' --tb=short`: 3,111 passed.
  - From `apps/api`, `./run_tests.sh tests/test_email_delivery_outbox.py tests/test_migration_*.py --tb=short`: 90 passed.
  - `apps/api/run_tests.sh tests/test_release_ci.py --tb=short`: 11 passed after the CI edit.
  - From `apps/api`, `mise exec -- uv run ruff check .`: all checks passed.
  - From `apps/web`, `mise exec -- pnpm run check`: typecheck, ESLint, and 270 files / 1,563 tests passed.
  - `mise exec -- pnpm run build`: successful production compilation, TypeScript,
    page generation, and standalone output; generated contracts remained unchanged.
  - Authenticated Chromium smoke on that standalone build: populated surrogate
    overview, profile empty state, interview empty state, create/edit/save a synthetic
    interview, saved transcript, and expanded General Notes passed. The inspected
    2x capture showed no missing content or rendering defects; browser errors were
    empty. Local API/database only, no worker or external-provider calls. The browser
    used loopback-only traffic with a platform-host header for production routing.
  - Browser sessions closed, task-started API/web/Postgres stopped, and the synthetic
    database dropped. No QA service intentionally remains running.
- This cleanup slice has a net reduction of 782 lines across code, tests, configuration,
  and dependencies (excluding this workplan); six direct dependencies and four
  transitive packages are removed. These are maintenance reductions, not measured
  runtime speedups.
- The immediate draft checkpoint is published. Continue to keep PR #718 in draft;
  no merge, deployment, shared database writes, or provider sends are authorized.

### Backend cleanup checkpoint and user-requested stop (2026-09-20)

- Removed the 61 unused service functions inventoried in section E, plus the newly
  orphaned `get_source_user_ids_for_grantee` and test-only `count_alerts`: 63 functions
  across 40 service files. Caller/registration searches included the OPS CLI. An AST
  comparison confirmed every retained service function and class was unchanged.
- Moved alert status/severity and cross-organization coverage to the live `list_alerts`
  path, asserting exact items and totals. Removed the unused serializer `db` argument
  and corrected the async-convention test's claim: any `await` does not prove DB offloading.
- This batch removes 1,474 net lines, excluding this workplan. No runtime speedup is
  claimed for unused-code removal; public API and database schemas are unchanged.
- Verification on this checkpoint:
  - Parallel-safe backend suite: 3,114 passed in 68.91 seconds.
  - Serial outbox/migration suite plus CI-contract checks: 101 passed in 42.66 seconds
    (90 serial tests and 11 repeated CI checks; 3,204 distinct backend tests overall).
  - Full API Ruff and `git diff --check`: passed.
  - No frontend changes were included in this batch; prior frontend checks remain
    recorded above, not rerun or claimed as new evidence.
- The user requested commit/push to the existing draft PR, then stop. Remaining
  notification transport, ZAP retirement, Terraform alignment, and reusable browser-QA
  work are paused. A temporary Terraform regression reproduced CI 1.6.6 being below
  the module's >=1.14.0 requirement; the incomplete failing test was removed from this
  checkpoint, and neither CI nor Terraform configuration was changed.
- Fable was asked to stop and preserve its separate notification work. It has not
  been transferred into this checkpoint. Resume only on a new user request.

## Fresh slop audit and cleanup order (2026-09-20)

This audit revisits live code, not the historical counts in `over-engineering-audit.md`.
Fable inspected the transferred implementation snapshot and compared upstream interview
changes; the execution thread independently checked the findings on the PR branch.
The audit spans API/web code, tests, dependency manifests, the donor prototype, scripts,
CI, infrastructure configuration, and guidance. It is a repository-wide evidence-led
pass, not a proof that every unused export, dependency, or performance issue is known.
The findings below were recorded before the draft implementation checkpoint above.

### A. Remove unused dependencies and test-only modules first

- **Five FullCalendar packages have no active web imports.** References remain in
  `apps/web/package.json:24-28` and `next.config.js:47-51`, but not app/components/lib/tests.
  `autoprefixer` is likewise unused by the PostCSS configuration, which only loads
  `@tailwindcss/postcss`. Remove those six direct dependencies and obsolete optimizer
  entries using the package manager; verify the lockfile, full frontend check, and
  production build. This reduces dependency maintenance; bundle/runtime savings are
  not established. The prototype has its own dependency graph and needs a separate check.
- **Two components only have test callers:** `DonorOwnershipSection.tsx` and
  `IntendedParentActivityTimeline.tsx`. Together with their dedicated tests they occupy
  578 lines (131 production, 447 test). Before deleting, compare owner-label/permissions
  and timeline assertions with the active donor-detail, intended-parent-detail, and
  `EntityActivityTimeline` tests; move only uniquely useful assertions to live surfaces.
  Acceptance: no production import changes required, useful behaviors still covered,
  frontend check/build pass. Do not equate deleting tests with improving coverage.
- **Compatibility aliases add navigation without policy:**
  `SurrogateDetailLayoutClient`, `SurrogateProfileCard`, and
  `surrogates/interviews/{SurrogateInterviewTab,InterviewWithComments}` only re-export
  existing components/types. Migrate actual callers and tests to their owner modules,
  retain existing client boundaries, then delete aliases. Verify detail/profile/interview
  tests and production route rendering; inspect the version-matched Next guidance.
- **`notification_facade.py:1-26` is an eager alias table.** It adds no authorization,
  transaction ownership, or cycle break, and patching the original function does not
  change already-bound aliases. Replace imports and monkeypatch targets directly.
  This is lower priority because notification callers span many services; run the full
  backend suite rather than adding another facade-delegation test.

### B. Remove tests that freeze spelling, not behavior

- `ui-description-policy.test.ts:9-129` maintains a historical copy-removal ledger,
  hard-codes 49 placements, and asserts exact AGENTS prose. Delete that bookkeeping.
  Keep the third test's seven safety/recovery-copy assertions at lines 132-154 in the
  first cleanup slice. They cover deletion consequences, template isolation, reconciliation,
  import validation, AI consent, and login guidance. Remove them only after equivalent
  rendered behavior coverage exists; neither reviewer established that replacement yet.
- `test_pipelines.py:1216-1226` forbids the literal `.count()` through source slicing.
  The adjacent test at lines 1230-1297 already records executed SQL and asserts a single
  grouped aggregate. Remove the redundant source scan; retain that query regression
  and the actual pipeline behavior tests. No new test framework is needed.
- `test_router_service_boundaries.py` pins exact service callee names at lines 27, 38,
  48, 59, and 70. Remove rename-sensitive positive assertions. Retain the intended
  per-route transaction/PHI boundary checks until equivalent coverage is demonstrated;
  do not replace them with a repo-wide ban that existing routes cannot satisfy.
- `test_fastapi_conventions_async_sync.py:50-68` counts any `await`; it cannot prove
  that synchronous database work leaves the event loop. Correct its claimed guarantee
  or remove it in a focused follow-up. Pinned `ruff rule RUF029` confirms that rule is
  also only an unused-async check and is preview-only, not an offloading guarantee.
  Do not introduce a broad preview-rule rollout to replace this weak assertion.
- Keep tenant/permission negatives, real transaction/concurrency tests, migration
  preservation checks, the durable Resend transport boundary, and nested-interactive
  accessibility checks. Source inspection alone does not make a test useless.

### C. Make existing verification commands honest and reproducible

- `.github/workflows/ci.yml:314-346` labels a job "Lint" but only compiles `main.py`
  and repeats the frontend typecheck already run by the build job. Run the existing
  pinned Ruff and ESLint commands there; retain one clear typecheck gate. Prove a
  synthetic lint violation fails the gate and the normal repository passes.
- The ZAP step at `ci.yml:485-493` targets `/health` and uses `-I || true`. It does not
  prove authenticated API coverage or reliably signal scan failure. Repair or explicitly
  retire that step, not the entire security job (Bandit and dependency audits remain).
  Any replacement needs a failing injected finding and scoped exceptions, not another
  success-only report. The committed root ZAP report and `.build-test` are cleanup candidates.
- Terraform CI uses 1.6.6 while `infra/terraform/versions.tf:2` requires >=1.14.0.
  Align the local/CI CLI and add backend-disabled validation if feasible, without
  credentials, plan/apply, or state changes. Formatting success does not validate this contract.
- `AGENTS.md:44` points to missing `docs/layouts.md`; repair the reference rather than
  creating a second design-policy document. Existing historical audits must be labeled
  as historical, not treated as current removal inventories.
- Browser QA currently requires ad hoc setup. The existing donor preview script checks
  fixed DB/API ports (`scripts/preview_donor_forms.py:22-31`); it is not a general QA runner.
  Reuse existing dev seed/login and supervised services for a small opt-in synthetic QA
  path, with per-worktree ports/database names, readiness, fake external providers, and
  deterministic teardown. No production auth bypass or new test platform. Acceptance:
  start twice, exercise one meaningful browser flow, inspect its result, and clean up
  without touching another worktree. Full provider E2E remains outside this audit.

### D. Measure performance candidates before cutting work

- **Measured and already implemented:** attachment metadata reads for 10 attachments
  fell from 12 SELECTs to 3, with ordered content and cross-org negatives verified.
- **Confirmed duplicate construction, unmeasured runtime cost:** the shell bell calls
  `useNotificationSocket` (`notification-bell.tsx:64`); the notifications page also calls
  it (`notifications/page.tsx:78`), while the dashboard independently opens the same
  endpoint (`use-dashboard-socket.ts:76`). Source inspection predicts two simultaneous
  sockets on either route, excluding transient reconnect/Strict Mode activity.
  `useUnreadCount` also polls every 30 seconds while healthy (`use-notifications.ts:46-51`).
  First record actual connection/request counts. Then consolidate existing transport
  ownership and connected polling, keeping server data in TanStack Query. Test logout,
  account change, route transitions, reconnect, unmount, and both event types; compare
  before/after counts rather than claim a speedup from fewer source lines.
- Task-delete invalidation breadth, per-member queue inserts, campaign remap lookups,
  and repeated digest queries remain hypotheses. Measure fixed-fixture query/network
  budgets and preserve visibility/transaction semantics before choosing a small fix.

### Comparison decisions and exclusions

- Fable agreed after comparison: mechanical removals first, CI/verification next,
  measured performance last. It withdrew the bulk-output deletion, finalizer registry,
  and broad RUF029 rollout recommendations. Its useful refinement was to retain the
  third UI-copy test while removing only the historical ledger/policy assertions.
- Fable judged the pending approval/Gmail safeguards and independent-session transaction
  tests substantive. Keep no-resend markers, sender pinning, receipt persistence,
  bounded legacy-key recovery, and queued-only polling. Do not remove safety to shrink code.
- Do not add a failure-finalizer registry for a single special job or a `_relock` wrapper
  that merely renames a query. The repeated finalization calls occur at different
  transaction boundaries; their presence alone does not justify a new extension mechanism.
- Do not delete all `output/` on a no-caller search. Its donor prototype includes hosting
  metadata, a sites worker, and tests; external use has not been established either way.
  Verify ownership before archiving. Shared UI imports mean its dependencies cannot be
  pruned by searching only its local `src/` directory. Re-audit retained dependencies;
  historical vulnerability counts are not a current security assessment.
- `scripts/prepare_tf_secrets.sh:32-51` prints credential values to stdout. This is a
  separate operational safety finding, not evidence of leaked production credentials.
  Do not run it with real secrets; a future change needs an explicit restricted-output
  contract and synthetic redaction tests.
- No exhaustive unused-export/Python dependency analysis, load test, production query
  inspection, or external hosting audit was performed. Import recovery, unsubscribe
  behavior, token contracts, worker redesign, and live IAM changes remain deferred.

### E. Deeper API audit: removed in the backend cleanup checkpoint

Fable repeated its AST/reference scan against the published draft checkpoint after
the OPS CLI merge. It reports 61 public service functions (1,248 function-body lines)
with no code or test references, including in-file callers. The scan covered all
tracked files, including `apps/ops-cli`, and checked worker registrations and the new
template service's dynamic access. This is static evidence, not runtime coverage or
proof against out-of-repository callers. The verified removals are recorded above.

The recheck removed `template_variable_catalog.extract_template_variables` from the
dead list because `platform_template_write_service` now calls it. This confirms that
inventories must be rechecked after merges. Before each removal group: read its owner
module, repeat caller/registration searches at current HEAD, delete only the unused
functions and newly unused imports, run Ruff and affected suites, then the full API
suite. Do not add delegation tests for deleted wrappers.

All paths below are under `apps/api/app/services/`:

| Module | Candidate functions |
| --- | --- |
| `ai_settings_service.py` | `get_ai_settings_versions`, `rollback_ai_settings` |
| `analytics_meta_service.py` | `get_cached_meta_spend_summary` |
| `analytics_surrogate_service.py` | `get_status_trend`, `get_surrogates_by_user`, `get_performance_stage_ids` |
| `appointment_email_service.py` | `send_reminder` |
| `audit_service.py` | `log_config_changed`, `log_integration_connected`, `log_integration_disconnected`, `log_data_export`, `log_import_started`, `log_import_completed` |
| `email_provider_service.py` | `get_provider_display_name`, `is_provider_configured` |
| `form_draft_service.py` | `delete_draft` |
| `google_tasks_cleanup_service.py` | `has_unresolved_google_task_work_for_user` |
| `google_tasks_sync_service.py` | `integration_has_google_tasks_scope` |
| `http_service.py` | `request_with_retries_sync` |
| `intake_pool_access_service.py` | `has_pool_access`, `list_accessible_intake_owners` |
| `intended_parent_status_service.py` | `get_default_pipeline_stage` |
| `interview_attachment_service.py` | `update_transcription_status` |
| `interview_service.py` | `to_interview_list_item` |
| `invite_service.py` | `list_pending_invites` |
| `message_content_service.py` | `pending_media_scan_job` |
| `meta_admin_service.py` | `get_ad_account_by_external_id` |
| `meta_lead_service.py` | `get_unconverted`, `get_meta_lead` |
| `meta_oauth_service.py` | `get_active_oauth_connections`, `get_oauth_connection_by_id` |
| `meta_page_service.py` | `get_mapping_by_page_id_any_org`, `update_mapping`, `delete_mapping` |
| `meta_token_service.py` | `get_connection_health_status` |
| `metrics_service.py` | `get_request_metrics` |
| `notification_service.py` | `notify_form_submission_received` |
| `org_service.py` | `get_org_versions`, `rollback_org_settings` |
| `permission_service.py` | `backfill_new_permissions` |
| `pii_anonymizer.py` | `anonymize_surrogate_context` |
| `pipeline_semantics_service.py` | `get_stage_integration_bucket`, `get_stage_terminal_outcome` |
| `pipeline_service.py` | `update_pipeline_stages`, `validate_surrogate_stage` |
| `platform_template_service.py` | `list_published_workflow_templates_for_org` |
| `profile_service.py` | `get_hidden_fields` |
| `resend_settings_service.py` | `clear_default_sender` |
| `scan_dispatch_service.py` | `dispatch_message_media_scan_job_sync` |
| `task_service.py` | `count_pending_tasks`, `get_pending_approval_tasks`, `get_expired_approval_tasks` |
| `tiptap_service.py` | `extract_comment_ids` |
| `tracking_service.py` | `get_recipient_events`, `get_run_events` |
| `user_service.py` | `update_user_signature` |
| `workflow_access.py` | `get_editable_scope` |
| `workflow_email_provider.py` | `get_provider_display_info` |
| `workflow_triggers.py` | `trigger_surrogate_updated`, `trigger_form_started`, `trigger_appointment_completed` |

Exceptions: `log_data_export` has a wish-list reference in `ENTERPRISE_GAPS.md`;
`update_mapping` collides with an unrelated frontend reducer action. Keep the three
import-recovery helpers outside this pass. `alert_service.count_alerts` is separate:
it has one dedicated test, so compare its coverage with the live alert path before
removing both. Dead audit/workflow hooks alone do not establish that equivalent
behavior is absent elsewhere; investigate any product gaps separately.

Fable also found an unused `db` serializer argument in `surrogates_shared.py` and
optional table-driven simplification of the dependency-security ratchet. Keep all
security minimum-version assertions. No new hot-list N+1 was established: surrogate
owner/stage reads are eager-loaded; interview counts and ticket associations are
batched. Cold-path query smells and notification sockets still need measurements.

## Outcome and execution rules

Improve correctness, remove demonstrated waste, and make local verification repeatable.
This plan covers the API, web app, jobs, infrastructure configuration, CI, and donor
prototype. It does not authorize deployment, Terraform apply, production writes, or
external messages. Commit/push/PR authorization is recorded in the scope correction.

Preserve the existing uncommitted cleanup: analytics facade removal, attachment
query batching, export logging correction, disposable test databases, and runtime
documentation. Work on the current branch. Keep each implementation slice independently
verifiable; do not combine unrelated cleanup with behavior changes.

Each slice follows: inspect callers and contracts → failing regression or measured
baseline → smallest implementation → focused checks → affected-suite checks → record
evidence here. A performance claim requires measured query/network counts or timings.
A visual change requires rendered inspection; security changes require denied and
cross-organization cases. Never weaken checks to obtain a green result.

## Status and sequencing

| Slice | Priority | Dependencies | Status |
| --- | --- | --- | --- |
| 0. One Fable review of this plan | Immediate | Draft and exact source snapshot | Complete; corrections incorporated |
| 1A. Atomic local AI approvals | High | Review | Complete; 3,117 backend tests passed |
| 1B. AI email delivery and replay contract | High | 1A and provider/outbox design | Complete; 3,152 backend and 1,542 frontend tests passed |
| 2. Import recovery and transaction ownership | High | Approval pattern verified | Deferred; product/reliability work |
| 3. Export tokens and unsubscribe semantics | High | Token/browser contract inspection | Deferred; separate security/contract work |
| 4. Release, CI, and dependency checks | High | Existing workflow tests | Re-audit for verification waste; no deployment changes |
| 5. Browser QA and isolated worktree tooling | Medium | Stable service/auth fixture contract | Re-audit existing tools before adding infrastructure |
| 6. Measured database and browser performance | Medium | Relevant correctness fixes | Audit; implementation requires a measured baseline |
| 7. Worker fairness and resumable ingestion | Medium | Queue baseline and retry tests | Deferred; architecture/workflow work |
| 8. Dead code, misleading tests, and operations hygiene | Medium/low | Caller verification and replacement coverage | Active slop audit; no IAM changes |

Do not report the whole backlog complete when only a slice is verified. Compare the
fresh audit with Fable before selecting behavior-preserving cleanup. Keep measured
facts distinct from static hypotheses and update outstanding work explicitly.

## 1A. Atomic local AI approvals

Owners: `ai_action_approval_service.py`, `ai_service.py`, `ai_action_executor.py`,
`routers/ai_actions.py`, `note_service.py`, and focused API tests.

Evidence: concurrent approvals both returned executed and created two notes. With
a matching workflow, a later audit-write failure left a committed note and pending
approval; retry created another note. Ordinary access tests passed despite both bugs.

Implementation:

- Serialize approve/approve and approve/reject decisions on the same approval,
  with organization scope from the authenticated conversation membership. Preserve
  access/permission checks and avoid returning another tenant's approval details.
  Re-read state under the lock, including objects already loaded in the ORM identity
  map. Move reject orchestration into the service. Preserve its existing owner/manager
  authorization; rejection does not gain the approval permission requirement.
- Ensure local note/task/status changes, approval state, activity, and audit records
  commit or roll back together. Inspect every invoked service for hidden commits.
- Validation, permission, and business failures remain terminal (`failed` plus audit,
  HTTP 200 with success=false). Unexpected/infrastructure exceptions roll back to
  `pending`, return a server error, and permit retry. A failed transaction has no
  persisted approval/failure audit; do not add a second audit transaction merely to
  log an infrastructure failure. Keep request diagnostics sanitized.
- Remove note workflow execution from the pre-commit executor path. Reuse the
  existing isolated post-commit note dispatch pattern where appropriate; explicitly
  record its process-crash delivery limitation rather than claiming an outbox.
- Preserve the current HTTP 400 response for an already-processed approval in this
  migration-free slice. Durable replay of the original result is a separate contract
  decision: AIActionApproval currently has no execution-result column.
- Do not claim Gmail sending is transactional. `send_email_logged` commits internally
  and performs provider I/O; a row lock alone does not protect it after those commits.
  In 1A, send_email shares the locked status check but otherwise keeps its behavior;
  its internal commit still allows duplicate notes/conflicting approval outcomes.
  Record this gap explicitly, not as an expected-failure test masking a green gate.
  Resolve it in 1B before describing all AI actions as retry-safe.
- Preserve the current two activity entries for an AI note (canonical note activity
  and AI-attributed activity) and pin that count. Consolidating attribution belongs
  to the later cleanup slice. Do not add status-change workflows: that executor does
  not dispatch them today.

Verification:

- Real PostgreSQL, independently committed fixture data and independent sessions;
  ordinary savepoint fixtures cannot prove concurrent visibility or actual rollback.
  Do not copy the shared-Session monkeypatch in test_org_scope_backstop.py. Use a
  unique committed organization per test and explicitly clean up its rows afterward.
- Two approvals create one note and one approval audit record; approve/reject cannot
  both win. Synchronize before the operation, not with a barrier inside a locked
  executor that would deadlock the correct implementation.
- Inject failure after note creation with an enabled workflow: no persisted note,
  contact mutation, activity, audit, or workflow side effect; retry creates one note.
- Successful approval still dispatches the expected workflow. Workflow failure after
  commit must not undo the approval or create a second domain mutation on retry.
- Cover other local actions, unauthorized users, cross-org IDs, CSRF, and repeated
  requests. Run AI approval/executor/note/workflow suites plus Ruff.

## 1B. AI email delivery and replay contract

Trace Gmail logging/idempotency, delivery outbox eligibility, token refresh, activity,
and frontend approval states before selecting an implementation. Preserve human
review: a persisted explicit approval must precede any provider send.

- Prefer durable intent using existing job/outbox infrastructure over a second queue
  or generic transaction framework. Check whether that infrastructure supports user
  Gmail rather than assuming platform email and Gmail are interchangeable.
  Fable confirmed EmailDelivery routes are Resend-only; the generic jobs queue's
  user_gmail workflow handler is the relevant reuse candidate.
- Persist approval identity through delivery, note creation, and completion. Handle
  provider success followed by lost response without blindly resending; Gmail may
  not support exactly-once delivery. Define an explicit ambiguous outcome/recovery.
- If asynchronous delivery or saved response replay requires new states/columns,
  document API/UI impact and add a dated Alembic migration with upgrade tests. No
  production migration or historical-state reset is part of local implementation.
- Test duplicate approvals, failed enqueue, retries, concurrent workers, provider
  timeout after acceptance, audit failure, and cross-org job payloads using fakes.
  Explicitly cover stuck-PENDING EmailLog records: currently a crash around provider
  I/O can leave a pending log that every replay permanently reports as send failure.

Acceptance: one durable human-approved intent; no preapproval send; no uncontrolled
resend after an ambiguous provider outcome; honest queued/sent/failed UI semantics.

Implementation decisions (2026-09-20):

- Reuse the generic jobs queue with `ai_send_email`, not the Resend-only outbox or
  template-based workflow sender. Commit the human approval, immutable EmailLog
  snapshot, job identity, and approval audit together. The old synchronous Gmail
  executor is removed; other Gmail callers retain their existing retry policy.
- `approved` now means queued for this action; `executed` means Gmail returned a
  message receipt. `delivery_unknown` and EmailLog `unknown` mean acceptance could
  not be confirmed. The existing string columns support these values: no schema
  migration or historical-state reset is needed. The API response means queue
  acceptance, not delivery; repeated approval requests still return HTTP 400, not
  a saved execution result. The conversation query refreshes queued delivery state.
- Before OAuth refresh or send I/O, persist a no-resend marker. Make one Gmail HTTP
  send attempt. Timeouts, malformed success responses, server errors, and process
  crashes require checking Gmail Sent before approving another draft. This trades
  automatic liveness for avoiding duplicate mail; even a crash immediately before
  the HTTP request can require manual recovery. It is not an exactly-once guarantee
  or a promise of recipient delivery.
- Persist provider receipts before local note/activity/audit finalization. Retry
  finalization without re-sending; recover expired worker claims and settle exhausted
  jobs. Create the email note and update last-contacted only for confirmed sends.
  Note workflows run after commit and remain best-effort across process crashes.
- Scope workers through the job organization plus bound approval/log identity;
  recheck active membership, user, permissions, surrogate access, suppression, and
  the approved Gmail sender. Job payloads contain IDs, not email bodies. New delivery
  audit details contain IDs/provider only; provider failure text is not surfaced.
- An old pending log with an approval-owned key becomes unconfirmed, never a resend.
  A legacy model-supplied key match also requires manual confirmation; it cannot
  establish ownership of the matching log's content. Existing terminal approvals
  are not reset or automatically resent.
- A future authorized rollout must include worker support before API queue admission
  and the matching frontend status labels; drain old synchronous approval requests.
  No deployment, live migration, Gmail send, or provider connection was performed.

## 2. Import recovery and transaction ownership

Owners: `import_service.py`, `surrogate_service.py`, custom-field and activity services.

- First reproduce a custom-field failure after surrogate creation, then retry the
  same import. Distinguish an already-existing record from a partially imported row.
- Give the import use case ownership of complete-row or bounded-chunk transactions.
  Preserve creation history, generated numbers, tenant checks, and duplicate policy.
- Persist progress/checkpoints so resumed work repairs incomplete work without
  repeating workflows or skipping missing custom fields. Reuse existing import
  metadata before adding schema. Specify migration/recovery if durable state changes.
- Dispatch workflows after successful domain/audit persistence; retain retryable file
  content until the established completion conditions are met.
- Measure queries, commits, refreshes, and dashboard updates on a fixed multirow
  fixture before batching. Do not promise a throughput gain from static analysis.

Acceptance: injected row/chunk failures never leave an irreparable partial record;
retry yields the same complete dataset; duplicates within/across organizations and
created-at overrides retain documented behavior. Run complete import and affected
surrogate/activity suites, migration tests if applicable, and Ruff.

## 3. Token-safe exports and scanner-safe unsubscribe

Export owners: PDF service, export-token authentication, Next print page, Terraform
logging exclusions, and export tests. Inspect version-matched Next documentation.

- Move export bearer capabilities out of both browser and API query strings using a
  scoped header/cookie supported by Playwright and the server-rendered print route.
- Preserve purpose, organization, resource, and expiry checks; do not introduce a
  normal-user-session dependency into the isolated PDF renderer.
- Add request-log exclusions as defense-in-depth. Configuration changes remain local.
- Test missing/expired/wrong-purpose/wrong-resource/cross-org credentials and verify
  the generated navigation and API request URLs contain no bearer tokens.
- Render representative exports and inspect PDFs/screenshots using synthetic data.

Unsubscribe owners: public router/service, email link/header producers, and tests.

- GET renders confirmation without writing suppression state. Human confirmation
  submits POST; provider one-click POST remains supported and token-bound.
- Verify the actual List-Unsubscribe-Post body contract, idempotency, invalid-token
  privacy, and tenant isolation. Do not require authenticated CSRF for provider POST.
  Verify build_list_unsubscribe_headers still targets the mutating POST endpoint;
  the manual link and one-click headers currently share the same token URL.
- Test scanner GET, manual POST, provider POST, retries, malformed payloads, and
  render success/invalid-token confirmation states without exposing recipient data.

## 4. Release, CI, and dependency checks

These independent changes need not wait for slices 1–3; keep their validation and
diffs separate when scheduling them alongside correctness work.

- Web Cloud Build: build with a unique release tag, resolve the digest once, and deploy
  that digest, following `cloudbuild/api.yaml`. Validate generated command references
  and concurrent-build isolation without invoking a deployment.
- Backend lint: enforce the repository's existing Ruff rules in CI, not only compile
  `main.py`. The full API/test Ruff check currently passes.
- Terraform: align CLI with `required_version`; use backend-disabled initialization
  and validate in addition to fmt. No cloud credentials, plan/apply, or state changes.
- DAST: replace `/health`-only discovery with meaningful local API coverage. Remove
  unconditional failure swallowing; distinguish scan execution errors and actionable
  findings from documented exceptions. Prove an injected finding fails the gate.
- Audit every maintained package manifest. The Vite donor prototype reported 10
  vulnerability findings, unlike the clean main frontend and Python environments.
  Trace its shared imports, remove genuinely unused dependencies, update retained
  dependencies/lockfile, and run its build and sites-worker tests. Do not equate an
  unused Next dependency advisory with a demonstrated Vite exploit.

Acceptance: focused workflow/release-policy tests, real static checks, successful
prototype build/tests/audit, and no newly introduced warnings. CI execution and
deployment are not triggered manually without authorization.

## 5. Browser QA and isolated worktree tooling

- Keep `.agents/setup` dependency-only and secrets-free. Preserve frozen installs,
  pinned runtimes, and disposable test database behavior already implemented.
- Add an opt-in QA entry point with supervised API/web services, readiness checks,
  synthetic organizations/roles, local-only authentication, per-worktree ports/service
  names, and deterministic teardown. Prevent inherited shared database credentials.
- Use existing development authentication patterns; never add a production bypass.
  Ensure seeds and test sessions cannot send real email or call real providers.
- Start a small browser suite: reviewed approval/retry, tenant isolation, import
  recovery, upload/export, notification reconnect. Add traces/screenshots on failure.
- Preserve the cheaper type/lint/unit loop. Document that `test:all` is an alias, not
  additional browser coverage. Test startup twice and simultaneous isolated worktrees.

Acceptance: one documented command starts usable synthetic QA, runs a meaningful
browser scenario, and cleans up only its own resources. Inspect changed UI states.

## 6. Measured database and browser performance

Treat these as separate small slices with baseline and after measurements:

1. Notification transport: one authenticated-shell socket feeding existing TanStack
   Query data; no mirrored server data in Zustand. Poll unread counts only when
   disconnected. Test route changes, reconnect, account changes, and unmount cleanup.
2. Task deletion: use deleted task identity to invalidate its entity/activity, lists,
   and relevant aggregates rather than every surrogate. Test unrelated caches stay
   fresh and all affected views still update.
3. Queue initialization: bulk membership inserts under caller-owned transactions;
   preserve membership authorization and unique constraints. Test concurrent creation
   and failure rollback, not merely query-count reduction.
4. Campaign stage remaps: preload the tenant/pipeline stage map; verify asymmetric
   remaps, deleted stages, multiple pipelines, and cross-org IDs before query budgets.
5. Daily digests: reuse org-level work while preserving each user's visibility and
   preferences. Fix dedupe races with a concurrency-safe design that respects both
   permanent and time-window dedupe; a blanket unique key would change semantics.

Acceptance: fixed-fixture query/network budgets improve; correctness and access
tests pass. Do not add caching without an explicit lifetime and invalidation owner.

## 7. Worker fairness and resumable ingestion

- Measure queue wait and completion time with a long synthetic mailbox job alongside
  short jobs. Establish which workloads the deployed configuration actually shares.
- Persist mailbox progress and yield bounded chunks. Test restart mid-page, token
  expiry, duplicated Gmail IDs, partial commits, and event/history ordering.
- Separate job pools using existing type routing where sufficient. If concurrency is
  added, each task owns its Session; never share the worker Session across threads.
- Preserve claim leases/heartbeats, retry backoff, fencing, and organization scope.
- Keep worker count/resource configuration changes local. Any capacity cost or live
  rollout requires a separate operational decision and authorization.

Acceptance: short-job delay is bounded under the synthetic mixed workload; restarted
backfill resumes without skipped messages or duplicate downstream effects.

## 8. Cleanup and operations hygiene

- Reconfirm no production consumers for DonorOwnershipSection and
  IntendedParentActivityTimeline. Move useful assertions to active surfaces before
  deleting orphan components/tests. Do not delete coverage solely to reduce counts.
- Remove SurrogateDetailLayoutClient and notification_facade aliases only after
  direct imports preserve component boundaries, cycles, and patch/test contracts.
- Replace spelling-based router guards and the any-await async guard with useful
  import-boundary or behavior coverage. Keep explicit architectural policy checks
  where they genuinely catch regressions.
- Stop secret-export helpers from implicitly printing credentials. Choose an
  explicit restrictive output-file contract or remove an unused helper; test modes
  and redaction with synthetic secret values, never real credentials.
- Narrow runtime IAM to the secrets actually required by each service. Review cloud
  SQL/Redis availability against SLOs and cost rather than labeling BASIC/single-zone
  choices a code defect. No IAM/availability change is applied by this workplan.

Acceptance: complete affected suites and dependency/build checks; no loss of live
behavior, security coverage, or externally consumed contract without an explicit
documented replacement.

## Review and implementation evidence

- [Fable review](https://ampcode.com/threads/T-01a0b832-7d17-72bc-82cd-e9479855c445):
  one round completed against the exact source revision and uncommitted patch.
  Incorporated explicit Gmail branching, failure taxonomy, lock re-reading/rejection,
  real-session tests, stuck Gmail-log recovery, and pinned activity counts.
  Chose documented Gmail limitations rather than a new processing state or xfail;
  preserved reject permissions and existing activity attribution in slice 1A.
- Slice 1A baseline: approval access, executor scoping, shared notes, and workflow
  trigger scoping suites passed (31 tests).
- Slice 1A regression baseline: 8 failing invariants and 7 passing checks before the
  product fix. The final regression file has 16 tests, including an additional
  action-permission denial case. The combined focused suite passed 47 tests.
- Slice 1A implementation: organization-filtered row locking refreshes cached approval
  state for both approve and reject. Local executor errors propagate to the service,
  which rolls back instead of committing partial changes as a terminal failure.
  Note workflow dispatch uses the existing isolated helper after the owner commit.
  No schema migration, new approval state, or frontend contract field was introduced.
- Full backend verification, from `apps/api`:
  - `./run_tests.sh -n 4 --dist loadfile --ignore=tests/test_email_delivery_outbox.py
    --ignore-glob='tests/test_migration_*.py' --tb=short`: 3,027 passed.
  - `./run_tests.sh tests/test_email_delivery_outbox.py tests/test_migration_*.py
    --tb=short`: 90 passed.
  - `mise exec -- uv run ruff check app tests`: all checks passed.
  - `git diff --check`: passed. Prior cleanup diff checksum remained unchanged.
- Verification discovered a separate existing adapter limitation: surrogate
  note_added workflows cannot run create_task because the adapter rejects the note
  event entity instead of resolving its surrogate subject. Left unchanged in 1A;
  the regression uses a supported notification action and asserts a real successful
  workflow plus exactly one notification after retry. Investigate subject resolution
  separately before changing workflow semantics.
- Limits at completion of 1A: Gmail's internal-commit race still needed 1B. Post-commit note
  dispatch is best-effort, not durable across process crashes. Existing rejection
  permissions and duplicate canonical/AI-attributed note activity are preserved.
- Cleanup: all disposable test databases were dropped; the task's PostgreSQL service
  was stopped and its processes verified exited. Temporary transfer/test logs were
  removed. No commits, pushes, deployments, or shared-state changes were made.

### Slice 1B verification (2026-09-20)

- The initial admission regression failed because approval called Gmail inline.
  Two later legacy-key regressions failed before conservative recovery was added.
  The transaction file now contains 44 cases covering local and queued approvals.
- Regression coverage includes competing approve/reject decisions, failed queue
  admission/audit/commit, immutable approved content, cross-org and foreign-job
  denial, revoked membership/disabled users, duplicate workers, process crashes,
  lost provider receipts, retry after local audit failure, and exhausted/stale jobs.
  HTTP transport tests use a fake server transport and assert one request for
  timeout/server failure, no request after sender replacement, and sanitized logs.
- Replaced the obsolete synchronous-email executor test with worker-level assertions
  for exactly one canonical note activity, one email activity, and post-commit
  workflow dispatch. No production Gmail or other provider was contacted.
- Full backend verification, from `apps/api`:
  - `./run_tests.sh -n 4 --dist loadfile --ignore=tests/test_email_delivery_outbox.py
    --ignore-glob='tests/test_migration_*.py' --tb=short`: **3,062 passed**.
  - `./run_tests.sh tests/test_email_delivery_outbox.py tests/test_migration_*.py
    --tb=short`: **90 passed**. Total: **3,152 passed**.
  - `mise exec -- uv run ruff check app tests`: all checks passed.
- Frontend: `mise exec -- pnpm run check` from `apps/web`: typecheck and lint passed;
  **269 test files / 1,542 tests passed**. After the final safe warning-copy change,
  reran typecheck, affected-file ESLint, and the four affected test files: **40 passed**.
  Polling tests verify queued mail refreshes and each terminal state stops polling.
- Rendered the real AIChatPanel with isolated synthetic fixtures in Chromium at 2x.
  Inspected all four status cards and warnings; DOM confirmed zero approval buttons
  for those processed states. Narrow 390px inspection confirmed the uncertainty
  badge/warning remain readable. Existing horizontal quick-action scrolling is
  unchanged. This is component QA, not an authenticated live-provider E2E test.
  Representative capture: `.amp/in/artifacts/ai-email-delivery-states.png`.
- `git diff --check` passed. Temporary preview files/logs were removed, both QA
  services stopped, PostgreSQL PIDs 62663/62666 exited, and zero disposable test
  databases remained. This was the local/uncommitted state at completion of 1B;
  slice 2 is now deferred by the scope correction above.

### Pre-PR verification on latest main (2026-09-20)

- Fast-forwarded the PR branch to include the current interview-appointment changes
  from `origin/main`, without conflicts or changes to that work.
- From `apps/api`, `./run_tests.sh -n 4 --dist loadscope
  --ignore=tests/test_email_delivery_outbox.py --ignore-glob='tests/test_migration_*.py'
  --tb=short`: **3,083 passed in 99.90s**.
- From `apps/api`, `./run_tests.sh tests/test_email_delivery_outbox.py
  tests/test_migration_*.py --tb=short`: **90 passed in 44.07s**.
  Total: **3,173 backend tests passed**.
- From `apps/web`, `mise exec -- pnpm run check`: typecheck and ESLint passed;
  **270 files / 1,549 tests passed** (Vitest 241.14s).
- Ruff, shell syntax, and `git diff --check` passed. Re-inspected the saved synthetic
  AIChatPanel state capture; no new visual changes were made during this pass.
- Zero disposable test databases remained; the PostgreSQL QA service was stopped
  and its processes exited. No real email/provider calls or production writes.
- Published the implementation in [PR #718](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/718).
  All 14 checks in the [implementation CI run](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/actions/runs/35484275579)
  passed, including backend coverage/migration gates, frontend build/tests, security
  scans, and API/web/worker container builds. The fresh audit adds documentation only.
