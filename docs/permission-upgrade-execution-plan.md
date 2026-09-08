# Permission upgrade execution plan

Status: permission version 2 and its affected module refactors are implemented locally. Production organizations remain on version 1 until reviewed activation. The selected role editor is Studio variant 2.

## Delivered packages

| Package | Result | Boundary |
|---|---|---|
| Permission core | Protected Admin/Dev, editable supplied roles, individual additions, explicit role-change review, current membership checks | Actions remain separate from record scope |
| Record scope | Assignment, phase/stage rules, individual scope additions, retained Intake collaboration, access explanations | One SQL scope feeds lists, counts, details, linked work, and reports |
| Approval | Surrogate, egg-donor, and sperm-donor approval gates; retained Intake owner and claim pool | Approval, stage changes, assignment, and ordinary editing remain distinct actions |
| Organization authority | Durable workflow/campaign authority, personal audience rechecks, safe publication copies and proposer credit | Organization work survives proposer departure; personal work uses its owner's current authority |
| Administration UI | Roles, People, Check access, migration review, individual additions, role carryover review | Server capabilities govern controls and inherited access has no individual deny |
| Consumer integration | Records, notes/interviews/profile, search, tasks, matches, attachments, appointments, status corrections, reporting, submission review, AI-approved actions | Related record access follows the same tenant and scope constraints |

Detailed checks and local commit status are in [permission-upgrade-verification.md](permission-upgrade-verification.md).

## Agreed defaults

- Intake: assigned records before approval, retained collaboration after handoff, configurable applicant approval.
- Case Manager: all records from Approved onward; actions remain configurable.
- Operations: organization workflow/campaign/template management and record/report viewing; no record writes or sending by default.
- Admin/Dev: protected administration authority within organization boundaries.
- Reports and exports: the viewer's record scope; organization advertising spend requires unrestricted donor and surrogate scope.
- Form submissions: linked submissions follow record access; unlinked intake belongs to Intake/Admin/Dev. Review is separate from form-building authority.

## Migration and activation

1. Apply additive migrations `20260907_2200_perm_policy`, `20260907_2210_record_scope`, and `20260907_2220_work_authority` with their matching application version. Existing organizations continue using version 1.
2. Inspect the per-organization preview: role and individual action changes, record-scope changes, uncertain historical handoffs, old pool grants, and existing execution items.
3. Resolve each legacy individual revoke by explicit removal or a meaningful role-wide denial. Protected-role and already-denied permissions cannot use a no-op role resolution.
4. Review historical approval ownership and unknown phases using explicit evidence. Do not infer collaborators from every past owner.
5. Resolve existing workflow/campaign execution before activation. Unreviewed organization execution cannot silently acquire authority.
6. Activate the exact reviewed preview. The server rechecks membership, configuration, records, and execution state under the organization lock; stale reviews require regeneration.
7. Verify each activated organization's real configuration and operational journeys before broadening rollout.

Schema downgrade rejects active version 2 policies and personal campaigns that the old schema cannot represent. A rollback after activation requires a reviewed data and authority plan. The migration retains inserted Approved stages because live records or configuration may reference them.

## Remaining platform sequence

| Order | Work | Start condition |
|---|---|---|
| 1 | Production rehearsal and first organization activation | Exact committed version validated against an isolated production-shaped copy; explicit release authorization |
| 2 | Remaining donor journeys and provider verification | Shared record and execution contracts stable; synthetic integration tests pass |
| 3 | Workflow and form-builder UX simplification | Editing, publication, validation, and execution authority remain behind existing service interfaces |
| 4 | Reporting redesign and per-organization Meta MCP | Evaluate the MCP connector and organization authorization; reuse existing ingestion/reporting contracts where applicable |
| 5 | Remaining platform UI and onboarding | Apply proven permission and scope patterns module by module |

Twilio end-to-end provider testing and Meta MCP configuration remain separate work. The earlier Meta app integration is blocked by app approval; a per-organization MCP connection is the chosen direction to evaluate. No provider traffic or production activation is part of this local implementation.

## Refactor rules

- Extract a module boundary when a concrete consumer needs it; avoid a generic framework for every model.
- Keep transport in routers, use cases and transactions in services, and phase transitions in their domain modules.
- Keep action permissions, record datasets, organization execution authority, and presentation separate.
- Migrate every consumer of a changed decision together, including aliases, list counts, exports, and queued work.
- Use independent agent ownership for separate modules, then run shared negative tests and full affected suites at integration.
- Remove the legacy policy path after all organizations migrate and its removal is separately verified; do not preserve two permanent permission systems.

[Module ownership and refactor sequence](permission-module-refactor-plan.md) · [Product model](permission-system-design.md) · [Platform roadmap](platform-upgrade-roadmap.md)
