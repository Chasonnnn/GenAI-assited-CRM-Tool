# Local QA — 2026-10-04

Revision: `65bca746e7e90b0da768e31dc06691c589eb07fb` on `main`, fast-forwarded to the cached `origin/main` with user approval. Production source remained unchanged during this audit.

Live browser checks used a disposable migrated PostgreSQL database, synthetic people and records, real application session/CSRF/role checks, and a guarded synthetic Google provider. Six parallel QA agents covered separate product areas. No production data or external delivery was used.

[UI/UX review and six current-versus-proposed mockups](../ui-ux-20261004/README.md)

Follow-up: [approved UI proposals 1–3 implemented and verified](../ui-ux-20261004/implementation.md), including F2 mapped submission identities and SCHED-01 availability feedback. [Case Manager creator access](../permissions-creator-20261004/README.md) resolves ROLE-01 under V1 and V2. The audit below preserves the original findings; the other 14 product findings and backend test-isolation failure remain unresolved.

## Findings

17 product findings and one test-isolation failure were confirmed. No fixes were applied.

| Priority | ID | Confirmed behavior | Evidence |
| --- | --- | --- | --- |
| P1 | ROLE-01 | Case Manager creates a surrogate successfully, then receives 403/No access on its detail page under both permission policies. | [Roles](roles.md), [V2 comparison](roles-v2.md) |
| P2 | F1 | Partially answered fixed tables cause draft save to fail. Autosave recovers after every required cell is complete. | [Forms](forms.md) |
| P2 | F2 | The standalone submission queue shows blank names/emails/phones for mapped identity fields that render correctly in the builder queue. | [Forms](forms.md) |
| P2 | SCHED-LIFE-01 | Marking No-show succeeds, but the appointment disappears from every list-status tab and list search. | [Scheduling lifecycle](scheduling-lifecycle.md) |
| P2 | SCHED-01 | Invalid weekly availability is rejected by the API without visible error feedback. | [Scheduling](scheduling.md) |
| P2 | COMM-01 | Invalid or foreign-organization SMS record links produce uncaught errors without in-app feedback. Backend access denial remains intact. | [Communications](communications.md) |
| P2 | R1 | Donor Education accepts and stores free text, then detail surfaces display Unknown. | [Records](records.md) |
| P2 | R3 | Approved form table answers display and edit as [object Object] in the profile card. The application view renders them correctly. | [Records](records.md) |
| P2 | REPORT-01 | Today/Week/Month summary counts exclude the final calendar day; Today becomes an empty interval. | [Reports](reports-dashboard.md) |
| P2 | REPORT-02 | All Time uses a 30-day fallback for several analytics, mixing recent cohorts with total/current metrics. | [Reports](reports-dashboard.md) |
| P2 | S1 | Duplicate queue creation leaves the dialog open without an error and logs an uncaught rejection. | [Settings](settings.md) |
| P2 | S2 | Clearing an existing queue description does not persist. | [Settings](settings.md) |
| P2 | ROLE-02 | Operations dashboard under policy V1 and appointments under both policies present permission denials as retriable loading failures. | [Roles](roles.md), [V2](roles-v2.md) |
| P2 | ROLE-03 | Operations can fill and submit Add Task, then receives a raw permission error: view_tasks under V1 or create_tasks under V2. | [Roles](roles.md), [V2](roles-v2.md) |
| P3 | ROLE-04 | Restricted Team pages show misleading zero counts alongside raw permission errors. | [Roles](roles.md) |
| P3 | R2 | Saving surrogate contact edits logs a Base UI uncontrolled-field error; the edit persists. | [Records](records.md) |
| P3 | AUT-01 | Paused execution rows exist but the status selector has no Paused option. | [Automation](automation.md) |
| P2 | Test isolation | A committed concurrency fixture leaves a calendar projection, causing the next preparation test to fail. | [Reproduction](test-analysis.md) |

P1 means a core workflow is blocked. P2 means incorrect behavior, missing feedback, or a significant coverage gate. P3 means a limited usability or console defect. These are QA priorities, not security severity ratings.

## Executed coverage

| Area | Browser coverage | Ledger |
| --- | --- | --- |
| Forms | Builder, field library, required mappings, all field types, conditions, table limits, publish, hosted and embedded submissions, routing/review, mobile | [Forms](forms.md) |
| Scheduling | Availability/types, public booking, approval, manual and normal reschedule, self-service token rotation/cancellation, Google failure/retry, both conflict choices, recurring/all-day/point events, completed/no-show/expired, pending conference recovery | [Core](scheduling.md), [Lifecycle](scheduling-lifecycle.md) |
| Records | Surrogate/donor/IP/match creation and edits, medical current/past/future/correction/archive/restore, notes/tasks, interview versions, match cancellation with two actors | [Records](records.md) |
| Lists and bulk | Sorting, pagination, combined filters, selection, bulk assignment and stage changes, validation/cancel paths | [Import and bulk](import-and-bulk.md) |
| Automation | Template editor/preview/drafts, workflow configuration and dry runs, campaign drafts/audiences, executions, AI-disabled states | [Automation](automation.md) |
| Communications | Tasks/recurrence, notification actions/deep links, ticket status/notes/linking, SMS filters/linking, global search, public invalid routes | [Communications](communications.md) |
| Administration | Profile, pipeline editing/history, queues, team/preferences, audit/compliance/alerts and integration screens | [Settings](settings.md), [Integrations](integrations-security.md) |
| Analytics | Dashboard trends/filters/navigation, report dates/campaigns/donor modes/performance sorting and PDF request | [Reports](reports-dashboard.md) |
| Access | Admin/developer/intake/case-manager/operations, both permission policies, archived donor nested access, cross-organization and same-organization ownership denials with positive controls | [Roles](roles.md), [V2](roles-v2.md) |
| Mobile | 390px forms, booking, tickets/SMS, pipeline editor, dashboard, reports and navigation | [Communications](communications.md), [Mobile supplement](supplementarymobile.md) |

## Automated checks

- Frontend: route/type checks, test types, ESLint, and 385 test files/3,038 tests passed.
- Backend: 5,601 passed, 1 failed, 503 subtests passed. The failure passes alone and reproduces after the leaking concurrency fixture.
- No source fixes were applied. The full backend gate is not green.

[Validation detail](validation.md) · [Environment](environment.md) · [API diagnostics](diagnostics.md)

## Console and runtime

- Uncaught browser errors reproduced for SMS record-link failures and duplicate queue creation. Surrogate Edit logs a Base UI uncontrolled-field error while saving successfully.
- Notification WebSocket warnings around the planned API restart recovered through polling. A Messaging settings crash was traced to an incomplete synthetic route fixture; adding the standard missing route restored the page. Neither was classified as a product regression.
- Sanitized API logging records route templates and status codes without request bodies or tokens. The final diagnostic ledger states its capture window and distinguishes expected denied/invalid requests from visible product failures.

## Limits

- Real Google/Zoom/OAuth, email/SMS delivery, provider reconciliation, AI generation, and production deployment were not verified. Google lifecycle simulation is not live provider proof.
- Native file-picker calls stalled while the Mac was locked. Browser uploads, CSV import completion, attachment search, and logo upload remain unverified. Native date inputs required trusted keyboard interaction; plain fill did not reliably commit React state.
- PDF export returned HTTP 200, but its downloaded bytes/rendering were not verified. Add to Calendar download capture also timed out. Form SVG/PNG QR files were verified by filename and nonzero size, without decoding scannability.
- Embedded submission passed using an enabled lead-capture form and an allowed localhost parent. Real third-party website integration was not verified.
- Automatic approval review blocked final test-email/ticket sends, Meta test events/Twilio connection tests, permanent task deletion, and queue membership changes. Those final actions were not retried or bypassed.
- Feature combinations and all permission permutations were not exhaustively enumerated. The [source-derived plan](coverage-plan.md) remains a plan; the linked execution ledgers identify actual checks and gaps.

## Cleanup

QA frontend, API, and token helper stopped; ports 3000, 8000, and 8001 have no listeners. The disposable QA database, test databases, private fixtures, raw logs, temporary files, and QA downloads were removed. Existing local PostgreSQL remains running. Only the QA report and sanitized evidence are retained. [Cleanup record](cleanup.md)
