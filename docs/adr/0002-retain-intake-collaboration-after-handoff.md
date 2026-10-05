---
status: accepted
---

# Retain Intake collaboration after approval handoff

Under Permission V2, approved surrogates belong to the shared Surrogate Pool. Case Managers see surrogates from Under Review onward, plus records they created. Visibility and approval use separate boundaries.

Approval retains the current active Intake owner as an Intake collaborator for follow-up work. Access lasts until explicitly removed while the person remains eligible staff. Earlier ownership alone grants no access. Collaboration permits viewing and normal information updates; stage changes require separate permissions. Donor handoff behavior remains unchanged.

Implemented locally behind reviewed organization activation. See [verification](../permission-upgrade-verification.md).

## Existing records at migration

The user approved the following migration rule on 2026-10-05. Preserve the current explicit active Intake assignee as a collaborator. Do not restore access solely because someone owned the record earlier. Missing ownership evidence grants nobody access. Keep existing valid collaborators unless separately reviewed for removal.

This migration rule does not change future handoff retention. Retain the active Intake owner when a future approval handoff occurs.

Reviewed V1-to-V2 activation now includes an explicit pool-transfer plan in the preview digest. Activation moves effective postapproval surrogates and retains current eligible Intake owners atomically. Changed ownership, membership eligibility, or pool state invalidates the preview.

Future approvals, imports, restores, workflow writes, and pipeline changes preserve shared ownership. Paused and terminal records use their canonical effective phase. A record that returns to preapproval can be assigned normally; existing collaboration remains.

Release does not activate organizations or bulk-convert existing V2 data. Existing V2 records normalize through the relevant mutation paths. A separate reviewed operation is required for any bulk conversion outside V1-to-V2 activation.

The approved record decisions remain unapplied. Revalidate current ownership, membership eligibility, and record fingerprints against a fresh preview after release. See the [migration decisions](../../output/permissions-v2-handoff-review-20261004/DECISIONS-20261005.md).
