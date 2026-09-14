# Donor details local QA

Date: 2026-09-14. Base: donor intake PR #703 (`0a3761de`).

The local Next.js app called the local FastAPI service against disposable PostgreSQL 18.1. All records, notes, tasks, identifiers, and uploaded documents were synthetic. Browser checks used the actual donor details page and normal authenticated mutations.

| Check | Observed result |
| --- | --- |
| Contact information | Edited full name; value persisted after reload. |
| Demographics | Changed weight from 135 to 145 lb; BMI changed from 21.8 to 23.4 and persisted. |
| Questionnaire answers | Education updated in both cards. College persisted. One-click nicotine answer changes and keyboard activation saved; clearing an answer remained blank after reload. |
| Personal information | Added a partner and saved their name. Canceling a college edit retained the previous saved value. |
| Medical record | Changed the lab clinic name; one update appeared in activity and persisted. |
| Sensitive information | Saved a synthetic SSN, verified masking and explicit reveal, then verified the masked state after reload and the reveal event in History. |
| Stage | Selected Contacted using the stage button and saved; badge and history persisted. |
| Assignment | Assigned Test Admin through header actions; success notification and activity appeared. |
| Notes | Verified empty state, added a note, and verified it after reload. |
| Tasks | Created a linked donor task, edited its due date, completed and reopened it, and verified it in the calendar. |
| Attachments | Uploaded a synthetic PDF; Clean status and Download control persisted after reload. |
| History | Verified stage, note, task, attachment, assignment, and sensitive-info reveal events. |
| Read-only role | Profile editors and checklist controls were disabled or absent; Change Stage was absent. |
| Mobile | At 375px, page width was 375px with the populated overview visible. |

Live QA reproduced duplicate saves and a canceled edit being saved by the shared inline editor's delayed blur handler. Regression tests failed before the fix and passed after it. The editor now saves when focus leaves the editor container, keeps Save/Cancel focus changes inside the container, and prevents concurrent saves. Live retesting confirmed one update per Save and no persisted canceled edit.

Validation:

- `apps/web`: `pnpm run check` passed type checking, lint, and 1,532 tests across 268 files.
- `apps/web`: `pnpm run build` passed.
- `apps/api`: 94 focused donor/profile/intake/attachment/note/task/ownership and migration tests passed, including cross-organization access, denied permissions, CSRF, encryption, explicit clears, and atomic activity writes.
- Ruff passed on all changed Python files.
- The migration applied through the full chain in a disposable database; upgrade/downgrade regression passed.
- The isolated mockup passed its build and four packaging tests with its saved lockfile and matching dependency policy.
- No application console errors or API 5xx responses were observed. A temporary sign-in helper error during setup and a later expired session were resolved before completing QA.

Limits: native task date entry did not persist during the first browser automation attempt; due-date editing through the calendar was verified. Downloading the attachment, external messaging, and deployment were not exercised. Loading/error/validation paths were covered by component and API tests; browser checks covered populated, empty, and read-only states.

The temporary API, web server, sign-in helper, and PostgreSQL container were stopped. The previously running mockup on port 3047 was left available. Original workspace changes were preserved; the PR was prepared in an isolated checkout.
