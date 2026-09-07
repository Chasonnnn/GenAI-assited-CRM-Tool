# Donor live QA — September 6, 2026

Starting revision: `9e665e84`. Local browser QA against a fresh PostgreSQL 18.1 database. Synthetic egg donors, sperm donors, intended parents, and match cases. External delivery disabled; no production changes.

## Results

| Area | Browser evidence | Result |
|---|---|---|
| Donor list | Egg/sperm tabs show separate records; create Jamie Quinn as a sperm donor; search and open D10003 | Passed |
| Donor profile | Assign Morgan Coordinator; change to Contacted using sperm stages; edit education without changing contacts; archive and restore | Passed |
| Notes and Activity | Save donor intake note; note, owner, stage, task, and file events appear | Passed |
| Tasks | Create linked task, complete it, find it in global completed tasks with Sperm Donor D10003 link | Passed |
| Documents | Upload synthetic PNG; file appears with size and activity entry | Passed; scan remains Pending without a worker |
| Matching | Accept donor's second overlapping IP case; preserve side-by-side profiles; save case note; create and complete retrieval attempt | Passed |
| Match completion | Completion with an open attempt shows validation error; completion succeeds after attempt is Completed; outcome remains visible | Passed |
| Appointments | Create sperm donor booking; approve; reschedule 9 AM to 10 AM; cancel; each status persists in donor card | Passed |
| Case appointment context | Create egg donor booking for M10001 and Attempt 1; October 10 appointment appears in that match calendar | Passed |
| Correspondence | Linked ticket plus direct, campaign, and workflow email appear; same-email unrelated control is excluded | Passed after fix |
| Search | Global search for Jamie returns the donor | Passed |
| Reports | Egg total 1; sperm total 2, split New 1 / Contacted 1; subtype-specific stages | Passed |
| Forms | Egg/Sperm lead choices; required-field publishing guard; add mapped name/email/photo; publish local egg form; preview | Passed |
| Campaigns | Choose Sperm Donors; subtype stages and review labels; recipient preview contains exactly Taylor and Jamie | Passed; cancelled before send |
| Workflows | Egg donor triggers/actions; create task workflow; search donor and run safe test; readable result | Passed after label fixes |
| Layout | Donor and IP retain cards and Activity; matches retain side-by-side layout; donor at 390px in light/dark has no horizontal overflow | Passed |

## Fixed findings

1. Donor correspondence omitted campaign and workflow emails. The query now follows tenant-scoped campaign recipients and workflow jobs, retains prior sends, and avoids duplicates. Four egg/sperm regression combinations failed before the fix. Browser confirmed the corrected history and exclusion of the unrelated control.
2. The workflow Fields to Watch selector displayed `Unknown selection` when empty. It now displays `Select field to add`.
3. Workflow dry-run output repeated `create_task` before the action description. It now displays the readable action once. Both label fixes were rechecked in the browser.

Changes are committed locally: correspondence fix `a4c3409a`, workflow labels `33427884`, and donor contact assertions `cb6be9d6`. No schema migration is required. Nothing was pushed or deployed.

## Verification

- 199 donor-related API tests passed against the disposable database: CRUD, analytics, notes, files, tasks, owners, search, campaigns, workflows, hosted forms, Meta routing, matches, attempts, appointments, and correspondence. Includes denied/cross-organization paths and transaction rollback.
- 77 donor-related frontend tests passed across 15 files.
- After the correspondence fix: 11 record integration tests passed, including four new regression combinations; Ruff passed.
- Donor edit assertions now verify populated contact controls and contact preservation during an education edit; all 20 donor-detail tests passed.
- Workflow label verification: 19 tests passed; ESLint and TypeScript passed; both fixes verified in browser.
- Fresh migration chain applied through `20260905_1600_record_integrations`; no downgrade or production migration performed.

## Limits

Public intake submission, photo upload and promotion were covered by automated tests, not a complete browser submission in this run. Profile-photo processing, document scanning/download, Meta synchronization, external calendar synchronization, email delivery, and scheduled workers were not exercised live. AI and SMS remain outside this integration scope. List pagination and every combination of filters were not exhaustively exercised.

The first browser tab reported blank edit contacts and later stalled. Fresh-tab screenshots showed populated contacts; saving education preserved them. Live API and component tests agreed. Appointment submission also required a fresh interaction before it persisted. These were browser-control inconsistencies, not reproduced product defects. The file chooser took about 31 minutes to return; the upload ultimately succeeded.

## Cleanup

Task-owned API PID 49169 and frontend PIDs 45911/45904 stopped. Disposable database container `crm-donor-liveqa-0906` removed. Temporary seed keys and upload fixtures removed. No services intentionally left running.
