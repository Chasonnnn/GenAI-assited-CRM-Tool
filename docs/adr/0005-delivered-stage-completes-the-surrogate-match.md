---
status: accepted
---

# The Delivered stage completes the surrogate's match

Matches have no manual Complete action. When a surrogate enters the stage whose system role is `delivered`, her accepted match becomes `completed` in the same transaction as the stage move: `closed_at` is the stage change's record time, `closed_by_user_id` is the acting user (the approver for an approved request, null for workflow and other system actors), `outcome` is the Delivered stage label, `closure_reason` stays empty, open attempts close, and the engine writes `match_completed` history. A cancellation-pending match is not completed. Donor matches are not completed by any stage.

Undoing that Delivered stage change through the grace-period undo restores the match to `accepted` and clears its closure fields, when the match is still completed and neither the surrogate nor the pair has another committed or open match. The restore writes `match_completion_undone` history. Attempts closed at completion stay cancelled. Any other move out of Delivered leaves the match completed, and moving back to Matched without that undo is refused.

`surrogate_status_service.apply_status_change` is the one stage-change chokepoint for manual, backdated, bulk, approved, undo, v2 workflow, and v2 AI changes. The v1 workflow and v1 AI stage actions write the stage directly, so they call the same engine function. Both run before the surrogate row is written, so the lock order matches the engine: organization configuration (permission v2), the surrogate's match rows, then the surrogate row. The engine functions live in `match_lifecycle`, keeping ADR 0004's single owner of match status changes.

The completion is not behind `MATCH_CASE_EXPANSION_ENABLED`. Match status metadata lists `accepted -> completed` and `completed -> accepted` as `system_transitions`, which no user action offers.

## Considered Options

- Keep a manual Complete action: rejected. Completion depended on a separate click that could come before delivery or never.
- Link the undo to the completion with a new column: deferred. The undo finds the match completed at or after the Delivered entry's record time, which is exact while delivery is the only way a surrogate match completes. A column is needed if another completion path is added.
- Stage-deletion remaps into Delivered: not covered. They move records without stage history or workflows, and do not complete matches.
