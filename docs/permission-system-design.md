# Permission system design

Status: discovery. No replacement permission model has been selected.

## Confirmed context

- The user finds the current permission system difficult to manage.
- The platform needs deeper donor integration and continued workflow and campaign modularization.
- This discussion will define the desired permission behavior before implementation.
- Organization isolation, centralized enforcement, CSRF, and human review of AI-authored messages remain repository requirements.

## Decision tree

| Decision | Status | Dependent decisions |
|---|---|---|
| Primary problems and success criteria | Awaiting round 1 | Acceptance scenarios, migration priority, administration experience |
| Organization control over internal staff access | Awaiting round 1 | Role presets, custom roles, individual exceptions, delegation |
| People included in the first redesign | Awaiting round 1 | Membership boundaries, external access, support access |
| Module and action permissions | Awaiting prerequisite decisions | Shared capabilities, dependency rules, configuration UI |
| Record and sensitive-data access | Awaiting prerequisite decisions | Assignment, teams, field restrictions, linked records, exports |
| Approval and background execution | Awaiting prerequisite decisions | Activation, retries, revocation, workflow and campaign authority |
| Migration and verification | Awaiting target behavior | Existing access comparison, rollout, recovery, completion criteria |

## Round 1

1. Which two problems should the redesign solve first: assigning access, staff being blocked, explaining effective access, or supporting changes to modules? Obtain one real example.
2. How much control should an organization have over internal staff access: fixed roles, configurable role presets, or unrestricted per-user configuration?
3. Which people belong in the first redesign: internal agency staff, platform support, or external participants and partners?

Recommendations pending user decisions: prioritize understandable administration and predictable staff access; use configurable role presets with a small number of explicit exceptions; focus first on internal staff and explicitly define platform-support boundaries, with external portal access as a separate milestone unless needed now.

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

No design decisions have been accepted. Record each accepted decision with its rationale, alternatives, consequences, and unresolved dependencies.
