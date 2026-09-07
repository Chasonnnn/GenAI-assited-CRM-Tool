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
| Module and action permissions | Campaign editing and sending are separate permissions | Other action groups, shared capabilities, dependency rules, configuration UI |
| Record and sensitive-data access | Per-module assignment/stage scope shared by view/edit; before/post-approval supported for surrogate and both donor types; individual scope widening explicit | Approval boundary, scope combination, sensitive data, linked records, exports |
| Approval and background execution | Awaiting prerequisite decisions | Activation, retries, revocation, workflow and campaign authority |
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

## Round 6 pending

1. Who may approve an applicant, and whether a separate reviewer is required.
2. How donor ownership is handed off at approval.
3. Which permission phase includes the approval milestone itself.

## Remaining decisions

- How assignment and phase/stage constraints combine.
- Whether workflow editing and activation have separate permissions, and whose authority governs background execution.
- Permission administration limits, role changes, revocation timing, linked-record access, and migration defaults.

## Approval baseline from current source

- Surrogates have a protected Approved gate and move to the Surrogate Pool at the gate. Approved is categorized as intake, while Case Manager record visibility begins at Approved; these overlapping rules need one explicit target definition.
- Egg donors enter the post-approval category at Ready to Match; sperm donors enter it at Available. Neither donor pipeline currently has a protected approval gate or equivalent ownership handoff.
- Donor stage-correction approval concerns requested backward stage changes. It is not applicant acceptance.
- Sources: `apps/api/app/core/stage_definitions.py`, `apps/api/app/core/surrogate_access.py`, `apps/api/app/services/surrogate_events.py`, `apps/api/app/services/donor_service.py`. Source inspection only; live organization configuration was not checked.

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
| Approval boundary | The pipeline milestone separating before-approval and post-approval access; inclusion of the milestone remains open |
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
- Accepted initially: internal staff and platform support form the first-release scope. Round 2 identified no support use case, so the proposal defers a new support mechanism. External professionals and participants remain outside this milestone.
