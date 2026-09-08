# Module refactors for the permission upgrade

Status: first implementation batch implemented and verified locally. The action/scope model is agreed in principle; the full action matrix and Operations defaults remain open. These refactors do not activate new staff permissions or change production data.

## First batch

| Module | Extraction | Purpose |
|---|---|---|
| Permissions | `core/permission_resolution.py` | Calculate effective actions from loaded defaults and overrides without database access; keep scoped loading and audited changes in `permission_service.py` |
| Workflow definitions | `services/workflow_definition_rules.py` | Validate trigger configuration and action ordering independently of CRUD, execution, and authorization |
| Email templates | `services/email_template_access.py` | Share editing authorization across published templates, drafts, and draft tests; keep HTTP disclosure rules at each route |
| Permission client | `lib/hooks/use-permissions.ts` | Separate effective-permission caches by authenticated user and refresh dependent views after permission changes |

Existing policy differences remain explicit during extraction. In particular, template editing, published test-send, rollback, and sharing currently have different authorization requirements. The approved policy changes must replace those differences deliberately with updated tests and migration decisions.

Verification: 3,124 backend tests passed, including the serial migration/outbox group; 1,513 frontend tests, frontend type checking, and frontend lint passed. Ruff passed for changed Python files. Independent reviews found no actionable issues in permission resolution, workflow rules, template access, or permission caching. Six cache regressions failed before the fix and passed afterward. Tests used a dedicated disposable PostgreSQL 18.1 database; no provider sends or deployment were performed.

## Shared boundaries

| Owner | Responsibility | Consumers |
|---|---|---|
| Permission registry and service | Action keys, role baselines, individual additions, protected administration, effective-action calculation | API dependencies, settings, module authorization |
| Record access | Authenticated organization scope, record inclusion, list filters, single-record decisions, access sources | Records, search, tasks, files, correspondence, matching, submissions, reporting |
| Domain services | Valid transitions, approval handoff, record relationships, transaction and audit writes | Manual operations and authorized automated actions |
| Execution services | Personal or organization authority, candidate eligibility, queued-action rechecks, retries | Workflows, campaigns, delivery admission |
| Frontend | Display server capabilities and explanations, enable permitted queries, refresh changed access | Navigation, editors, record controls, reports |

Extend the existing registry, record service, workflow adapters, audience query, and delivery modules. An extraction needs a concrete caller or duplicated rule. Feature availability and beta gates remain separate from staff permission grants.

## 1. Record scope and approval handoff

Files: `services/record_access_service.py`, `core/surrogate_access.py`, surrogate/donor pipeline and handoff services, list/search/count/export consumers.

- Define query filters and single-record decisions from the same module rules. Organization scope comes from authenticated membership.
- Combine assignment and phase restrictions, then add explicit scope grants and retained collaborators.
- Keep donor subtype stages and surrogate stages in their domain definitions. Handle paused and archived records deliberately.
- Create the Intake-collaborator relationship and handoff audit atomically. Repeated handoffs must not duplicate access grants.
- Match and joint-document access requires authorization for each linked party.
- Preserve access through a second valid route after one grant is removed.

Gate: list/detail/search/count parity, no per-record permission query growth, cross-organization denial, handoff idempotency, next-action revocation, and reviewed migration of historical ownership and individual denials.

One owner coordinates scope filters and handoff writes. `test_surrogate_permission_access.py`, `test_record_capability_access.py`, and `test_surrogate_stage_role_permissions.py` are starting coverage. The old expectation that Intake loses access after approval must change only with the new behavior.

## 2. Permission API and administration

Files: `routers/permissions.py`, permission schemas, `lib/api/permissions.ts`, `lib/hooks/use-permissions.ts`, role/member settings pages.

- Return allowed actions, configured record scope, sources of access, and which settings the actor may edit.
- Use the same decision data for effective-access explanations and the role-editor preview.
- Implement selected visual variant 2 with additions-only member editing, protected baselines, change review, loading, errors, and unsaved-change handling.
- Carry authenticated organization/member identity into the complete permission cache contract. The first cache fix uses the existing user identity and self endpoint; the organization-wide cache migration is separate.
- Invalidate relevant record datasets when scope changes, alongside permission and administration views.

Gate: one user's cached permissions are never displayed for another user; configuration changes refresh affected views; UI controls agree with server denials. Operations remains outside activation until its defaults are settled.

## 3. Workflow admission and execution

Files: `services/workflow_access.py`, `workflow_triggers.py`, `workflow_engine_core.py`, `workflow_engine_adapters.py`, workflow/email job handlers, workflow router.

- Keep human management checks in `workflow_access.py`; route edit and activation through Manage Workflows plus required action authority.
- Use the same personal assigned-or-collaborator selection rule for events and scheduled sweeps.
- Separate execution authority from the actor recorded for credit or audit. Personal execution depends on current owner authority; organization execution uses authorized agency configuration.
- Check authority before dispatch, resume, retry, and provider admission. Revalidate configuration that expands actions or reach.
- Preserve execution APIs, result shapes, immutable action snapshots, schedule timestamps, idempotency keys, and provider routing.

Gate: collaborator eligibility, owner departure, permission removal after enqueue, organization execution after proposer departure, resume/retry organization binding, and approved-action snapshot behavior.

One execution owner coordinates the engine, adapters, and worker handlers. Existing tests include `test_workflow_trigger_scoping.py`, `test_workflow_task_sweeps.py`, `test_workflow_execution_retry.py`, `test_workflow_approvals.py`, and `test_workflow_email_outbox.py`.

## 4. Campaign actions, audiences, and template publication

Files: campaign router/service/schema/model and frontend API; template publication services; campaign/email/messaging job and dispatch modules.

- Give campaigns explicit View, Edit, and Send actions. Current campaign routes use email-template permission keys; that coupling must change with the reviewed role matrix.
- Add personal scope, owner, organization scope, and original-proposer attribution to the campaign contract. The server combines permission and lifecycle decisions for UI controls.
- Extend the existing `_build_recipient_query` for personal eligibility; do not create another audience engine.
- Align preview, recipient materialization, retry selection, and final email/messaging admission. Initial filtering alone cannot enforce revocation after enqueue.
- Make publication a transaction-owned use case: independent organization copy, draft/disabled initial state, authorized organization-template dependencies, original credit, and no usable private-source link.
- Preserve consent, suppression, immutable launch content, snapshots, delivery locking, and retry idempotency in their current owners.

Gate: edit-allowed/send-denied, peer-private campaigns, audited Admin access, publication rollback, revoked collaborator after enqueue, skipped counts, and continued organization execution after proposer departure.

Template publication and campaign CRUD can run separately after their shared copy contract is fixed. Run/retry plus email and messaging admission need one coordinated owner. Coverage starts with campaign recipient/run tests, donor campaigns, campaign/workflow messaging, template personal-scope tests, and delivery dispatch tests.

## 5. Forms, reports, and remaining UI

| Module | Refactor | Gate |
|---|---|---|
| Form submissions | One access adapter for list, detail, files, matching, and review; definitions/publication stay in forms | Filter before pagination; linked subjects use shared record access; define unlinked-intake access; preserve token-bound public flows |
| Reporting and exports | Supply one authorized dataset to counts, charts, drill-downs, and export; aggregation remains in analytics | Equivalent scope across outputs; cache identity reflects scope; changes invalidate cached results |
| Navigation and record controls | One capability selector using server decisions; preserve domain lifecycle checks | No duplicated frontend role/stage calculations; denied operations do not trigger unauthorized data requests |
| Integrations | Organization-owned connection/configuration and execution authority stay independent of proposer credit | Organization-bound credentials, jobs, account selection, and cache keys; revoked connections stop admission |

Agency-wide reporting beyond a person's ordinary record scope and access to unlinked intake submissions require explicit product rules before rollout. These decisions do not block the first extractions.

## Coordination

- Keep shared permission names, schema changes, and the API contract under one owner.
- Assign UI, workflow definition/publication, and verification work independently after their interfaces are fixed.
- Review each stable extraction independently, then validate the integrated application.
- Review old/new access differences before module activation. Temporary comparison support must have a removal gate.
- Commit behavior-preserving refactors separately from permission changes and migrations.

[Execution sequence](permission-upgrade-execution-plan.md) · [Permission model](permission-system-design.md) · [Selected UI](mockups/permissions/role-variants/README.md)
