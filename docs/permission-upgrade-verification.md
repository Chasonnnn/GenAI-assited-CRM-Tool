# Permission upgrade verification

Date: September 7, 2026 (America/New_York). Local implementation on `main`, based on `1ac17c6c`. No production migration, activation, deployment, push, or provider sends.

## Implemented contract

- Five supplied roles, protected Admin/Dev, editable Intake/Case Manager/Operations baselines, and individual additions without individual denies.
- Shared record scope across actions, lists, counts, search, linked records, appointments, submissions, reports, and exports.
- Surrogate, egg-donor, and sperm-donor approval boundaries with atomic Intake collaboration and pool handoff.
- Personal work uses current owner authority. Organization workflows and campaigns use approved organization authority independent of proposer membership.
- Publication creates independent organization copies with proposer credit; workflows start disabled and campaigns start as drafts.
- Studio role editor, People additions and role carryover review, Check access, collaborator controls, and reviewed per-organization activation.

## Automated verification

| Check | Result |
|---|---|
| Integrated API suite, excluding serial migration/outbox files | 3,255 passed |
| All migration tests and email outbox tests, serial | 94 passed |
| Full frontend check: route types, TypeScript, ESLint, Vitest | 1,615 tests passed across 279 files; typecheck and lint passed |
| Stage and surrogate contract generators | Completed; generated stage constants synchronized |
| OpenAPI path/method/status snapshot | Passed in the integrated API suite |
| Ruff and formatting | All 120 changed Python files passed |
| Fresh database Alembic upgrade | Complete chain from empty database through `20260907_2220_work_authority` passed |

Tests used dedicated PostgreSQL databases on a task-owned local PostgreSQL 18.1 container. API tests explicitly set `DATABASE_URL`; no production database was used. Migration files ran serially because they alter shared schema state. Focused test selections overlap with the integrated suite and are not added to its totals.

Security regressions cover cross-organization denial, missing actions, records outside scope, inactive membership, protected roles, stale activation previews, current personal execution authority, final delivery rechecks, approval handoff, and transactional rollback. Queued execution tests include organization work surviving proposer departure and personal work stopping when owner authority is removed.

Approval corrections now retain their domain callbacks until commit. Match cancellation cannot cross applicant approval without the reviewer's approval permission. Post-commit surrogate events preserve the owner chosen by the v2 handoff transaction; legacy queue behavior remains covered.

## Browser verification

The Codex in-app browser used synthetic local organizations and staff at `localhost:3016` with the QA API at `localhost:8016`.

| Journey | Observed result |
|---|---|
| Studio role editor | Ivory/plum layout inspected; Operations note-edit change reviewed, saved, reloaded, and restored |
| Check access | Assigned pre-approval surrogate allowed for Intake and denied for Case Manager |
| People | Protected rows, inherited permissions, individual report addition, and explicit role-change carryover choices rendered |
| Denied permission administration | A single Permissions unavailable state; no administration controls |
| Migration activation | Both individual-revoke removal and role-wide denial paths completed in disposable organizations; refreshed diff required before activation |
| Role-wide denial result | Activated Intake role showed Edit Donors disabled while View/Change Status/Approve remained enabled |
| Egg donor handoff | Intake approval, Case Manager pool claim, collaborator removal, and subsequent Intake denial |
| Sperm donor handoff | Approval immediately displayed Donor Pool and retained Intake collaborator without reload; retained Intake saved contact/education changes |
| Surrogate handoff | Approval immediately displayed retained collaborator; Intake Profile loaded; Case Manager claimed and removed collaboration; subsequent Intake access denied |
| Workflows | Intake personal definition visible; organization definition readable with edit/activation disabled |
| Campaigns | Operations saw organization work without another person's personal campaign; Edit available, Send Now disabled, Details credited Alex Intake |
| Templates | Operations personal list empty; organization template editable, Send test disabled, Details retained proposer credit |
| Form submissions | Intake saw linked and unlinked submissions with review controls; Operations saw only linked submissions with no review controls |
| Application tab | Operations loaded the linked application without Form Builder access; Export remained available and edit/review controls were absent |
| Read-only applicant UI | Operations overview fields and eligibility controls were read-only; profile Edit/Sync disabled; interview creation absent; task creation disabled |
| Reports | Operations saw the pre-approval surrogate; Case Manager saw zero surrogates and the approved donor; organization spend controls were absent for restricted Case Manager scope |

Loading, empty, error, review, and populated permission states also have frontend regression coverage. Browser checks did not exercise every configurable role/stage combination or real provider integration. Publication copying, inactive-member cleanup, queued retries, and rollback behavior were verified through automated tests rather than external execution.

The local notification WebSocket used its existing polling fallback. A synthetic `.test` contact address failed normal email validation during editing; changing it to an `example.com` QA address allowed the save. Two note-editor locator attempts did not modify content; retained edit authority was verified through the contact form instead.

The optional React Doctor command was not run: automatic approval review rejected downloading and executing unpinned `react-doctor@latest`. Repository-pinned TypeScript, ESLint, and Vitest provide the frontend checks above.

Application metadata has a separate record-scoped API. Its picker does not grant Form Builder access or create intake links during reads. Link sending requires explicit email-send authority. Zoom scheduling and invitation authorization is checked before provider access. Invitations use the saved meeting's authorized subject and metadata. Both normal and concurrent retry returns verify that the saved meeting belongs to the same actor and subject; provider execution remains mocked in tests.

## Activation and remaining work

Existing organizations remain on version 1. Production activation requires an exact-version rehearsal with production-shaped data, explicit review of access and execution changes, and release authorization. Active v2 policies block schema downgrade; personal campaigns also block a downgrade that cannot represent them.

The broader donor completion, builder redesign, reporting redesign, per-organization Meta MCP, Twilio provider setup, and global onboarding/UI work remain separate roadmap items. Their module boundaries and order are recorded in `permission-module-refactor-plan.md` and `platform-upgrade-roadmap.md`.

## Delivery

`b1ffdfab` — permission backend, migrations, shared record scopes, execution authority, and regression tests.

`55822dce` — permission Studio, People and migration review, module controls, application access, and frontend regressions.

`81ad5b8d` — scoped application metadata, Zoom authorization, retry binding, and API contract tests.

The task's API process (PID 88986), frontend process (PID 49877), and disposable PostgreSQL container `crm-permission-v2-0907` were stopped and removed as applicable. Process exits, closed QA listeners, and container removal were verified. Temporary QA scripts, synthetic record references, logs, and cache were removed. No task services were left running.
