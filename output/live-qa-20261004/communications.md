# Communications browser QA

Revision: `65bca746e`. Date: 2026-10-04. Local web: `http://localhost:3000`; local API: `http://localhost:8000`. Disposable database: `crm_qa_20261004_b7f21d`.

Browser: Chrome through `mcp__cua_repl`; IAB was unavailable to this subagent. Shared admin profile stayed signed in. Developer ticket tests used a separate browser profile and the harness's normal developer login link. No production tabs, general worker, provider credentials, or external sends were used.

## Confirmed finding

### COMM-01: SMS record-link errors escape as uncaught runtime errors

Priority: P2. Route: `/tickets?view=messages`.

1. Sign in as the synthetic developer.
2. Open an unlinked SMS conversation.
3. Enter `not-a-uuid` into **Entity ID** and click **Link**.
4. The UI retains the form without an application error or toast. The console records an uncaught `ApiError`; the development issue panel opens a **Runtime ApiError** overlay.

Console at `2026-10-04T20:12:06.890Z`:

```text
ApiError: entity_id: Input should be a valid UUID, invalid character: expected an optional prefix of `urn:uuid:` followed by [0-9a-fA-F-], found `n` at 1
    at request (.../_next/static/chunks/_076cbul._.js:2026:15)
```

The overlay points to `lib/api.ts:151`. A second attempt using the seeded foreign-organization surrogate ID correctly failed authorization but produced the same missing UI feedback and uncaught rejection:

```text
2026-10-04T20:13:11.002Z
ApiError: Link target was not found in this organization
```

Source: `apps/web/app/(app)/messages/page.client.tsx:143` returns `linkConversation.mutateAsync(...)` directly from its click handler without handling rejection. Valid linking works. No cross-organization record was linked.

Screenshot: [sms-link-error.jpg](sms-link-error.jpg), reproduced again at `20:20:18.377Z` with a second unlinked synthetic conversation. Console evidence: [communications-console.json](communications-console.json).

## Executed task checks

| Check | Result |
| --- | --- |
| Empty Add Task dialog | Create task disabled until nonblank title. |
| Create linked task | Created `QA Communications Task 1004`, Follow Up, description, linked surrogate S10001. |
| Record picker | Search returned synthetic surrogate, intended parent, and donor with display labels. Selected surrogate persisted. |
| Edit task | Renamed to `QA Communications Task Updated`, selected Oct 5 in calendar, set 3:30 PM using native keyboard input; saved and reloaded through task dialog. |
| Complete/reopen | Open task disappeared on completion, appeared under Completed, reopened under Open; status filter and reset behaved correctly. |
| Search | Narrowed to synthetic task; clear/reset restored rows. |
| Calendar | Month, Week, Day, Next period, Today, task selection, exact 3:30 PM label. |
| Recurrence validation | Daily recurrence rejected missing due date, missing end date, and end before due date with visible errors. |
| Recurrence creation | Created three `QA Recurrence Validation` tasks dated Nov 5, 6, 7. List showed Later (3). |
| Linked-record filter | No linked record retained recurrence tasks. |
| Due filter | Combining recurrence search + unlinked + Overdue produced No matching tasks; Clear filters worked. |
| Delete dialog | Confirmation and cancel passed; task retained. Final deletion was blocked by automatic approval review. |
| Console | No application warning/error during task CRUD/calendar/recurrence checks. |

Native date/time `.fill()` in the Chrome automation transport changed the DOM value without committing React state. Calendar selection and trusted ArrowUp input committed correctly. Initial absent dates/times were treated as an automation-input limitation, not a product defect.

## Executed notification checks

| Check | Result |
| --- | --- |
| Action/Updates tabs | Counts, empty Action state, update unread count displayed. |
| Stage request | Reject opened inline confirmation; Cancel retained request; Approve succeeded and removed action. |
| Surrogate claim | Claim succeeded and removed action. |
| Workflow approval | Approve succeeded; Deny confirmation Cancel then final Deny succeeded for separate fixture. |
| Task actions | Assigned and overdue tasks completed from notification panel. |
| Exact task deep link | Clicking QA Calendar Follow Up opened `/tasks?filter=my_tasks&focus=tasks&task=fecbaecd-1cb5-40bf-a8f0-ab267bc09e28` and its correct Edit Task dialog. |
| Updates mark-read | Panel Mark all read cleared update unread count. |
| Notification history | View all opened `/notifications`; Applications filter showed No matching notifications; Clear filters restored list; global Mark all read removed unread badge. |
| Appointment approval | Approved QA Pending Client; action removed. |
| Appointment decline | Cancel confirmation retained booking; final Decline succeeded and removed action. |
| Empty action queue | After outstanding synthetic actions, panel displayed Nothing needs you. Screenshot captured in CUA transcript. |
| Error recovery | During the planned API restart, approval showed Couldn't approve appointment, panel showed Couldn't load notifications and Retry. Retry after restart succeeded, then approval succeeded. |

The planned restart was confirmed by the environment owner at `20:04:10–20:04:15Z`; its `[WS] Handshake rejected - notifications will use polling fallback` warning and transient request failures are harness-induced, not classified as defects. Desktop alert permission was not requested.

## Executed ticket checks

| Check | Result |
| --- | --- |
| Admin access | `/tickets` displayed Permission required / Tickets are available only to developers. |
| Legacy messages route | `/messages` redirected to `/tickets?view=messages`; admin access stayed denied. |
| Developer empty state | No tickets before synthetic fixture seeding. |
| New ticket draft | Opened To/Subject/Message fields, filled synthetic draft, cancelled; no ticket created or communication sent. |
| Ticket list | Seeded Open/Normal and Resolved/High rows displayed human labels. |
| Filters | Open status, ticket-code search, High priority and no-match search, Clear filters. |
| Ticket detail | Synthetic inbound body, sender, and seeded note displayed. Fixture has no provider timestamp, so Unknown time is expected. |
| Status/priority save | Pending/Urgent persisted after reload. |
| Internal note | Added `QA internal browser note 1004 — local synthetic record.`; appeared immediately and after reload. |
| Record-link validation | Malformed UUID produced a visible validation error. |
| Tenant boundary | Foreign-organization surrogate UUID rejected with Surrogate not found. |
| Link/unlink | Valid surrogate ID saved and persisted; clearing ID successfully unlinked. |
| Reply draft | Typed synthetic reply without sending. Reload cleared unsaved draft. |
| Close/reopen | Closed status saved; Open status saved; list reflected Open/Urgent. |

Synthetic ticket IDs: `52563c21-a042-42e3-8e3e-f66fdb09957e`, `9643fede-d2bc-41cf-8479-5c9c5f56d6e0`. Fixture script: `/private/tmp/crm-live-qa-20261004/communications-fixtures.py`; it asserts the exact disposable database, blocks outbound HTTP, and only inserts local model fixtures.

## Executed SMS checks

| Check | Result |
| --- | --- |
| Channel tab | SMS/MMS selected and URL became `/tickets?view=messages`. |
| Conversation display | Masked phone 0189, operational label, unlinked and unread badges, synthetic inbound message, unknown consent states, Read-only badge. |
| Invalid/foreign link | Backend rejected both; UI error handling failed as COMM-01. |
| Valid link | Linked local surrogate; unlinked controls and badge disappeared. |
| Mark read | Unread count and Mark as read control disappeared. |
| Read filter | Unread only excluded the read conversation. |
| Link filter | Unlinked only excluded the linked conversation. |
| Purpose filter | Promotional showed empty state; Operational restored the two operational conversations. |
| Entity type menu | Surrogate, Intake lead, Meta lead labels rendered. Blank Entity ID disables Link. |

Conversation ID: `d4c50007-9ad8-4682-8f57-8673b10a7c46`. Second conversation for error screenshot: `aa9ba008-8432-4308-b32b-66a2af1e1c0f`. Provider route remains disabled; no message was submitted or delivered.

## Search and public routes

| Check | Result |
| --- | --- |
| Global search dialog | Minimum-two-character empty prompt, QA query results, narrowed QA Donor query; selected result opened correct donor D10001. |
| Full search page | Empty and one-character query did not fetch results; clear control rendered. |
| Search persistence | Query written to URL, survived reload and Back navigation. |
| Intended-parent result | QA Intended found I10001; link opened its detail. |
| Surrogate result | QA Surrogate found S10001; link opened its detail. |
| Note result | QA Surrogate also found QA Records Surrogate note; link opened the correct surrogate, with the note visible in activity. |
| No-match query | ZzzNoMatchingQaRecord showed No results found. |
| Keyboard clear | Escape cleared input and q from URL. |
| Dialog keyboard navigation | ArrowDown + Enter on the unique QA Intended result opened I10001. |
| Exact email search | qa-intended-parent@example.com returned I10001. |
| Normalized phone search | (212) 555-0104 returned I10001. |
| Privacy/Terms | Public pages rendered; Privacy→Terms link and Terms Privacy link target correct; no legal agreement accepted. |
| Malformed invitation | /invite/not-a-uuid displayed Invitation not found / invalid or expired, without raw API validation. |
| Invalid text preference | /public/messaging-consent/qa-invalid-token displayed This link is unavailable / invalid or expired. |
| Invalid unsubscribe token | Confirmation page displayed; Unsubscribe POST returned neutral success page and Return Home worked. Backend intentionally uses HTTP 200 for invalid tokens; no subscription record affected. |
| Unknown public route | /__qa_unknown_page__ displayed Page not found; Go home returned to landing. |
| Invalid developer ticket | /tickets/not-a-uuid displayed Ticket not found; Back to Tickets returned populated list. |

## Mobile browser checks

Chrome isolated developer profile at 390×844; viewport reset afterwards. Shared admin profile viewport remained unchanged.

- SMS inbox filters, conversation cards, and detail stack fit the viewport. DOM page width and scroll width both 390. [sms-mobile.jpg](sms-mobile.jpg).
- Ticket list, detail fields, notes/reply sections, and New ticket dialog fit. Dialog fields, close, Send, Cancel all visible; Cancel returned to list. [ticket-mobile.jpg](ticket-mobile.jpg). No send executed.
- Public `/book/test-admin`: selected multi-format appointment, Phone Call format, Oct 14, 10:00 AM, Enter contact details. Calendar and contact form fit with no horizontal overflow. Blank Request Appointment showed Name/Email/Phone required errors without creating a booking. Change returned to calendar with selected slot retained. [Calendar](public-booking-mobile-calendar.jpg), [required validation](public-booking-mobile-details.jpg).
- Public `/intake/qa-comprehensive-intake-20261004`: identity inputs, birth-date year/calendar, Alpha conditional Long Text reveal and Beta hide, multi-select/radio/checkbox, height 5 ft 6 in, repeating Add Row/Remove, disabled Remove at one row, stacked table/upload fields, and saved-progress restoration after reload passed. Form remained unsubmitted with attestation unchecked and Submit Application disabled. [Mobile intake](public-intake-mobile.jpg).
- Appointment-type duration was changed concurrently by root after this selection; screenshot reflects the pre-change 30-minute type. No booking was submitted.

## Console evidence

[communications-console.json](communications-console.json) contains captured warnings/errors from both QA tabs. Application errors are the three SMS link rejections described in COMM-01. Shared-admin console contains only the restart-related WebSocket warning. No new application error appeared during global search, public routes, or mobile ticket/booking/intake checks.

## Limits and blocked checks

- Automatic approval review rejected final **Delete task** because the dialog described irreversible deletion and required fresh confirmation. The task remains in the disposable database; no workaround was used.
- Automatic approval review rejected **Send** in the empty New ticket dialog because the QA scope excludes sends. No Send or Send reply action executed. Local draft fields, cancel paths, and seeded inbound tickets provided the remaining coverage.
- Console warnings from `chrome-extension://cndibmoanboadcifjkjbdpjgfedanolh/...` (`AssignmentCache`, no LMS adapter) are browser-extension output, not application output.
- Ticket/SMS provider delivery, reconciliation/delivery-history media fixtures, attachment uploads, global attachment search, native desktop notification permission, and permanent deletion are not verified.
- No production code changes or commits made by this agent.

## Cleanup

No services were started by this agent. Temporary fixture scripts are under `/private/tmp/crm-live-qa-20261004/` for root cleanup with the disposable environment. Both agent-created browser tabs were closed. Temporary viewport overrides were reset.
