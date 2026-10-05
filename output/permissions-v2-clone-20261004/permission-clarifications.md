# Permission clarification after the clone rehearsal

Date: 2026-10-04, America/New_York. Investigation used local source at `9b6c530a5` and read-only production permission pages.

## Correction to the rehearsal interpretation

The preview counts record scope separately from required permissions. Its result explicitly sets `scope_only: true`.

For V1 intended parents, the scope calculation includes every organization record. It does not check `view_intended_parents`.

The reported 100 Intake–IP pairs therefore do not establish effective access. The earlier recommendation to preserve presumed organization-wide Intake access is withdrawn.

The saved clone output remains unchanged. [Scope calculation](../../apps/api/app/services/record_scope_service.py:1119).

## Case Manager boundary

Current V1 source allows Approved and later, plus surrogates created by that Case Manager. V2 defaults also use post-approval scope, with creator access separately retained.

Under Review precedes Approved and is not included by the default phase boundary. A Case Manager can still see an Under Review record through creator access.

The user's proposed review boundary is Under Review and later. This visibility change can keep the approval and pool handoff boundary at Approved.

No boundary change was implemented during this investigation. The previous clone counts do not describe the proposed Under Review boundary.

Sources: [V1 visibility](../../apps/api/app/core/surrogate_access.py:103), [V2 defaults](../../apps/api/app/services/record_scope_service.py:52), [stage order](../../apps/api/app/core/stage_definitions.py:370).

## Intake, intended parents, and matches

Intake defaults include neither `view_intended_parents` nor `view_matches`. Sidebar entries require those module permissions.

The requested Intake member's live page showed the Intake Specialist role, neither permission, and no individual overrides.

The live access checker denied a selected intended-parent record because the required view permission was missing. No permission was changed.

Matches have no owner or assignee field. Match access requires permission to view matches and independent access to both participants.

Under V1, an explicit IP view grant gives organization-wide IP reads. Under V2, Intake IP scope defaults to records assigned directly to that member.

Surrogate collaboration does not grant access to the linked IP. V2 currently supports collaborator grants for surrogates and donors, not IPs.

An accessible surrogate's activity feed can show generic match events without match-module access. This does not authorize opening the match or IP profile.

No session signed in as the requested Intake member was tested. The reported ability to open specific match details remains unverified.

A known match URL or record number is needed to investigate that report against the exact production surface.

Sources: [default permissions](../../apps/api/app/core/permissions.py:607), [sidebar](../../apps/web/components/app-sidebar.tsx:79), [match authorization](../../apps/api/app/services/match_access.py:67), [IP scope](../../apps/api/app/services/record_scope_service.py:52), [collaboration boundary](../../apps/api/app/services/record_scope_service.py:120), [activity endpoint](../../apps/api/app/routers/surrogates_read.py:687).

## Historical handoffs

Historical reviews decide whether a former Intake owner retains record collaboration. They do not change current ownership.

V2 approval retains a verified active Intake owner as a collaborator and normally moves ownership to the surrogate pool. A claim then assigns ownership to the claiming user.

The pool page lists queue-owned records at Approved. It does not contain every post-approval surrogate.

Current ownership and the person who recorded approval do not prove who owned the record at the historical handoff.

An explicit decision to remove historical Intake access would be a different policy from finding no verified historical owner.

Sources: [approval handoff](../../apps/api/app/services/approval_handoff_service.py:44), [claim](../../apps/api/app/services/queue_service.py:284), [pool listing](../../apps/api/app/services/surrogate_service.py:1687), [historical resolution](../../apps/api/app/services/record_scope_service.py:990).

## Organizational workflows

The workflow flagged by the clone already belongs to the organization. Its missing item is V2 authorization for its configured actions.

V2 records authority against the workflow configuration. Organizational execution then survives the original author's departure.

The current migration requires pausing the legacy workflow and re-enabling it under V2. It has no authorize-and-continue migration option.

The clone had no pending unreviewed executions or running campaigns. This result does not establish current production execution state.

The product currently supports both organizational and personal workflows. Creation defaults to organizational scope. Removing personal workflows would be a separate product change.

Sources: [workflow authorization](../../apps/api/app/services/workflow_execution_authority.py:169), [migration behavior](../../apps/api/app/services/workflow_execution_authority.py:566), [creation schema](../../apps/api/app/schemas/workflow.py:495).

## Validation and state

- Read-only production member and access-check pages were inspected.
- The selected IP check returned a missing view-permission denial.
- The inspected browser session returned no warning or error logs.
- No application code, production permissions, workflow state, or policy version changed.
- No new runtime tests were run for this documentation correction.
