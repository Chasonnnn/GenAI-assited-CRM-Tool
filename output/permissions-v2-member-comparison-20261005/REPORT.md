# Intake member V1–V2 comparison

Date: 2026-10-05, America/New_York.

The requested member's live effective permissions and a fresh organization preview were inspected through the authenticated administrator interface. Permission V1 remains active. No permission, ownership, collaborator, workflow, or activation change was applied.

## Record access

| Surface | Current V1 | Deployed V2 preview | Finding |
| --- | ---: | ---: | --- |
| Non-archived surrogate scope | 187 | 183 | Four specific losses; no gains. |
| Intended-parent effective access | 0 | 0 | Both permission sets lack `view_intended_parents`. |
| Full match access | 0 | 0 | Both permission sets lack `view_matches`; match actions are empty. |
| Non-archived donor scope | 0 | 0 | No change. |

The preview's surrogate counts are explicitly scope-only. The member has the required surrogate view and post-approval permissions. The live administrator access checker returned `Record visible` for all four listed surrogate losses. A sampled IP check returned a missing record-view permission denial.

Three losses are post-approval records currently owned by this member, without retained collaboration. Their current ownership matches the earlier isolated evidence ledger. All three current Intake-owner preservation cases from that rehearsal belong to this member.

The agreed policy retains this member as a collaborator while the shared pool owns those records. Migration must explicitly apply that policy to existing records. Future approval-handoff retention does not backfill them. No backfill or ownership transfer was performed in this investigation.

The fourth record is On-Hold, with Contacted → Lost → On-Hold history and Lost recorded as its pause origin. This matches the phase defect addressed by the locally committed fixes. The corrected phase is expected to preserve Intake access through its pre-approval operational history. That expectation is not a fresh production preview of the undeployed code.

The deployed preview also reports 25 lost IP scope pairs. Those are not lost effective access: the member lacks the IP view permission in both versions.

## Action permission keys

Added keys in the proposed V2 configuration:

- `approve_donors`
- `approve_surrogates`
- `create_donors`
- `create_surrogates`
- `edit_campaigns`
- `manage_automation`
- `manage_email_templates`
- `review_form_submissions`
- `send_email`
- `send_sms`
- `view_campaigns`
- `view_form_submissions`

Removed key: `manage_ai_settings`.

These are effective permission-key differences. They do not establish that every corresponding operation was previously unavailable through legacy role-based checks. Record scope and other operation-specific authorization still apply.

## Verification and limits

- Live membership is active, with the Intake Specialist role and no individual permission overrides.
- The fresh preview reports policy 1 → 2, `ready=false`, 48 unresolved handoffs, and one unresolved execution review.
- The deployed preview still uses older phase logic. The corrected clone review identified 46 historical handoffs.
- Four surrogate access checks returned visible; the sampled IP check returned denied.
- Captured administrator and record-browser warning/error logs were empty.
- No session signed in as the target member was used. Match denial follows the required module permissions, not an impersonated match-page test.
- No tests or local services were started for this read-only investigation.

Exact record numbers, links, and the member-specific comparison are in the private, Git-ignored report at `.exports/permissions-v2-member-comparison-20261005/report.md`.
