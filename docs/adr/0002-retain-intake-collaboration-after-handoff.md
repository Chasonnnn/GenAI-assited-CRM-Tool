---
status: accepted
---

# Retain Intake collaboration after approval handoff

Approval transfers ownership to a Case Manager or pool while retaining the Intake owner at handoff as an Intake collaborator, because that person may continue follow-up and information updates requested by the Case Manager. Retained access lasts until explicitly removed by a Case Manager or Admin while the person remains eligible staff; other collaborators are added explicitly rather than granting access to everyone who ever owned the record. Collaboration permits viewing and normal information updates, with stage changes and reassignment controlled separately.

Implemented locally behind reviewed organization activation. See [verification](../permission-upgrade-verification.md).

## Existing records at migration

The user approved the following migration rule on 2026-10-05. Preserve the current explicit active Intake assignee as a collaborator. Do not restore access solely because someone owned the record earlier. Missing ownership evidence grants nobody access. Keep existing valid collaborators unless separately reviewed for removal.

This migration rule does not change future handoff retention. Retain the active Intake owner when a future approval handoff occurs.

The shared-pool ownership target is approved but remains an implementation gate. The existing handoff hook does not backfill old records or implement permanent pool ownership.

The approved record decisions remain unapplied. Revalidate current ownership, membership eligibility, and record fingerprints against a fresh preview after release. See the [migration decisions](../../output/permissions-v2-handoff-review-20261004/DECISIONS-20261005.md).
