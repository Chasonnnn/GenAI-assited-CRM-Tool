# Permission system design

Status: discovery. Initial product direction accepted; detailed access rules remain open.

## Confirmed context

- The user finds the current permission system difficult to manage.
- The platform needs deeper donor integration and continued workflow and campaign modularization.
- This discussion will define the desired permission behavior before implementation.
- Organization isolation, centralized enforcement, CSRF, and human review of AI-authored messages remain repository requirements.

## Decision tree

| Decision | Status | Dependent decisions |
|---|---|---|
| Primary problems and success criteria | Predictable staff access and easier configuration accepted; concrete scenarios pending | Acceptance scenarios, migration priority, administration experience |
| Organization control over internal staff access | Agency edits Intake/Case roles; Admin and Dev protected; one role plus removable action/scope additions | Delegation limits, effects of role changes |
| People included in the first redesign | Internal staff prioritized; no concrete platform-support access use case identified | Existing developer-access compatibility review; new support mechanism deferred in the proposal |
| Module and action permissions | Campaign editing/sending separate; workflow editing/activation share Manage Workflows | Other action groups, shared capabilities, dependency rules, configuration UI |
| Record and sensitive-data access | Case Managers see/edit all Approved-and-later records; owner at handoff retains Intake collaborator access for information updates until removed | Interaction with phase limits, sensitive data, linked records, exports |
| Approval and background execution | Applicant approval is an explicit permission; approved donors enter a shared claim pool | Workflow activation, retries, revocation, background authority |
| Personal and organization content | All three support both scopes; personal work private from peers with audited Admin management; personal actions limited to assigned/collaborated records | Organization management, publication, background authority |
| Migration and verification | Awaiting target behavior | Existing access comparison, rollout, recovery, completion criteria |

## Round 1 decisions

1. Prioritize both predictable staff access and easier permission configuration.
2. Agency administrators need editable role presets and individual permission additions. A selected person may need more access than others with the same role.
3. Limit the first redesign to internal agency staff and platform support.

Interview questions use the native tool that waits for a response.

## Round 2 decisions

1. Individual exceptions add permissions. An administrator can remove an addition to restore the role baseline; this does not deny a permission inherited from the role.
2. Configure record scope separately from action permissions. Exact scope options and combinations remain open.
3. The user has no concrete platform-support record-access use case. Defer a new support-access mechanism in the proposal; do not infer new standing access or changes to existing developer access.

## Round 3 decisions

1. Agencies edit the supplied role presets; they do not create custom roles.
2. Each person has one role preset plus individual additions, rather than combining multiple roles.
3. Record scope is configured per module. A role can cover all donor records while covering only assigned surrogate records.
4. The supplied roles are Intake Specialist, Case Manager, Admin, and Dev.

## Round 4 decisions

1. First-release record scopes support assignment, pipeline stages, and all agency records. Queue membership does not introduce an additional visibility rule in this milestone; existing queue workflows still need compatibility review.
2. Viewing and editing share one record scope within each module. Their action permissions remain distinct.
3. Campaign editing and sending are separate permissions. Human approval requirements remain a separate decision.

## Round 5 decisions

1. Surrogate, egg-donor, and sperm-donor pipelines each support before-approval, post-approval, or both for access, with a boundary defined for each pipeline.
2. Individual additions can explicitly widen a module's record scope. Adding an action alone never widens scope.
3. Agency administrators can edit Intake Specialist and Case Manager baselines. Admin retains full agency authority; Dev remains controlled by the platform. Repository invariants still apply to every role.

## Round 6 decisions

1. Applicant approval is an explicit permission, granted to Intake and Admin by default and configurable for Intake. No separate reviewer is required for ordinary applicant approval; protected Dev authority remains unchanged.
2. Approved donors enter a shared pool for Case Managers to claim, mirroring the surrogate handoff. Whether egg and sperm donors share a physical pool remains an implementation/design detail to resolve.
3. The Approved milestone starts the post-approval phase. A person authorized to approve a record may lose ordinary access after the transition; default post-handoff access and the approval transition contract still need agreement.

## Round 7 decisions

1. Assignment and phase/stage limits must both match when configured together.
2. Case Managers need access to all relevant records for matching. Assigned-only access is not their intended default; whether all includes before-approval records and which other modules are needed remains open. No pool-summary restriction was accepted.
3. Workflow editing and activation use one Manage Workflows permission. Unlike campaign editing/sending, these actions are not separated.

## Round 8 decisions and requirements

1. Case Managers see all Approved-and-later donor/surrogate records regardless of owner; before-approval records are outside the default scope.
2. Retain shared view/edit scope: a Case Manager with Edit can edit all records within that scope.
3. Intake works from New through before-approval, then hands off to a Case Manager or pool. Some Intake Specialists continue following records previously assigned to them and update information at a Case Manager's request. An assigned-before-approval-only default does not satisfy this requirement; the retained relationship and actions still need agreement.
4. Preserve personal and organization separation for campaigns, workflows, and templates. Their content visibility and authority to act on records must be resolved separately.

## Round 9 decisions

1. Automatically retain the Intake owner at the approval handoff as an Intake collaborator; other people can be added explicitly when needed. Do not infer continuing access for everyone who ever owned the record.
2. The Intake collaborator can view and update normal information without an additional system approval step. Stage changes and reassignment remain separate permissions; this is not full Case Manager authority.
3. Retained access lasts while the person is eligible staff, until a Case Manager or Admin removes it. There is no automatic expiry period or later-stage cutoff.

## Round 10 decisions

1. Personal and organization scope apply to campaigns, workflows, and templates. Personal campaign support is part of the redesign.
2. Agency Admins may inspect and manage personal work with an audit trail. Personal work is private from peers, not from agency administrators.
3. Personal workflows and campaigns may act on currently assigned records and records where their owner is an Intake collaborator. Visibility of other records does not extend personal automation/campaign reach; underlying action permissions remain relevant.

## Round 11 pending

1. Who can manage or publish organization content.
2. Whether publishing personal content creates an organization copy or changes/shares the original.
3. How enabled/scheduled work responds when its creator loses needed access or leaves the agency.

## Remaining decisions

- Interaction of retained Intake access with phase constraints, and claim behavior for nondefault assigned-only scopes.
- Organization ownership, publication, and sharing rules for campaigns, workflows, and templates.
- Whose authority governs background execution and how revocation affects queued work.
- Permission administration limits, role changes, revocation timing, linked-record access, and migration defaults.

## Approval baseline from current source

- Surrogates have a protected Approved gate and move to the Surrogate Pool at the gate. Approved is categorized as intake, while Case Manager record visibility begins at Approved; these overlapping rules need one explicit target definition.
- Egg donors enter the post-approval category at Ready to Match; sperm donors enter it at Available. Neither donor pipeline currently has a protected approval gate or equivalent ownership handoff.
- Donor stage-correction approval concerns requested backward stage changes. It is not applicant acceptance.
- Sources: `apps/api/app/core/stage_definitions.py`, `apps/api/app/core/surrogate_access.py`, `apps/api/app/services/surrogate_events.py`, `apps/api/app/services/donor_service.py`. Source inspection only; live organization configuration was not checked.

## Personal and organization baseline from current source

- Workflows and email templates have explicit personal/org scope. Campaigns currently have organization ownership and creator attribution, without personal scope.
- Personal workflows restrict editing to their owner; personal templates allow Admin/Dev editing as well. The target administrator policy needs one explicit definition.
- Personal workflows currently act on records owned by the workflow owner, not every record the person can view. Campaign recipient filters are organization-wide today.
- Sources: `apps/api/app/services/workflow_access.py`, `apps/api/app/services/workflow_triggers.py`, `apps/api/app/routers/email_templates.py`, `apps/api/app/schemas/campaign.py`, `apps/api/app/services/campaign_service.py`. Source inspection only.

## Working glossary

These definitions are discussion terms, not an approved data model.

| Term | Meaning |
|---|---|
| Organization | An agency whose data and access are isolated from other agencies |
| Membership | A person's association with an organization |
| Module | A product area such as donors, surrogates, workflows, or campaigns |
| Action permission | Authority to perform an operation such as viewing, editing, exporting, or activating |
| Role preset | One supplied staff role; agencies edit Intake/Case baselines while Admin/Dev baselines remain protected |
| Record scope | Which records an action permission applies to |
| Override | A removable individual permission addition; it cannot deny a role permission in the proposed model |
| Effective access | The final access a person has after applicable rules are evaluated |
| Approval boundary | The Approved milestone, which begins post-approval access |
| Applicant approval | An authorized decision that the applicant has reached the Approved milestone; distinct from approval of a requested correction |
| Intake collaborator | A former Intake owner retained at handoff, or another explicitly added collaborator, with continued access for information follow-up |
| Action approval | Human authorization for a requested operation, separate from applicant approval |
| Module availability | Whether an organization has a feature enabled, separate from a member's authority to use it |

## Decision log

- Accepted: editable role presets with removable individual permission additions. Role-wide changes alone cannot cover a person who needs higher access than peers; removing an addition restores inherited permissions. Administration limits remain open.
- Accepted: configure record scope separately from permitted actions.
- Accepted: agencies edit supplied roles instead of creating custom roles; each staff member has exactly one role plus individual additions. This keeps role inheritance simpler while retaining person-specific flexibility.
- Accepted: record scope can differ by module, with the same scope for viewing and editing. First-release controls include assignment, stages, and all agency records; their combination remains open.
- Accepted: campaign editing and sending are separate permissions.
- Accepted: individual record scope may be explicitly widened and later restored; action additions do not implicitly widen scope.
- Accepted: agency configuration applies to Intake Specialist and Case Manager baselines; Admin and Dev baselines remain protected.
- Accepted: surrogate and both donor pipelines use before/post-approval permission concepts with their own approval boundary.
- Accepted: applicant approval requires an explicit permission, without a separate reviewer; Approved begins post-approval and approved donors enter a shared claim pool.
- Accepted: assignment and phase/stage limits combine with AND; Case Manager access should support matching across relevant records rather than defaulting to assigned-only.
- Accepted: one Manage Workflows permission covers workflow editing and activation.
- Accepted: Case Manager default scope includes all Approved-and-later donor/surrogate records regardless of owner, shared by viewing and editing.
- Accepted: retain the owner at approval handoff as an Intake collaborator, with viewing/information-update access until a Case Manager or Admin removes it; other collaborators require explicit addition.
- Accepted: personal and organization scope for campaigns, workflows, and templates, including new personal campaigns. Admin management of personal work is audited; peers cannot access another person's personal work.
- Accepted: personal workflows/campaigns act on currently assigned or Intake-collaborator records, subject to action permissions.
- Accepted initially: internal staff and platform support form the first-release scope. Round 2 identified no support use case, so the proposal defers a new support mechanism. External professionals and participants remain outside this milestone.
