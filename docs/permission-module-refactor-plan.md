# Module refactors for the permission upgrade

Status: permission v2 and its shared record filters are implemented in draft PR #691 behind organization activation. Existing organizations remain on v1 until their access and execution reviews are resolved. Integrated verification is recorded in `permission-upgrade-verification.md`. No deployment, production migration, or provider testing has occurred.

## Implemented boundaries

| Module owner | Implementation | Stable interface and responsibility |
|---|---|---|
| Permission policy | `core/permissions.py`, `core/permission_resolution.py`, `services/permission_service.py`, `services/permission_policy_service.py` | Resolve action keys from loaded baselines and additions; protected Admin/Dev administration; lock configuration changes and bind activation to a reviewed digest |
| Record scope | `services/record_scope_service.py`, `services/record_access_service.py`, `core/surrogate_access.py` | `build_visibility_filter`, `build_linked_visibility_filter`, `can_access_record`, and `get_record_with_access`; the same record set for View/Edit, with actions checked separately |
| Approval handoff | `services/approval_handoff_service.py`, surrogate/donor status services | Canonical approval crossing, retained Intake collaboration, and pool ownership in the domain transaction; `record_phase` shares list/detail phase semantics |
| Workflow definitions | `services/workflow_definition_rules.py` | Trigger validation and action ordering independently of CRUD, execution, and authorization |
| Workflow authority | `services/workflow_access.py`, `services/workflow_execution_authority.py` | Human management, personal subject eligibility, organization execution snapshots, action authorization, retry/resume, and delivery admission |
| Campaign authority | `services/campaign_access.py`, existing campaign audience and run services | View/Edit/Send, personal versus organization ownership, viewer-scoped preview/recipient/count queries, durable execution audience, send authorization, recipient rechecks, and publication |
| Template authorization/publication | `services/email_template_access.py`, `services/email_template_publication.py` | Shared edit decisions and independent organization copies; proposal credit is separate from execution authority |
| Submission review | `services/form_submission_access.py` | Submission actions, unlinked Intake/Admin/Dev queue, linked record scope, form picker, and intake-lead access; builder authority remains in `manage_forms` |
| Application metadata | `services/form_application_access.py` | Record-scoped published form metadata and active link selection without builder access; explicit email-send permission before sending |
| Reporting | `services/analytics_access_service.py` and existing analytics services | Request-scoped authorized ORM dataset, including aliases; v2 request-only result reuse until cross-request scope invalidation has a reliable revision |
| Permission client | `lib/api/permissions.ts`, `lib/api/record-scopes.ts`, corresponding query hooks and permission components | Server capabilities, record rules, access explanations, reviewed changes, and cache invalidation; rendered validation remains part of the integration gate |

Action baselines and Operations defaults are settled in `permission-system-design.md`. Individual additions never remove role access. Operations has record View without record Edit by default. Legacy post-approval visibility controls no longer narrow v2 list, date, search, or claim-queue results.

## Record consumer coverage

| Surface | Integration |
|---|---|
| Surrogate and donor approval | Approved begins the post-approval phase; paused records use their prior stage; terminal records use usable history; unknown historical phase requires an explicit evidence-backed review |
| Donor records | Shared list/count/detail scope; owner changes require `assign_donors`; default personal creation assigns the creator; claim uses action, scope, organization, queue, and locking checks |
| Intended parents | Shared list/count/date/stat/detail scope; no applicant approval-phase restriction |
| Surrogate lists and queues | Shared list/date/stat scope; claim queue filters before pagination/count; claim and reassignment check record scope separately from assignment permission |
| Global search | Record, note, and attachment branches apply shared SQL filters before branch limits and global pagination; v1 branches retain legacy rules |
| Tasks and matches | Every linked participant must be visible; task list/count and match list/detail use the same subject rules |
| Appointments | Linked surrogate, donor, intended-parent, match, and transfer subjects use shared scope before list counts and pagination; detail follows the same rule after collaboration is removed |
| Attachments and correspondence | Subject access remains in the record adapter; attachment lists also use shared linked-subject filters |
| Dashboard and AI summaries | Donor attention, linked task/meeting lists, overdue counts, and AI dashboard statistics use the actor's scope |
| Intelligent suggestions | Rule matches and summary counts use module View plus shared scope; retained collaborators and individual additions are included |
| Forms | Submission lists filter before limits; candidate lists and manual links check record access; inaccessible automatic rematches stay in manual review; Operations can read visible linked submissions but cannot review |
| Record creation | `core/record_creation.py` separates Create from Edit across record CRUD, import approval/retry, and intake promotion |
| AI availability | Safe organization availability is separate from provider settings; current actor actions and linked-record scope apply to proposals, approvals, and task chat |
| Manual email | New manual template jobs recheck active actor, Send permission, template ownership, and linked scope before provider delivery; uncertain revoked retries require reconciliation |

Configuration mutations refresh active membership after acquiring the organization lock. Returning inactive members can have their existing scope additions inspected and removed; new grants require an active membership. Removing one grant preserves any remaining role, individual, or collaborator route.

Migration review persists per-record ownership and phase decisions. Legacy Intake pool grants require explicit removal or replacement with a scope addition. The activation snapshot includes unresolved records, grant decisions, exact current/proposed/gained/lost record-scope counts, and a record-state digest. These counts describe record scope; the permission preview reports action changes separately.

## Ownership and transaction rules

| Boundary | Owns | Must not own |
|---|---|---|
| Router | Authenticated session, CSRF, request/response validation, HTTP disclosure behavior | ORM queries, a second permission resolver, provider side effects |
| Permission service | Actions, organization configuration locks, audited administrative changes | Stage transitions, consent, audience materialization |
| Record scope service | Organization/member boundary, SQL inclusion, access sources, collaboration, migration review | Implicit action grants, domain status writes, provider access |
| Domain service | Record relationships, status invariants, domain audit/activity, commit or rollback | A parallel role/stage access matrix |
| Workflow/campaign use case | Management authority, immutable execution configuration, dispatch/retry admission | Ownership-based credit as proof of authority |
| Delivery service | Consent, suppression, provider routing, idempotency, final execution admission | Reusing stale enqueue-time authorization |
| Frontend | Server-state queries and permitted controls | Recomputing role, stage, or ownership rules as authorization |

Record scope helpers compose into SQL before pagination and aggregates. Single-record adapters check the action and reuse that scope. A scope grant alone never authorizes Edit, Send, approval, assignment, or builder changes. Public token flows keep their existing token-bound organization resolution.

Publication creates independent organization-owned work with proposal credit. Organization work continues when its proposer leaves. Personal work rechecks the owner's current membership, actions, and assigned-or-collaborator reach at execution and delivery.

## Next refactor sequence

### 1. Rehearse production activation

- Rehearse the exact committed version against an isolated production-shaped copy and inspect organization-specific access and execution changes.
- Activate only a reviewed organization after explicit release authorization; validate its operational journeys before broadening rollout.
- Remove legacy adapters after every organization has migrated and a separately validated change retires version 1.

### 2. Split workflow execution by concrete use case

Keep `workflow_definition_rules` as the definition validator and `workflow_execution_authority` as the authority boundary. Extract action execution from `workflow_engine_core` into existing action/adaptor modules by family: record changes, task creation, communications, and intake routing. Extract scheduled candidate selection separately from action execution.

Preserve immutable action snapshots, scheduling timestamps, idempotency keys, approval results, and retry/resume behavior. Each extraction requires an existing caller and behavioral tests. Keep one coordinator for engine/adaptor/worker changes so dispatch and final delivery cannot drift apart.

### 3. Split campaign lifecycle around the existing audience query

Keep `campaign_access` responsible for authority. Separate campaign definition CRUD, publication, audience preview/materialization, run state, and retry dispatch where the current service combines them. Continue extending the existing recipient-query implementation.

Preview, materialized recipients, retry selection, and delivery admission must agree. Consent, suppression, immutable launch content, skipped counts, and delivery locking stay with their current owners. Campaign definition/UI work can run alongside workflow refactoring after the shared action and delivery contracts are stable.

### 4. Separate form definition, intake routing, and review transactions

Keep builder definition/publication separate from `view_form_submissions` and `review_form_submissions`. Move submission review transport orchestration into focused use cases that own matching, audit, and transaction completion together. Consolidate the current retry path's intermediate commits before adding more routing actions.

Retain the explicit unlinked queue and shared linked-record access. Public intake, draft tokens, published-schema snapshots, file scanning, and duplicate detection remain independent boundaries. UI simplification follows this split; it does not require a new form engine.

### 5. Consolidate reporting datasets and invalidation

Keep metric calculation in existing analytics modules and supply the same authorized dataset to counts, charts, drill-downs, and exports. Group related metrics around an explicit dataset/query context as duplication appears.

Before restoring cross-request v2 caches, define a scope revision covering role rules, individual additions, collaborators, membership changes, and record ownership/stage/archive changes. Test revocation on the next request. Agency-wide reporting requires explicit authority; ordinary report access uses the person's record scope.

### 6. Refactor organization integrations, then broaden UI simplification

Meta spend synchronization already exists but is stale because Meta app approval is unavailable. Evaluate an organization-specific Meta MCP connection against that existing ingestion, account mapping, scheduling, deduplication, and reporting code. Configurable daily/weekly synchronization and its provider verification remain future work.

Twilio setup and provider testing remain unfinished. Keep organization connection configuration, consent, execution admission, and proposer credit separate. Do not treat passing local delivery tests as a completed Twilio setup.

Continue donor completion against the existing workflow/campaign code and tests. Default donor creation workflow, onboarding, and the remaining global UI polish belong in their own reviewed slices. Reuse server capabilities and established component primitives as each surface is simplified.

## Verification status

The integrated API suite, serial migration/outbox suite, frontend checks, fresh migration rehearsal, browser journeys, and local delivery state are recorded in [permission-upgrade-verification.md](permission-upgrade-verification.md). Focused lane selections overlap and are not additive.

[Execution sequence](permission-upgrade-execution-plan.md) · [Permission model](permission-system-design.md) · [Selected UI](mockups/permissions/2026-09-12-module-first-studio.png)
