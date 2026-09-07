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
| Organization control over internal staff access | Supplied roles only, editable by agencies; one role per person plus removable individual additions | Protected permissions, delegation, effects of role changes |
| People included in the first redesign | Internal staff prioritized; no concrete platform-support access use case identified | Existing developer-access compatibility review; new support mechanism deferred in the proposal |
| Module and action permissions | Campaign editing and sending are separate permissions | Other action groups, shared capabilities, dependency rules, configuration UI |
| Record and sensitive-data access | Per-module assigned/stage/all scope; viewing and editing share the same scope | Scope combination, individual widening, sensitive data, linked records, exports |
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
4. The supplied roles are Intake Specialist, Case Manager, Admin, and Dev. Which permissions of Admin and Dev remain protected from agency edits is still open.

## Round 4 decisions

1. First-release record scopes support assignment, pipeline stages, and all agency records. Queue membership does not introduce an additional visibility rule in this milestone; existing queue workflows still need compatibility review.
2. Viewing and editing share one record scope within each module. Their action permissions remain distinct.
3. Campaign editing and sending are separate permissions. Human approval requirements remain a separate decision.

## Round 5 pending

1. How before-approval and post-approval phases should affect surrogate access, and whether the same model should apply to donors. The user proposed donor parity; exact boundaries need agreement.
2. How assignment and stage constraints combine when both are configured.
3. Whether an individual addition can explicitly widen record scope as well as add actions.
4. Whether workflow editing and activation should have separate permissions.
5. Which Admin and Dev permissions remain protected from agency configuration.

## Working glossary

These definitions are discussion terms, not an approved data model.

| Term | Meaning |
|---|---|
| Organization | An agency whose data and access are isolated from other agencies |
| Membership | A person's association with an organization |
| Module | A product area such as donors, surrogates, workflows, or campaigns |
| Action permission | Authority to perform an operation such as viewing, editing, exporting, or activating |
| Role preset | One of the platform-supplied staff roles, with permissions editable by the agency |
| Record scope | Which records an action permission applies to |
| Override | A removable individual permission addition; it cannot deny a role permission in the proposed model |
| Effective access | The final access a person has after applicable rules are evaluated |
| Approval | Human authorization required before a particular operation proceeds |
| Module availability | Whether an organization has a feature enabled, separate from a member's authority to use it |

## Decision log

- Accepted: editable role presets with removable individual permission additions. Role-wide changes alone cannot cover a person who needs higher access than peers; removing an addition restores inherited permissions. Administration limits remain open.
- Accepted: configure record scope separately from permitted actions.
- Accepted: agencies edit supplied roles instead of creating custom roles; each staff member has exactly one role plus individual additions. This keeps role inheritance simpler while retaining person-specific flexibility.
- Accepted: record scope can differ by module, with the same scope for viewing and editing. First-release controls include assignment, stages, and all agency records; their combination remains open.
- Accepted: campaign editing and sending are separate permissions.
- Accepted initially: internal staff and platform support form the first-release scope. Round 2 identified no support use case, so the proposal defers a new support mechanism. External professionals and participants remain outside this milestone.
