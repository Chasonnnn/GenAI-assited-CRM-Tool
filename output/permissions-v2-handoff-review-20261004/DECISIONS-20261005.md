# Approved migration decisions — 2026-10-05

The user approved these decisions after reviewing concrete ownership and workflow examples. Permission V2 activation remains on hold until the fixes are released and a fresh preview passes.

## Historical records

Preserve the current explicit active Intake assignee. Do not restore access from earlier ownership alone. Missing ownership evidence grants nobody access. Existing valid collaborators remain unless separately reviewed for removal.

Applied to the saved EWI evidence, this rule produces:

| Decision | Records |
| --- | ---: |
| Retain the current Intake assignee as a collaborator | 3 |
| Add no historical Intake collaborator | 43 |
| Total reviewed | 46 |

All three retained assignments belong to the same active Intake member. One also has a different former-owner observation; that observation creates no additional grant.

The other 43 records include 15 with former-owner observations and 28 without an identified former owner. The user did not verify those former owners for restoration.

The existing API decisions are `retain_verified_owner` for the three current assignments and `no_verified_owner` for the other 43. Each request includes its evidence reference and record fingerprint. Here, `no_verified_owner` means no verified former owner retained by this review. It does not assert that the record never had an Intake owner.

The private plan is `.exports/permissions-v2-handoff-review-20261004/approved-decisions-20261005.json`. It is Git-ignored, mode `0600`, and marked `applied=false`. It contains identifiers and concrete request fields, but no credentials, contact details, notes, or message content.

## Welcome workflow

The user authorized continuing the existing **Welcome Email for New Lead** organizational workflow. Keep its new-surrogate trigger, empty conditions, and current email template unchanged.

The current migration pauses this workflow during activation. After authorized activation, an eligible administrator must authorize and re-enable the unchanged configuration under V2.

The private configuration metadata and approval are in `.exports/permissions-v2-handoff-review-20261004/approved-workflow-20261005.json`. They came from the authenticated browser inspection on 2026-10-05. They require fresh verification before execution.

No workflow was paused, edited, authorized in production, or re-enabled. No email was sent or replayed. Before activation, recheck pending executions and campaigns. Record leads created during any pause for separate review; do not replay them automatically.

## Release conditions

1. Complete and validate the approved Under Review visibility and shared-pool behavior.
2. Release the local fixes through the normal authorized process.
3. Generate a fresh EWI preview and compare ownership, eligibility, phases, and fingerprints with the private plan.
4. Recheck workflow configuration, pending executions, campaigns, and permission differences.
5. Apply approved record reviews using authenticated, organization-scoped services.
6. Generate a new preview after those writes. Confirm retained access and obtain the current activation digest.
7. Activate only after explicit activation authorization, then authorize and re-enable the unchanged workflow.

Changed evidence requires reconciliation before applying a saved request. The business rule is approved; the saved snapshot is not permanently current.

## Validation and state

The saved evidence contains 46 unique records, no unresolved phases, and no existing human reviews. Exactly three current owners qualify as active Intake members. All 46 request shapes pass the current Pydantic schema. Workflow resolution fields pass the current permission-policy schema.

The working files contain policy documentation and private unapplied plans only. No application code, database, production permission, or workflow state changed. No local servers or test databases were started.
