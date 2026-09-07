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
| Organization control over internal staff access | Editable role presets plus individual permission additions accepted | Role creation, exception limits, delegation |
| People included in the first redesign | Internal agency staff and platform support accepted | Support access boundaries |
| Module and action permissions | Awaiting prerequisite decisions | Shared capabilities, dependency rules, configuration UI |
| Record and sensitive-data access | Awaiting prerequisite decisions | Assignment, teams, field restrictions, linked records, exports |
| Approval and background execution | Awaiting prerequisite decisions | Activation, retries, revocation, workflow and campaign authority |
| Migration and verification | Awaiting target behavior | Existing access comparison, rollout, recovery, completion criteria |

## Round 1 decisions

1. Prioritize both predictable staff access and easier permission configuration.
2. Agency administrators need editable role presets and individual permission additions. A selected person may need more access than others with the same role.
3. Limit the first redesign to internal agency staff and platform support.

Individual restrictions below role defaults, role creation, record scope, delegation limits, and support access have not been decided. Interview questions use the native tool that waits for a response.

## Round 2 pending

1. Whether individual exceptions can only add permissions or can also remove inherited permissions.
2. Whether record visibility should be configured separately from action permissions, including assigned-record and stage-based access.
3. How platform support obtains access to an agency's records.

## Working glossary

These definitions are discussion terms, not an approved data model.

| Term | Meaning |
|---|---|
| Organization | An agency whose data and access are isolated from other agencies |
| Membership | A person's association with an organization |
| Module | A product area such as donors, surrogates, workflows, or campaigns |
| Action permission | Authority to perform an operation such as viewing, editing, exporting, or activating |
| Role preset | A named starting set of access rules for a job function |
| Record scope | Which records an action permission applies to |
| Override | An explicit exception to inherited access rules |
| Effective access | The final access a person has after applicable rules are evaluated |
| Approval | Human authorization required before a particular operation proceeds |
| Module availability | Whether an organization has a feature enabled, separate from a member's authority to use it |

## Decision log

- Accepted: editable role presets with individual permission additions. Role-wide changes alone cannot cover a person who needs higher access than peers; exception precedence and administration limits remain open.
- Accepted: internal staff and platform support form the first-release scope. External professionals and participants are outside this milestone.
