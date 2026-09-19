# Permission UI mock-ups

Status: historical visual concepts, not screenshots of implemented behavior. These image-generation outputs use synthetic people and records. A production Roles editor and team/member access controls now exist; implementation evidence and remaining acceptance gaps are tracked in [verification](../../permission-upgrade-verification.md).

The user preferred the role editor and selected [variant 2](role-variants/README.md) as its visual direction.

## 1. Roles

[Full image](01-roles.png)

![Role setup](01-roles.png)

Module scope appears above actions. Admin and Dev are protected. Operations shows Setup pending. The illustrated switches are a sample configuration, not a complete default-permission specification.

## 2. People

[Full image](02-people.png)

![Individual access](02-people.png)

Inherited access, individual additions, and retained collaboration appear separately. The Surrogates selector applies to the role and addition sections; the collaboration list illustrates relationships across modules. A refinement should make that distinction explicit.

Alice has a surrogate stage-change addition in this example.

## 3. Check access

[Full image](03-check-access.png)

![Access explanation](03-check-access.png)

The concept explains both the granted action and the record-access route. The settled implementation is a visibility-only checker: action permission is evaluated separately. Do not treat the illustrated Edit conclusion as the current checker contract. Linked intended-parent access remains separate.

## Open design work

- Confirm the navigation and preferred screen structure.
- Show adding record scope, reviewing changes, role changes, and collaborator removal.
- Show personal versus organization authority in workflow, campaign, and template controls.
- Verify responsive layouts, interaction states, and keyboard behavior during implementation.

Operations defaults are settled in the permission model; accepting the live controls remains separate from choosing these visual concepts.

[Permission model](../../permission-system-design.md) · [Generation prompts](prompts.md)
