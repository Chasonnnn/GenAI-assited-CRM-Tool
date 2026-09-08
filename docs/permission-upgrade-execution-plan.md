# Permission upgrade execution plan

Status: implementation started. The first foundation batch is implemented and verified locally; server permission rules remain unchanged. Role-editor visual variant 2 is selected; Operations defaults and the complete permission matrix remain open.

## First delivery

- Extracted deterministic permission resolution while preserving scoped loading, existing precedence, audits, and transaction ownership.
- Extracted workflow trigger and action-ordering rules from the workflow CRUD service.
- Centralized template editing authorization across published templates and drafts.
- Fixed effective-permission cache identity and refresh after role/member changes.
- Passed 3,124 backend tests and 1,513 frontend tests, frontend type checking/lint, and changed-Python Ruff checks. Independent reviews found no actionable issues in these changes.

The [module refactor plan](permission-module-refactor-plan.md) defines the next owned packages. The new record-scope model, approval handoff, administration UI, and production migration remain subsequent milestones.

## Order

| Step | Deliverable | Completion gate |
|---|---|---|
| 1 | Tested permission foundation and agreed API contract | Existing resolution behavior is preserved; action, record scope, access source, and administration contracts are explicit |
| 2 | Working role editor and one approval-handoff journey | Admin configures access; Intake approves; Case Manager claims; retained Intake access and removal behave correctly |
| 3 | Personal and organization execution authority | Workflows and campaigns use the agreed audience and action rules; organization work survives proposer departure |
| 4 | Donor completion and module migration | Both donor types complete intake, handoff, follow-up, workflow, campaign, and communication journeys; every access path in an activated module uses the new policy |
| 5 | Builder simplification and reporting | Form/workflow creation uses stable capabilities; reporting uses verified organization-specific Meta MCP data |
| 6 | Remaining platform UI migration | Selected patterns are proven in real tasks before adoption across remaining screens |

Steps overlap at explicit boundaries. The UI can progress alongside step 1 after its API contract is agreed. Donor gap verification and provider readiness can run immediately. Workflow/campaign extraction follows the authority contract; the module's production switch follows complete consumer coverage.

## First implementation packages

### A. Preserve and isolate current resolution

- Capture current role defaults, organization role overrides, user grants/revokes, developer-only filtering, and tenant isolation in focused tests.
- Separate deterministic resolution from database loading inside the existing permission service where this supports testing and access comparison. Preserve its public entry points and actual precedence.
- Leave mutations, audit records, membership checks, and transaction ownership intact.
- Record callers and the list/detail/search/count/export/job paths that will need the new contract.
- Keep the current grant/revoke model during this behavior-preserving extraction. Its replacement belongs to the explicit migration package.

Gate: existing precedence and negative tests pass, affected Python checks pass, and no schema or externally visible access change is introduced. Preserve database round-trip counts; cross-request caching is outside this package.

### B. Define the new decisions and migration

- Define role baseline, individual additions, module record scope, approval boundary, and Intake collaboration using the agreed product model.
- Define one decision contract with the allowed action, covered record scope, and source of access. API and UI explanations derive from that decision.
- Keep surrogate, egg-donor, and sperm-donor stage/handoff rules in their domain modules. Shared authorization consumes those rules without hard-coded stage labels outside the canonical definitions.
- Define list filtering and single-record decisions together, including pagination and counts. Avoid per-record permission queries.
- Map current overrides and historical handoffs to the proposed model. Report access gained or lost, and require explicit resolution of existing individual denials.
- Specify additive schema changes and rollback behavior. Temporary old/new comparison ends after migration; it does not become a permanent second policy system.

Gate: reviewed action/scope matrix, API contract, migration examples, and old/new access differences. Keep Operations outside activation until its responsibilities, record access, and send authority are decided.

### C. Build the selected administration UI and first journey

- Implement the selected variant 2 role editor using existing UI primitives. Include scope selection, action controls, access preview, unsaved changes, and configuration-diff review.
- Add individual additions and access explanations against the same contract. Inherited permissions have no per-person deny control.
- Demonstrate a surrogate and an egg donor through approval, Case Manager claim, retained Intake follow-up, and collaborator removal in an isolated environment. Verify sperm-donor stage differences before expanding the demonstration.
- Test approval authority separately from ordinary editing, stage changes, and reassignment. Verify linked records require both parties' access.
- Verify atomic handoff/audit writes, duplicate handoff execution, paused and archived records, role changes, and departure. Removing collaboration must preserve access through another valid grant.
- Before activating either module, cover lists, details, search, counts, exports, notes, documents, tasks, matches, and affected queued execution. A successful detail-page demo is not module rollout completion.

Gate: Admin can explain a person's effective access; allowed and denied journeys match API, database queries, and rendered UI. No cross-organization or indirect access path bypasses the model.

### D. Apply personal and organization authority to automation

- Extract audience selection, subject adapters, action authorization, template resolution, delivery, and execution recording only where the new behavior requires shared ownership.
- Keep campaign Edit and Send separate. Manage Workflows covers editing and activation; executable actions still require authority.
- Personal work uses its owner's current assigned/collaborator audience and action permissions. Revocation is rechecked before queued personal actions.
- Organization work uses authorized organization configuration. Proposer departure does not stop it. Reach/action changes are revalidated before taking effect.
- Publishing creates independent organization copies with safe initial states and no live private-template dependency.
- Preserve saved definitions, campaign snapshots, in-flight jobs, approvals, retries, and idempotency during extraction.

Gate: denied actions, lost ownership, revoked permissions, proposer departure, publication, retry, and cross-organization tests pass for surrogate and donor consumers.

## Parallel work

| Workstream | Can start | Boundary |
|---|---|---|
| Permission core | Current behavior inventory and package A | One owner for resolution, scope semantics, and migrations |
| UI | Refine individual access and change review in variant 2; implement once the contract is agreed | No separate frontend permission rules; shared API types change with the contract owner |
| Verification and provider readiness | Reconcile donor gaps; inspect Twilio readiness; verify Meta MCP provider feasibility | Separate fixtures and environments; provider sends/activation need explicit authorization |

Keep one core behavior milestone active. Parallel work should produce a usable dependency or independent result; separate simultaneous rewrites of permissions, workflow execution, and campaign execution would overlap on the same rules.

## Working rules

- Each package states its user-visible outcome, owned files, required decisions, acceptance cases, and migration impact before implementation.
- Keep behavior-preserving refactors separate from permission changes in reviewable commits.
- Reuse existing services and introduce a shared abstraction when a concrete consumer needs it.
- Finish a small end-to-end journey before expanding to more modules.
- Run focused checks during development and full affected suites plus authorization/migration invariants at integration gates.
- Review old/new access differences before activating an organization or module. Avoid silent privilege expansion or administrator lockout.
- Record local implementation, automated tests, browser verification, provider verification, and deployment separately.

## Current source evidence

- `apps/api/app/services/permission_service.py` already loads defaults and overrides, resolves actions, and owns permission mutation/audit behavior.
- `apps/api/app/services/record_access_service.py` already provides a shared record entry point. Its additional role/record-scope checks currently apply specifically to surrogates.
- `apps/api/app/core/surrogate_access.py` contains SQL visibility filters and single-record checks; both are migration surfaces.
- `apps/api/tests/test_permissions.py` covers override precedence, developer-only restrictions, and organization isolation.
- `apps/api/tests/test_surrogate_permission_access.py` exercises visibility and editing across related surfaces.
- `apps/web/lib/api/permissions.ts` exposes the existing grant/revoke API. The selected UI needs the new contract before production wiring.

These files were inspected for planning; tests were not run for this document-only change.

[Permission model](permission-system-design.md) · [Selected visual direction](mockups/permissions/role-variants/README.md) · [Platform roadmap](platform-upgrade-roadmap.md)
