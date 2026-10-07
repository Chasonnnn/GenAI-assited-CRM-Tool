# Case Managers retain access to surrogates they created

Date: 2026-10-04

## Decision

Within their organization, Case Managers can access Approved-and-later surrogates and surrogates whose `created_by_user_id` matches their user ID. The creator route applies in permission V1 and V2, including before approval and after reassignment.

## Reason

Case Managers could create a queue-owned New Unread surrogate and immediately receive 403 when the frontend opened it. The user selected continued creator access, rather than removing creation or redirecting away from the created record.

## Boundaries

- Creation and assignment are separate relationships. Assignment alone does not grant a Case Manager pre-approval access under the default scope.
- The creator route is separate from V2 role-scope rules and remains available when the role is configured as assigned-only or none. Removing record-view permission, ending active membership, or changing the member's role still removes the corresponding authority.
- Existing tenant, archive, action-permission and V1 post-approval permission checks remain in place.
- Personal workflows and campaigns still require assignment or explicit collaboration. Creator visibility alone does not expand their reach.
- Donor and intended-parent visibility are unchanged. Historical null creator values are not inferred or backfilled.
- List, detail, search, counts, access explanations and migration comparisons must use the same creator route. A creator change invalidates an earlier migration preview digest.

## Delivery

The existing creator column supplies the rule; no schema migration is required. Deploying this change and activating an organization's V2 policy are separate actions. V2 activation still requires the full, fresh organization-specific review.
