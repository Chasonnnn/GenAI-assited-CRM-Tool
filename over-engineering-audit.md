# CRM Over-Engineering and AI-Slop Audit

**Audit date:** 2026-07-23
**Committed snapshot:** `6e7cb2eb58e33d4e40b6eabd82480bdc70a4c736` (`main`, five commits ahead of `origin/main`)
**Scope:** `apps/api`, `apps/web`, representative tests, dependency manifests, architecture documentation, and relevant Git history
**Excluded from findings:** the active, uncommitted Resend/email-delivery backend work and other dirty worktree changes

## Executive judgment

The CRM is **not broadly “AI slop.”** It contains substantial real product complexity and several well-earned seams: multi-tenant authorization, provider integrations, webhook dispatch, job processing, email-provider selection, workflow loop control, and explicit PHI/audit concerns.

There is, however, a high-confidence cluster of over-engineering and AI-slop-like engineering:

1. The workflow and approved-AI paths reimplement canonical CRM mutations instead of reusing them. These implementations have already drifted from sanitization and business side effects.
2. Task transaction ownership is split between services and routers, making audit atomicity incidental.
3. A 4,826-line source-text regression suite and a 4,922-line scanner log have shaped code around exact syntax, helper names, and line counts. Committed features now contradict two guards.
4. The frontend opens duplicate WebSocket connections to the same endpoint for different consumers.
5. At least 1,369 lines of committed frontend production modules are unreachable from production entry points but remain maintained and tested.
6. Several backend “facades” are pass-through layers with little or no abstraction depth.

These patterns do **not** prove AI authorship. “AI-slop-like” here means locally plausible code or process output that is insufficiently grounded in system-wide invariants and shifts integration, review, or repair cost downstream.

## Working definitions

**Over-engineering** is complexity whose current, evidence-backed benefit does not repay its implementation, navigation, testing, operational, and change costs.

**Engineering AI slop** is materially AI-generated or AI-amplified output that looks plausible locally but lacks adequate grounding, verification, or ownership. A repository audit cannot establish authorship, so this report identifies **slop-like failure modes**, not who or what produced them.

The main tests used here are:

- **Deletion test:** if an abstraction is removed, does important complexity reappear elsewhere? If only imports change, the abstraction is probably shallow.
- **Adapter test:** are there at least two real implementations, policies, or consumers that justify a seam?
- **Invariant test:** do all paths performing the same domain action preserve the same security and business rules?
- **Interface test:** do tests protect externally meaningful behavior, or merely freeze implementation spelling?

## Findings summary

| ID | Priority | Finding | Primary risk | Confidence |
| --- | --- | --- | --- | --- |
| F1 | P0 | Workflow and approved-AI paths duplicate canonical domain mutations | Security and business-invariant drift | High |
| F2 | P1 | Services and routers share transaction ownership around audit events | Audit-completeness and transaction reliability | High |
| F3 | P1 | Scanner-driven source-text tests freeze syntax and decomposition | Refactor tax, false confidence, stale gates | High |
| F4 | P1 | Multiple hooks open independent sockets to `/ws/notifications` | Duplicate connections and split retry policy | High |
| F5 | P2 | Unreachable frontend inventory remains tested and dependency-bearing | Dead-code churn and review noise | High |
| F6 | P2 | Notification, dashboard, and status facades are shallow | Navigation and signature duplication | High |
| F7 | P2 | Analytics split is hidden behind a dynamic compatibility facade | Weak discoverability and an excessively wide interface | High |
| F8 | P3 | Dependency and documentation inventories contain low-value residue | Install and maintenance overhead | Medium-high |
| F9 | P3 | Resend engagement formatting is duplicated across history views | Presentation drift and duplicate tests | High |

## F1 — Parallel domain mutation implementations

**Classification:** AI-slop-like integration failure and architectural duplication
**Priority:** P0
**Confidence:** High

### Evidence

Workflow assignment directly mutates and commits a surrogate:

- `apps/api/app/services/workflow_engine_adapters.py:545-565`

The canonical assignment operation performs substantially more policy and side-effect work:

- `apps/api/app/services/surrogate_service.py:1013-1117`
- user-versus-queue handling
- `assigned_at` maintenance
- assignment/unassignment activity
- assignee notification
- pending workflow-approval invalidation
- assignment workflow emission

Workflow stage mutation implements a second stage-transition path:

- `apps/api/app/services/workflow_engine_adapters.py:868-953`

The canonical stage service contains the actual transition policy:

- `apps/api/app/services/surrogate_status_service.py:340-656`
- `apps/api/app/services/surrogate_status_service.py:659-809`
- pipeline and role policy
- regression approval
- backdating rules
- on-hold and interview scheduling behavior
- status history metadata
- downstream task, integration, and event side effects

Workflow note creation writes raw `content` directly:

- `apps/api/app/services/workflow_engine_adapters.py:978-1008`

The canonical note service sanitizes HTML and emits the note-added workflow:

- `apps/api/app/services/note_service.py:36-38`
- `apps/api/app/services/note_service.py:46-76`

Approved AI actions form another parallel implementation:

- note creation: `apps/api/app/services/ai_action_executor.py:83-142`
- task creation: `apps/api/app/services/ai_action_executor.py:145-211`
- status mutation: `apps/api/app/services/ai_action_executor.py:214-298`
- production invocation: `apps/api/app/services/ai_action_approval_service.py:156-205`

The approved-AI note path does sanitize content and emit `note_added`; it is not the sanitizer bypass. Its concern is duplicated persistence and orchestration. The concrete sanitizer bypass is the workflow adapter.

The AI task path deliberately assigns the approving user, so owner defaulting and reassignment notification are not meaningful parity gaps there. The clear omitted side effect is Google Tasks synchronization; optional dashboard emission is a policy choice:

- `apps/api/app/services/task_service.py:84-138`

Existing executor tests largely confirm immediate row changes and registry selection, not parity with canonical behavior:

- `apps/api/tests/test_ai_workflow.py:539-740`
- `apps/api/tests/test_workflow_engine_full_paths.py:576-735`

### Why this matters

The same business action now has different invariants depending on whether it came from the normal UI, a workflow, or an approved AI action. The workflow note path bypassing the canonical sanitizer is concrete drift, not merely speculative duplication.

System and workflow actors do need special authorization, loop control, and transaction behavior. That justifies explicit actor and execution policies; it does not justify separate persistence implementations.

### Recommendation

Create canonical domain commands for assignment, status change, note creation, and task creation. Each command should accept explicit:

- actor context, including system/workflow actors;
- authorization mode;
- workflow/event emission policy;
- transaction ownership (`flush` versus caller-owned commit);
- idempotency metadata where relevant.

Make the workflow and AI executors adapters over those commands. Add parity tests that run the same domain action through user, workflow, and AI entry paths and compare required invariants.

## F2 — Split transaction ownership around audit events

**Classification:** Architectural incoherence with audit-reliability risk
**Priority:** P1
**Confidence:** High

### Evidence

Task creation commits in the service:

- `apps/api/app/services/task_service.py:102-118`

The router then stages the semantic audit event and commits again:

- `apps/api/app/routers/tasks.py:185-208`

The same pattern exists for:

- update: `apps/api/app/services/task_service.py:155-180` and `apps/api/app/routers/tasks.py:286-298`
- completion: `apps/api/app/services/task_service.py:219-229` and `apps/api/app/routers/tasks.py:339-350`

`audit_service.log_event` stages the audit row in the current session rather than independently making the prior business mutation atomic with it:

- `apps/api/app/services/audit_service.py:90-148`

### Why this matters

If audit construction or the second commit fails, the task mutation has already succeeded. The layering gives two modules partial transaction ownership and makes the intended audit guarantee unclear.

The cited code does not itself prove a regulatory requirement for atomic task audit rows. This is therefore an audit-completeness and reliability risk, not a confirmed compliance violation. It is defensible to keep a business mutation durable when an ancillary audit sink fails, but that should be an explicit policy backed by an independently durable audit/outbox design rather than an accidental consequence of double commits.

### Recommendation

Choose one transaction owner for each request-level command:

- Prefer a service/application command that stages mutation and semantic audit in one transaction.
- If audit delivery must be isolated, write an audit outbox record atomically with the mutation and process it separately.
- Normalize service APIs around caller-owned transactions before routing workflow and AI actions through them.

## F3 — Scanner-driven source-shape regression lattice

**Classification:** Over-engineering and AI-slop-like verification
**Priority:** P1
**Confidence:** High

### Evidence

`apps/web/tests/react-regressions-source.test.ts` is:

- 4,826 lines;
- 312 tests;
- touched by 419 commits;
- historically 4,988 added lines versus 162 deleted lines;
- home to 64 test names framed as compiler-friendly, compiler-compatible, or compiler-derived.

Its parser is based on string indexes and textual next-function markers:

- `apps/web/tests/react-regressions-source.test.ts:5-27`

It freezes exact implementation choices such as:

- required helper and reducer names;
- absence of `useMemo`, `useCallback`, `useEffect`, and `finally`;
- exact code fragments;
- exact component decomposition;
- line-count ceilings.

Representative examples:

- `apps/web/tests/react-regressions-source.test.ts:117-195`
- `apps/web/tests/react-regressions-source.test.ts:848-880`
- `apps/web/tests/react-regressions-source.test.ts:1249-1258`

The surrogate application guard requires exact helper names and an exported component under 300 textual lines:

- `apps/web/tests/react-regressions-source.test.ts:855-871`

The resulting file is still 2,272 lines and contains large pass-through input structures and renderer repackaging:

- `apps/web/components/surrogates/SurrogateApplicationTab.tsx:1531-1640`
- `apps/web/components/surrogates/SurrogateApplicationTab.tsx:1742-1977`
- `apps/web/components/surrogates/SurrogateApplicationTab.tsx:1979-2272`

The project log explicitly records tightening the limit through `<520`, `<450`, `<400`, and `<300` to clear `no-giant-component`:

- `docs/react-doctor-triage.md:4904-4922`

That log itself spans 4,922 lines and 230 batches.

The source suite is already inconsistent with committed behavior.

Commit `58fa0c10` added email-template history and rollback as a real feature. One assertion directly rejects the new `EmailTemplateVersion` interface:

- feature API: `apps/web/lib/api/email-templates.ts:83-90` and `apps/web/lib/api/email-templates.ts:165-183`
- contradictory guard: `apps/web/tests/react-regressions-source.test.ts:1249-1258`

The guard's other four checks look for older names (`getTemplateVersions`, `rollbackTemplate`, `useTemplateVersions`, and `useRollbackTemplate`). The feature uses `listEmailTemplateVersions`, `rollbackEmailTemplate`, `useEmailTemplateVersions`, and `useRollbackEmailTemplate`, so those checks are obsolete and fail to cover the equivalent new exports.

Commit `67d64a72` then added `email-operations.ts` with an API-barrel import that another source guard forbids:

- committed import: `apps/web/lib/api/email-operations.ts:1`
- contradictory boundary guard: `apps/web/tests/react-regressions-source.test.ts:883-887`

Focused verification at the final audit snapshot returned **310 passed / 2 failed** for this file. The behavioral surrogate-application suite returned **6 passed / 6 passed**.

Backend counterparts repeat the implementation-lock pattern:

- `apps/api/tests/test_workflow_engine_split.py:1-11`
- `apps/api/tests/test_ai_router_split.py:1-29`
- `apps/api/tests/test_surrogates_router_split.py:1-14`
- `apps/api/tests/test_router_service_boundaries.py:9-74`

### Why this matters

These tests make harmless refactors fail while allowing behavior to remain wrong. They incentivize code that satisfies a scanner’s visible shape rather than code with deeper interfaces and better locality.

React Compiler is not the problem. Some source or AST checks are useful for genuine architectural constraints. The problem is treating exact syntax, helper names, and scanner score as the product contract.

### Recommendation

Partition the suite:

1. Retain behavior tests for user-visible and stateful outcomes.
2. Express real architectural rules with ESLint, TypeScript AST checks, or import-boundary tooling.
3. Delete exact helper-name, exact-fragment, and arbitrary line-count assertions.
4. Keep narrowly justified repository-wide gates, such as the TypeScript-AST design-system boundary in `apps/web/tests/design-system-primitives.test.ts`.
5. Replace the 230-batch log with a short current baseline, accepted exceptions, and a decision record for compiler policy.

## F4 — Duplicate WebSocket clients for one endpoint

**Classification:** Over-engineered client transport
**Priority:** P1
**Confidence:** High

### Evidence

`useNotificationSocket` owns a connection, ping loop, authentication close handling, retry suppression, and exponential reconnect behavior for `/ws/notifications`:

- `apps/web/lib/hooks/use-notification-socket.ts:83-230`

`useDashboardSocket` independently implements another connection, ping loop, and different reconnect state machine for the same endpoint:

- `apps/web/lib/hooks/use-dashboard-socket.ts:37-203`

The notification bell is mounted in the authenticated app header:

- `apps/web/components/app-sidebar.tsx:752-770`
- `apps/web/components/notification-bell.tsx:34-43`

The dashboard then opens its own socket:

- `apps/web/app/(app)/dashboard/page.client.tsx:76-90`

The notifications page also calls `useNotificationSocket` while the global bell remains mounted:

- `apps/web/app/(app)/notifications/page.tsx:74-86`

### Why this matters

Dashboard sessions open at least two concurrent sockets to the same user stream. The notifications page also duplicates the bell’s notification connection. Each connection sends pings and owns separate connection refs and reconnect timers. Multiple `useNotificationSocket` instances share that module's suppression timestamp, while `useDashboardSocket` has a separate suppression variable and a different retry policy.

Separate consumers are sensible; separate transports are not required.

### Recommendation

Own one authenticated notification-stream connection in a provider or external store. Dispatch typed messages to subscribers:

- notification/count consumers;
- dashboard-stat invalidation;
- future real-time consumers.

Keep one retry and keepalive policy, and test fan-out behavior independently from transport behavior.

## F5 — Unreachable frontend inventory kept alive by tests

**Classification:** AI-slop-like residue and dead-code maintenance
**Priority:** P2
**Confidence:** High

### Evidence

A route/layout/proxy-rooted TypeScript import-graph review and repository-wide symbol search found no production caller for:

| Module | Lines |
| --- | ---: |
| `apps/web/components/surrogates/LatestUpdatesCard.tsx` | 133 |
| `apps/web/components/surrogates/interviews/TranscriptViewer.tsx` | 288 |
| `apps/web/lib/hooks/use-transcript-viewer-listeners.ts` | 40 |
| `apps/web/components/ui/carousel.tsx` | 71 |
| `apps/web/components/version-history-modal.tsx` | 214 |
| `apps/web/lib/forms/templates.ts` | 623 |
| **Total** | **1,369** |

Tests and source guards still import or inspect these modules. Examples:

- `apps/web/tests/surrogate-interview-accessibility.test.tsx`
- `apps/web/tests/transcript-viewer.test.tsx`
- `apps/web/tests/transcript-viewer-listeners.test.tsx`
- `apps/web/tests/carousel-listener-cleanup.test.tsx`
- `apps/web/tests/version-history-modal.test.tsx`
- `apps/web/tests/forms-builder-template.test.tsx`

`embla-carousel-react` is reachable only through the unused carousel module and its test:

- `apps/web/package.json:45`
- `apps/web/components/ui/carousel.tsx:4`

### Why this matters

The repository spends test, dependency, scanner, and review effort on code with no current product path. Recent scanner cleanup even continued modifying some of these modules.

Dormant reusable inventory is a possible justification, but this is an in-house project with an explicit no-backward-compatibility policy. Reusable code should earn its place through a current caller or live as an explicit example/fixture outside production source.

### Recommendation

Confirm there is no runtime registry or external package consumer, then delete the modules, their dedicated tests/guards, and `embla-carousel-react` if no remaining caller exists. Reintroduce a component when a real product path requires it.

## F6 — Shallow backend facades

**Classification:** Over-engineered indirection
**Priority:** P2
**Confidence:** High

### Evidence

`notification_facade.py` contains 22 public functions; all 22 delegate to the same-named `notification_service` function:

- `apps/api/app/services/notification_facade.py:31-307`

Its tests verify forwarding mechanics:

- `apps/api/tests/test_notification_facade.py:7-78`

Production jobs and routers still import `notification_service` directly, so the supposed boundary is not comprehensive:

- `apps/api/app/routers/internal.py:444-491`
- `apps/api/app/jobs/handlers/notifications.py:9-46`
- `apps/api/app/jobs/handlers/reminders.py:10-46`
- `apps/api/app/jobs/scan_attachment.py:24-153`

`dashboard_events.py` is an 18-line module containing one exact delegate:

- `apps/api/app/services/dashboard_events.py:1-18`

`surrogate_service.change_status` is a 39-line exact forwarding wrapper retained after status extraction:

- `apps/api/app/services/surrogate_service.py:972-1010`

### Why this matters

These modules fail the deletion test: removing them changes imports but does not force important policy or implementation complexity to reappear. They add navigation, signatures, mock surfaces, and delegation-only tests.

A facade can be valuable when it translates policy, isolates an external dependency, breaks a real cycle, or selects between implementations. These examples currently do little or none of that.

### Recommendation

For each facade, choose one:

- delete it and import the canonical module directly; or
- deepen it by moving real event policy, durability, translation, or adapter selection behind the interface.

Do not keep a seam solely because a future implementation might need it.

## F7 — Dynamic analytics compatibility facade

**Classification:** Over-engineered compatibility layer
**Priority:** P2
**Confidence:** High

### Evidence

The analytics split created domain modules, but `analytics_service.py` dynamically re-exports roughly 50 symbols through four allowlists and module `__getattr__`:

- `apps/api/app/services/analytics_service.py:171-246`

Its substantive local operation is `get_pdf_export_data`:

- `apps/api/app/services/analytics_service.py:20-168`

Production callers continue using the wide facade rather than importing the relevant domain module:

- `apps/api/app/routers/analytics.py`
- `apps/api/app/services/admin_export_service.py:999-1014`
- `apps/api/app/services/pdf_export_service.py:1964-1977`

Delegation tests preserve the compatibility behavior:

- `apps/api/tests/test_analytics_service_refactor.py:5-64`

### Why this matters

The split is invisible at the call site, static discovery and typing are weaker, and the public interface remains almost as broad conceptually as the pre-split module.

A stable facade can reduce external migration cost. That argument is weaker in this repository because its stated policy explicitly rejects backward-compatibility constraints.

### Recommendation

Move `get_pdf_export_data` to an explicit report/export module and have callers import `analytics_meta_service`, `analytics_surrogate_service`, `analytics_usage_service`, or `analytics_shared` directly. Delete dynamic re-export tests after migrating callers.

## F8 — Dependency and documentation residue

**Classification:** Low-priority over-engineering and ownership drift
**Priority:** P3
**Confidence:** Medium-high

### Unused duplicate HTTP client

The backend declares both `httpx` and `httpx2`:

- `apps/api/pyproject.toml:31-33`

Repository-wide Python search finds no `httpx2` import. It also brings a second transport dependency, `httpcore2`, into the lock.

`httpx2` is a legitimate Pydantic-maintained continuation of HTTPX, not a suspected typo-squatting package. Its presence is still redundant until the application actually migrates to it. See the [verified PyPI project](https://pypi.org/project/httpx2/).

The manifest also explicitly pins several transitive packages already captured by `uv.lock`. Some pins are documented resolver/security constraints, so this report does not recommend a blanket removal. Direct dependencies should nevertheless be limited to packages the application imports or intentionally constrains.

### Stale manual code map

`CODEMAP.md` is a 635-line hand-maintained filesystem catalog last updated on 2026-01-30. Since that commit, the repository has accumulated approximately 1,788 commits and a source diff of 165,797 insertions and 49,046 deletions. It already references a missing route, `apps/web/app/apply/[token]/page.tsx`, and its inventory counts have drifted.

No repository file links to `CODEMAP.md`.

### Recommendation

- Remove `httpx2` until a deliberate migration uses it.
- Review transitive-only direct pins and document only the constraints that are intentional.
- Replace `CODEMAP.md` with a short architecture index centered on stable boundaries and decisions, or generate the filesystem inventory automatically.
- Archive the full React Doctor batch log and retain a compact current policy/status document.

## F9 — Duplicate Resend engagement presentation logic

**Classification:** Small but concrete AI-slop-like duplication
**Priority:** P3
**Confidence:** High

### Evidence

Commit `6e7cb2eb` added the same delivery/open/click formatting rules to two history surfaces:

- `apps/web/components/surrogates/ActivityTimeline.tsx:171-203`
- `apps/web/components/surrogates/detail/SurrogateHistoryTab.tsx:290-317`

Both implementations independently:

- normalize `delivery_status`;
- format delivered/opened/clicked timestamps;
- pluralize open and click counts;
- label the timestamp as the first event;
- append `Open tracking is approximate`.

The surrounding views legitimately differ: one includes attachment preview details, while the other handles AI prefixes, template labels, and a caller-provided date formatter. Those differences do not require duplicating the shared engagement semantics.

### Why this matters

The duplication landed with parallel tests in the same commit. A future wording, timestamp, or tracking-policy change now requires coordinated edits across both views and tests.

### Recommendation

Extract a pure engagement-summary formatter that accepts the date formatter and returns semantic parts. Keep view-specific prefixes, attachment text, and final joining in each component.

## Justified complexity and false positives

The following were reviewed and should **not** be labeled over-engineering on current evidence:

- `EmailSender` has two real production implementations: Gmail and platform email.
- The webhook protocol dispatches five concrete handlers.
- The AI provider hierarchy represents real Gemini/Vertex credential and runtime variants.
- The job registry dispatches many distinct production job types.
- `WorkflowDomainAdapter` has one production adapter but test adapters exercise the generic workflow core; the seam is defensible. Its duplicated domain mutations are the problem.
- Thin routers, organization scoping, CSRF enforcement, PHI-aware DTOs, and audit controls are required project constraints.
- The TypeScript-AST design-system boundary in `apps/web/tests/design-system-primitives.test.ts` enforces a genuine platform-wide interface more robustly than substring checks.
- The active email-delivery WIP contains substantial layering, but durable outbox state, leases/fencing, retry policy, idempotency, provider I/O, webhook reconciliation, and organization-specific credentials are real concerns. Unfinished WIP was not labeled slop.

## Recommended sequence

### P0 — Restore one implementation per domain action

1. Define canonical, caller-transaction-aware commands for assignment, status, notes, and tasks.
2. Add user/workflow/AI parity tests for sanitization, history, notifications, tasks, approvals, events, and org scope.
3. Route workflow and approved-AI adapters through those commands.

### P1 — Fix transaction and verification boundaries

1. Make request mutation plus semantic audit atomic, or use an explicit audit outbox.
2. Remove the stale email-template source guard.
3. Classify every source-text assertion as behavior, architecture, lint, or obsolete.
4. Move behavior to rendered/unit/integration tests.
5. Move real architecture rules to AST/import-boundary tools.
6. Consolidate `/ws/notifications` into one transport with typed subscribers.

### P2 — Delete or deepen

1. Remove unreachable frontend modules and their dependency/test residue.
2. Delete shallow event/status facades or give them real durability/policy.
3. Replace dynamic analytics exports with explicit domain imports.
4. Remove module-existence tests that do not verify behavior or a meaningful boundary.

### P3 — Reduce inventory maintenance

1. Remove the unused `httpx2` dependency.
2. Audit direct versus transitive dependency pins.
3. Replace stale hand-maintained file catalogs with decision-focused documentation or generated inventories.
4. Share Resend engagement-summary semantics across the two history views.

## Verification performed

- `cd apps/web && pnpm tsc --noEmit` — passed.
- `cd apps/web && pnpm lint` — passed.
- `cd apps/web && pnpm test --run tests/react-regressions-source.test.ts` — 310 passed, 2 failed due to the committed API-boundary and email-template-version guards.
- `cd apps/web && pnpm test --run tests/surrogate-application-tab.test.tsx` — 6 passed.
- Focused backend Ruff check across application code and representative architecture/facade tests — passed.
- Static import/caller searches, targeted source inspection, Git history/blame, and deletion/adapter analysis were performed.

A full backend/frontend test run was intentionally not used as audit evidence because the worktree contained substantial concurrent feature work. No product code was modified as part of this audit.
