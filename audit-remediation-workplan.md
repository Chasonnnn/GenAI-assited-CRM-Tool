# Repository audit remediation workplan

Audit and plan: 2026-09-19

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
Fable is independently auditing the current source so findings can be compared before
the next cleanup implementation is selected.

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
