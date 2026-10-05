# Role and tenant browser QA

Revision `65bca746e`; 2026-10-04. Local disposable database and browser profile isolated from the other QA agents. Both organizations use permission policy version 1, the default for newly seeded organizations; a separate activated V2 comparison is documented in [roles-v2.md](roles-v2.md). Existing development login establishes real application sessions. Auth, CSRF, membership, role, and tenant checks remain active. Role changes use the local QA login picker. No external messages sent.

## Findings

| ID | Priority | Reproduction | Observed result | Evidence |
| --- | --- | --- | --- | --- |
| ROLE-01 | P2 | Sign in as case manager; Surrogates → New surrogate; enter `QA Case Manager Created` and synthetic email; submit; reopen resulting record. | Creation succeeds with POST 201 and success toast. Redirected detail and a fresh navigation both show `No access to this surrogate`; GET 403. The default creation produces a queue-owned New Unread record; legacy case-manager visibility is Approved onward. The resulting redirect has no accessible detail. Created ID `c9082d3d-6fd3-438f-9f5f-1e3e21f0cf3a`. | [Screenshot](roles-case-manager-created-denied.jpg) |
| ROLE-02 | P2 | Sign in as operations; open Dashboard and Appointments. | Dashboard cards offer Retry for permission-denied surrogate/task/attention requests. Appointments simultaneously shows `Unable to load booking link` with Retry and `Permission required`. The API correctly denies access, but the UI presents permanent authorization failures as recoverable load failures. | [Dashboard](roles-operations-dashboard.jpg), [Appointments](roles-operations-appointments.jpg) |
| ROLE-03 | P2 | Sign in as operations; Tasks → Add task; enter a title; Create task. | Add task opens and permits submission even though task listing is denied. Submit returns403 and dialog displays raw `Missing permission: view_tasks`. No task creation succeeded. | [Screenshot](roles-operations-task-create-denied.jpg) |
| ROLE-04 | P3 | Sign in as case manager, intake specialist, or operations; navigate directly to `/settings/team`. | Page shows `0 members • 0 actionable invitations`, Members(0), and raw `Missing permission: manage_team` with Try again. Member/invitation API requests correctly return403. Counts look like valid empty data despite denied access. | [Screenshot](roles-team-permission-state.jpg) |

## Completed route checks

| Role | Route or action | Result |
| --- | --- | --- |
| Case manager | Dashboard | Loads |
| Case manager | Surrogates list | Loads allowed records; New surrogate available |
| Case manager | Create then reopen surrogate | ROLE-01 |
| Case manager | Reports | Loads counts, charts, and Export PDF control |
| Case manager | Appointments | Loads own empty status tabs and booking-link control |
| Case manager | Form Builder | `No access to Form Builder` |
| Case manager | Team | API denied; ROLE-04 |
| Intake specialist | Dashboard | Loads |
| Intake specialist | Surrogates list | Loads intake records and New surrogate control |
| Intake specialist | Donors list | Loads seeded donors and New donor control |
| Intake specialist | Appointments | Loads own empty status tabs and booking-link control |
| Intake specialist | Reports | `Permission required`; asks for View Reports permission |
| Intake specialist | Form Builder | `No access to Form Builder` |
| Intake specialist | Team | API denied; ROLE-04 |
| Operations | Dashboard | ROLE-02 |
| Operations | Reports | Permission-required page; no report data |
| Operations | Surrogates list | Permission-required page; no records |
| Operations | Donors list | Permission-required page; no records |
| Operations | Form Builder | `No access to Form Builder` |
| Operations | Data Management | Permission-required page, developers only |
| Operations | Appointments | API denied; ROLE-02 |
| Operations | Tasks calendar and list | Permission-required state |
| Operations | Task creation | API denied; ROLE-03 |
| Operations | Team | API denied; ROLE-04 |

## Tenant isolation

A separate organization and admin were created in the disposable database. Signed in as the foreign admin, direct browser navigation to known primary-organization identifiers produced:

| Resource | Primary organization identifier | Result |
| --- | --- | --- |
| Surrogate | `364bf4bf-c2e9-4adf-8efe-f04e19383184` | Surrogate not found; API 404 |
| Donor | `dcf68389-2e94-47c4-9f90-1de0d12e7663` | Donor not found; API 404 |
| Intended parent | `04096775-f16f-4bd8-aeaf-422cc0d6d9cc` | Intended parent not found; API 404 |
| Form | `0faa0607-0f97-4660-b7b5-f6b5b84f0bcb` | Form not found; API 404 |
| Own foreign surrogate | `08aaa7e5-e317-43d1-bf8f-fb2cf9e6b42a` | Loads own candidate overview and contact data |

[Foreign tenant surrogate denial screenshot](roles-foreign-surrogate-denied.jpg). No primary organization data appeared in the four denied detail pages. This pass does not establish exhaustive isolation across every endpoint or export.

## Archived donor nested access

Donor `cca9d2b9-5656-43ec-913c-573f66e822f6` (D10004, QA Records Sperm) was archived through the administrator UI after coordination with the records agent.

- Administrator can reopen the archived donor; Notes shows the existing note, Tasks shows the completed task with a disabled checkbox, Files shows its empty state.
- Intake specialist can reopen the same archived donor and read Notes, Tasks, Applications, and History without erroneous403 responses.
- Archived overview edit controls are disabled, the mutation action menu is absent for intake, and no add/edit controls appear for archived notes/tasks.
- The donor remains archived in the disposable database.

## Match cancellation with two actors

The records agent requested cancellation of match `459b7ff5-a0cd-4c6a-97b0-8580ec432f11` (M10021) as Test Admin. A second primary-organization admin, QA Review Admin (`ae8f1ffa-03c6-4e0d-9efb-2499c7cfb4df`), signed in through the local picker.

- Match detail shows Cancellation Pending and disables Withdraw Cancellation for the non-requester.
- Tasks → Pending Approvals displays the request, requester, participant names, and reason.
- Approve removes the request from the pending list.
- Reopened match shows Cancelled; surrogate and intended parent both show Ready to Match.
- The generated stage note attributes the transition to QA Review Admin.
- [Approved cancellation screenshot](roles-match-cancellation-approved.jpg).

## Diagnostics and limits

Browser console checks at case-manager denial, foreign-tenant positive control, match approval, and operations task rejection returned no captured warning/error messages. API 403/404 responses are recorded separately through sanitized route-template/status logs. Unexpected permission errors in this report are visible UI behavior even when the browser console remains empty.

These checks use synthetic users and data with no real providers. OAuth login, production role customizations, and external delivery are outside this pass. No app source was changed.
