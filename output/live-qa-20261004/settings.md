# Settings and administration browser QA

Revision: `65bca746e`. Local disposable organization only. Live Chrome UI, shared administrator session, October 4, 2026. No application source changed.

## Confirmed findings

### S1 — P2: Duplicate queue creation fails without visible feedback

1. Open `/settings/queues` and Create Queue.
2. Enter existing name `QA Settings Queue Edited` and submit.
3. Dialog remains open with entered data, no error text or toast, and Create still enabled.

Console reports uncaught `ApiError: Queue 'QA Settings Queue Edited' already exists`; Next development issue badge appears. The mutation is rejected, but the user cannot tell why. Screenshot: [duplicate queue dialog](settings-evidence/queue-duplicate-no-error.jpg). Source: `apps/web/app/(app)/settings/queues/page.tsx:93` awaits the mutation without an error handler.

### S2 — P2: Existing queue description cannot be cleared

1. Edit `QA Settings Queue Edited`, whose description is `Local QA queue lifecycle`.
2. Clear Description (optional) and Save Changes.
3. Dialog closes; row still displays `Local QA queue lifecycle`.

Source: `apps/web/app/(app)/settings/queues/page.tsx:109` only includes description in the update payload when nonempty, so the API receives no clear instruction.

## Executed checks

| Area | Verified live behavior |
|---|---|
| Profile | General loaded profile, role, protected SSO email, and active sessions. Title change displayed dirty count; Discard reverted it. Save displayed success; reload preserved changed title. Original `QA Administrator` restored and saved. |
| Signature settings | Email Signature navigated with query parameter. Five templates, sidebar initials fallback, signature logo, color, company/contact fields, disclaimer, social links, and preview control rendered. No signature mutation was completed in this pass. |
| Pipeline table | Surrogates loaded 25 stages/10 locked with counts, labels, behavior and milestone labels. Egg and sperm donors loaded 14 stages each; intended parents loaded four locked stages. |
| Pipeline drawer | Anatomy Scanned showed label/slug/key/type/color/position/behavior/rules/milestone/funnel/references. Empty label showed inline error, error count, and disabled Save. `Invalid Slug!` normalized to `invalid_slug`; Discard restored values. |
| Pipeline save | Unused Anatomy Scanned (0 records) changed only to label `QA Anatomy Scanned` and color `#4F46E5`; Save produced v2. Reload preserved both. Restored `Anatomy Scanned` and `#006529`, saved v3. No transition rules changed. |
| Pipeline history | Version sheet showed v3 Current, v2, and v1 with timestamps and change descriptions. |
| Pipeline draft actions | Add Custom Stage inserted row and focused label. Renamed, moved up, selected Delivery Preparation milestone, and enabled funnel. Duplicate created Copy draft. Removal Cancel retained it; Confirm Removal removed draft. Discard restored original 25 stages and mappings/funnel. |
| Pipeline safeguards | Existing-stage removal displayed friendly `Ongoing Pregnancy Care` dependency and cancelled. Locked New Unread drawer explained platform dependency, disabled identity/rules, omitted duplicate/remove. |
| Pipeline mobile | Per-tab 390x844 emulation rendered list and stage page. Back returned to stages; Reorder exposed up/down controls. Moving Anatomy Scanned retained move-button focus and showed dirty Save/Discard. Discard restored order. Viewport override cleared. [Mobile stage screenshot](settings-evidence/pipeline-mobile-stage.jpg). |
| Queues | Blank/whitespace names disabled Create. Create, rename, reload persistence, deactivate, and reactivate passed. Empty member dialog and account labels rendered. Duplicate-name and clear-description failures are S1/S2. Fixture left inactive. |
| Team | Six members rendered; current-user and developer bulk selection disabled. No-match search showed `No matching people`; Case Manager filter returned only Test Case Manager with readable trigger. Invite dialog opened and cancelled without sending. Member detail showed role, permissions and empty overrides; role overview loaded permission modules and access preview. No role/override/security mutations. |
| Notification preferences | In-app and email settings loaded all controls. Task Reminders disabled, reload confirmed false, restored true. Browser push permission and security alert preference untouched. |
| Intelligent suggestions | Rules and readable template/stage/time labels rendered. Zero business days disabled Add Rule. Added local `QA Unsaved Rule` with 2 business days; immediate success appeared. Disabled it, edited name to `QA Settings Rule`, reloaded and confirmed disabled persisted. |
| Audit | Populated live activity log included settings changes. Next advanced page 1 to 2. Filter AI Events reset to empty AI Action Approved result and showed no audit entries. Export controls rendered; export execution not tested. |
| Compliance | Retention table, audit-log Always On protection, and no-hold empty state rendered. Hold scope labels opened; Surrogate scope enabled search, QA search returned fixture names, selecting QA Form Pending showed readable record. Missing reason kept Create Hold disabled. No hold/retention mutation. |
| Alerts | Existing synthetic appointment-503 alert rendered with counts/actions. Resolved filter showed no resolved alerts; Refresh completed. No alert was acknowledged/snoozed/resolved. |
| Security/sessions | Security rendered Duo Unavailable local-provider state. `/settings/sessions` routed to General active sessions, displaying current-device marker and other-session revoke controls. No revoke/logout/MFA changes. [Sessions screenshot](settings-evidence/sessions.jpg). |

## Console

- Initial settings load: no captured warnings or errors.
- Later: one `[WS] Handshake rejected - notifications will use polling fallback` warning; fallback expected in local harness.
- Duplicate queue submit: uncaught ApiError described in S1.
- Final check: no additional captured warnings/errors.

## Boundaries and gaps

- Sidebar logo upload used a synthetic local PNG and documented chooser flow, but the tool call hung for 1,983 seconds and was aborted. Recovery showed no uploaded logo. Upload/replace/invalid-type/size/remove remain unverified; no further chooser attempt was made.
- Automatic approval review rejected adding `Test Case Manager` to `QA Settings Queue Edited`, citing claim/access-permission changes without recipient-specific authorization. No member mutation occurred; this action was not retried or bypassed.
- Role mutation, access override, invite send, MFA, session revoke, retention purge/hold creation, alert lifecycle mutations, and provider connection/delivery were not executed.
- Signature preview/save and audit export were not completed in this pass. Other agents own reporting/dashboard, provider integrations, and broader role-denial QA.
- Browser interaction covered the listed states; it does not establish every possible state or race.

## Final local state

- Profile title and notification preference restored.
- Pipeline presentation and ordering restored; history retains v2/v3 QA versions.
- `QA Settings Queue Edited` remains inactive with zero members and original description.
- `QA Settings Rule` remains disabled (created for this QA).
- No production tab/state changed. No service started by this agent. Browser viewport override cleared.
