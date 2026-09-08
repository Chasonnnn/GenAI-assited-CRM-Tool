# Platform upgrade roadmap

Date: 2026-09-07. Status: proposed priorities; implementation and external activation are separate tasks.

## Recommended sequence

| Order | Work | Reason | Completion gate |
|---|---|---|---|
| 1 | Build the tested permission foundation | The agreed product model now supports a focused implementation contract | Current behavior captured, action/scope contract reviewed, and migration differences identified |
| 2 | Build permission administration and one approval-handoff journey | Prove the selected UI and record rules together before expanding them | Admin configures access; Intake approval, Case Manager claim, retained collaboration, and removal work in an isolated surrogate/donor journey |
| 3 | Apply personal/organization authority and modularize workflow/campaign execution | Shared execution must honor the new authority rules before broader activation | Audiences, actions, publication, revocation, proposer departure, approvals, and retries are verified |
| 4 | Complete donor journeys and module-by-module permission migration | Finish existing donor investment on the tested foundation | Both donor types work end to end; UI, API, jobs, exports, and linked-record access agree for each activated module |
| 5 | Simplify form and workflow creation | Stable behavior and permissions make the new creation experience easier to maintain | Representative staff can publish a form and configure a common workflow without developer assistance |
| 6 | Rebuild reporting with a Meta MCP connection per organization | The existing direct integration is blocked by Meta app approval; useful reporting needs verified organization-specific data | A reconciled acquisition report supports a real budget or follow-up decision |
| 7 | Extend the shared UI improvements across the platform | Apply patterns proven in the earlier work | Priority journeys use consistent navigation, components, and onboarding, with measured usability and performance improvements |

Twilio setup and controlled verification should start early as a bounded separate work item. Provider setup can take elapsed time without blocking donor email or the rest of the roadmap. Complete donor SMS after the applicable consent, record-access, and messaging paths are ready.

Global UX discovery and shared visual rules also start early. Each feature adopts those rules as it changes; broad remaining screen migration comes later.

The role-editor visual direction is selected: variant 2. The [permission execution plan](permission-upgrade-execution-plan.md) defines the first implementation packages, parallel work, and activation gates. Operations defaults remain open; they do not block behavior-preserving extraction or work on the agreed roles.

The first foundation batch is implemented and verified locally: permission resolution, workflow definition rules, template editing authorization, and permission-cache correction. The [module refactor plan](permission-module-refactor-plan.md) maps the remaining record, workflow, campaign, form, reporting, and UI work. The upgraded policy and administration UI are not yet active.

## 1. Permissions and module foundations

- [ ] Inventory module availability, action permissions, record scope, ownership, field restrictions where needed, and approval requirements separately.
- [ ] Define a small set of understandable role presets, with module-level grouping and explicit exceptions.
- [ ] Decide how administrators inspect effective access and the reason an action is denied.
- [ ] Map current roles and overrides to proposed behavior; identify every access expansion and loss before migration.
- [ ] Define shared capability boundaries for record access, events, templates, messaging, workflow actions, and campaign audiences. Keep donor, surrogate, and intended-parent domain rules separate.
- [ ] Apply the proposed model to one donor journey before committing to platform-wide implementation.

The current permission registry and resolution service already exist. Modularization can reduce duplicate checks, but the permission problem also requires clear product rules. A replacement authorization engine is not a prerequisite; decide whether one is needed after the policy inventory.

## 2. Donor completion

- [ ] Create a capability matrix for egg donors and sperm donors covering manual creation, hosted intake, Meta intake, duplicate handling, review, ownership, stages, tasks, appointments, documents, correspondence, matches, search, reporting, workflows, campaigns, and email.
- [ ] Mark each capability as implemented, locally verified, provider-verified, or deployed-verified. Reproduce reported failures before assigning fixes.
- [ ] Define the default journey: intake or manual creation → review and duplicate resolution → assignment → follow-up task → approved welcome communication → application or screening → next-stage handoff.
- [ ] Confirm subtype-specific stages and required information with operations staff. Reuse configurable pipelines without assuming surrogate clinical rules apply to donors.
- [ ] Seed editable donor workflow and email templates for new and existing organizations, without overwriting local customization or enabling sends automatically.
- [ ] Verify trigger coverage, audience filters, template variables, approval behavior, delivery history, unsubscribe handling, delays, retries, and archived-record handling across workflows and campaigns.
- [ ] Verify donor visibility and action access across global surfaces; define the exit from beta availability.
- [ ] Complete browser journeys for both donor types and permission-negative tests, then record live provider and deployment verification separately.

Current evidence: donor workflow and campaign code/tests exist. The system workflow seeder inspected on this date uses the default pipeline; donor starter workflows need a focused design and seeding review. The September 6 local QA report explicitly excludes live email delivery, Meta synchronization, and scheduled workers. Older audit gap lists must be reconciled against later fixes before becoming tickets.

AI context and donor-cycle sharing remain separate decisions under the existing relationship plan. They should not silently expand the first donor completion milestone.

## 3. Workflow and campaign modularization

- [ ] Trace execution, scheduling, audience selection, subject adapters, approval, template rendering, delivery, and activity recording to identify duplicate ownership.
- [ ] Extract one shared capability at a time, starting with duplication exposed by donor completion.
- [ ] Make supported record types and actions explicit so unsupported combinations are rejected before activation.
- [ ] Preserve saved workflow definitions, campaign snapshots, in-flight jobs, and approval state; document any required migration and rollback.
- [ ] Test a change to a shared action across surrogate and donor consumers, including retry and failure paths.

Keep refactor scope tied to a concrete behavior or maintenance problem. A full platform rewrite is outside this roadmap.

## 4. Permission migration and administration

- [ ] Replace inconsistent local role checks with the agreed policy entry points, module by module.
- [ ] Use effective permissions consistently in navigation, screens, API operations, background execution, reports, and exports.
- [ ] Build administration around role presets, module groups, clear overrides, and an effective-access preview.
- [ ] Compare old and proposed access for existing roles and overrides before switching each module; review all differences.
- [ ] Verify denial, cross-organization access, record ownership, privilege escalation, and CSRF boundaries as applicable.
- [ ] Retain audited permission changes and a recovery path for accidental administrator lockout.

## 5. Form builder and workflow creation

- [ ] Observe staff creating one intake form and one common follow-up workflow; record completion time, mistakes, and requests for help.
- [ ] Prototype form creation first: choose record type and starter template, edit fields, preview, publish.
- [ ] Prototype workflow creation next: choose goal or starter template, select trigger, configure actions, preview effects, test, activate.
- [ ] Keep advanced branching and configuration available through progressive disclosure.
- [ ] Make recipient, subject type, timing, required fields, and approval consequences visible before activation.
- [ ] Preserve existing forms, submissions, saved workflows, and in-flight executions during editor migration.
- [ ] Validate the redesigned journeys with representative staff and compare against the baseline.

## 6. Reporting and Meta data

Proposed first focus: acquisition performance. Operations reporting follows unless current user priorities change this order.

Confirmed direction, 2026-09-07: the existing direct Meta integration is stale because Meta app approval could not be obtained. Use a separate Meta MCP connection for each organization. Existing spend-sync code is reference material for reusable data handling, not an available ingestion path or an alternative awaiting selection. The MCP provider and its supported authentication, tools, and unattended execution still need verification.

- [ ] Select the first decisions the report must support: which source to fund, which leads need attention, or where the funnel stalls.
- [ ] Define spend, leads, qualified leads, conversion, cost per qualified lead, and cost per conversion. Specify cohorts, dates, attribution, and subtype-specific stage mappings.
- [ ] Select and verify a Meta MCP provider that supports organization-specific authorization, required spend and campaign data, and scheduled background reads. Confirm that its setup can work under the app-approval constraint.
- [ ] Add organization-admin connection, account selection, connection testing, reconnection, and disconnection. Bind credentials and allowed ad accounts to authenticated organization membership; isolate jobs, stored data, and caches by organization.
- [ ] Reuse applicable spend storage, normalization, reconciliation, and reporting code behind the MCP ingestion path. Identify and disable superseded direct-sync schedules during migration without deleting historical data.
- [ ] Verify cross-organization denial, revoked credentials, partial responses, retries, and duplicate ingestion. Treat connection success and a successful scheduled refresh as separate checks.
- [ ] Make refresh cadence configurable by organization. Proposed default: daily ingestion with weekly review; aggregation period and refresh cadence are separate settings.
- [ ] Support retries, backfill, reconciliation, timezone/currency handling, attribution gaps, and visible freshness or sync failures.
- [ ] Reconcile a sample period against Meta and CRM records; distinguish platform-reported outcomes from CRM-observed outcomes and avoid duplicate spend across breakdowns.
- [ ] Build the report with drill-down to source records and distinct donor/surrogate views where definitions differ.
- [ ] Add operational views for workload, overdue follow-up, and stalled records after agreeing their definitions.

## Twilio completion

- [ ] Inventory organization credentials, sending routes, sender setup, callback endpoints, readiness state, and deployment prerequisites without exposing secrets.
- [ ] Confirm the first supported use case. Existing relationship planning specifies organization-owned transactional SMS; a conversation inbox is a separate scope decision.
- [ ] Verify queue and provider failure behavior locally, including duplicate callbacks, retries, and uncertain delivery outcomes.
- [ ] Arrange explicitly authorized test numbers and controlled live sends; verify receipt, callbacks, replies where supported, opt-out handling, and consent enforcement.
- [ ] Verify intended record types and workflow/campaign consumers independently; do not infer donor readiness from surrogate success.
- [ ] Record setup, automated tests, live provider verification, and production activation as separate gates.

## Global UI and onboarding

- [ ] Begin with an inventory of navigation, page composition, spacing, density, typography, forms, tables, and loading/error states using the existing component system.
- [ ] Agree common patterns before implementing the builder and reporting redesigns.
- [ ] Preserve light donor and intended-parent layouts while sharing common components and behavior.
- [ ] Identify the first useful action for each role and remove unnecessary onboarding steps.
- [ ] Measure task completion, assistance needed, and load/interaction times before and after changes.
- [ ] Apply proven patterns to remaining high-use screens, including responsive and keyboard behavior.

## Delivery cadence

Plan in rolling monthly priorities and small independently reviewable releases. Re-estimate each milestone after its scope and completion gate are agreed; staffing and provider readiness are not yet specified, so calendar commitments would be premature.

First implementation cycle: preserve and isolate current permission resolution, complete the action/scope contract, refine the selected UI, and reconcile donor/provider gaps in parallel. First working milestone: permission administration plus an isolated approval-handoff journey. Complete the module's access paths and automation authority before production activation.

Every milestone records implementation, automated checks, browser checks, provider checks where relevant, migration readiness, and deployment status separately. This plan does not authorize external sends or deployment.

## Repository evidence inspected

- `apps/api/app/services/permission_service.py`: current effective-permission resolution and overrides.
- `apps/api/app/services/template_seeder.py`: disabled system workflow seeding and default pipeline resolution.
- `apps/api/tests/test_donor_workflows.py`: donor subject and workflow integration tests.
- `apps/api/tests/test_donor_campaigns.py`: existing donor campaign test surface, identified but not rerun.
- `apps/api/app/services/meta_sync_service.py`: existing hierarchy, daily spend, and schedule code; the direct integration is stale and blocked by Meta app approval according to the user's clarification.
- `apps/api/app/services/analytics_meta_service.py`: existing Meta analytics with surrogate stage mapping in the inspected funnel path.
- `apps/api/tests/test_twilio_readiness.py`: local cached readiness contracts, not live provider proof.
- `docs/relationship-integration-plan.md`: accepted relationship rules, light record layouts, and SMS scope.
- `output/donor-live-qa-2026-09-06/report.md`: prior local QA coverage and explicit verification limits; not rerun for this planning task.
- `docs/donor-integration-audit-2026-09-05.md`: historical baseline and shared capability direction; gap list predates later integration work.
