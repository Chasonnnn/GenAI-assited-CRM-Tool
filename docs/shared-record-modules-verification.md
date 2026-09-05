# Shared record modules: local verification

Date: September 5, 2026. Base revision: `930cd7b2`. Changes remain uncommitted in the current checkout.

## Automated checks

| Check | Result |
|---|---|
| API suite, excluding migration files | 2,844 passed; the new owner-options endpoint required an OpenAPI snapshot update. The corrected contract test passed separately, covering all 2,845 tests. |
| Existing migration tests, serial | 51 passed. |
| Database schema | At `20260830_0100`; Alembic detected no new upgrade operations. No model or migration changes. |
| Python lint | Ruff passed for all changed Python surfaces. |
| Frontend types and lint | Final typecheck and full ESLint passed. |
| Frontend full suite | 1,465 passed; three tests exceeded the existing five-second limit. All affected files passed isolated reruns: match detail 17/17, and surrogate detail, form builder, and IP detail 90/90. No timeout limits were changed. |
| React Doctor 0.9.12 | No findings across 36 changed files at scan time. Remote score service unavailable; no numeric score claimed. |
| Patch whitespace | `git diff --check` passed. |

API tests used an explicit disposable PostgreSQL 18.1 database on loopback port 55435, separate from the configured application database. Migration tests ran serially after the main API suite. No production database or messaging provider was used.

Frontend verification corrected two obsolete assertions: the donor document component no longer contains a native file-input exception, and the Next.js instruction test now checks the existing root-only instructions. The shared task row uses the project's Button primitive. A run with fewer workers still had the three timing failures above; isolated reruns passed their assertions, but the full run itself was not green.

## Browser verification

Visible Chrome used the real local API and frontend, with synthetic records and no messaging-provider credentials. API and frontend ports were 8015 and 3015. External browser requests were blocked.

| Flow | Verified behavior |
|---|---|
| Surrogate notes and tasks | Existing tabs retained; shared rich-text note creation worked; list/calendar controls remained visible. |
| Intended parents | Compact cards rendered with shared notes, tasks, and documents; note creation, file upload, and full task description loading worked. |
| Egg donors | Compact cards rendered; note creation, task edit, completion/reopening, file upload/deletion, and ownership change to Unassigned worked. |
| Sperm donors | Normal API creation selected the sperm pipeline; shared task creation worked; deleting a note retained its durable activity entry. |
| Failed note save | A browser-injected 503 kept the draft; retry persisted the note and cleared the editor. |
| Failed document read | Browser-injected 503 responses rendered the error state; retry restored the real attachment list. |
| Loading and empty states | Full task editor stayed unavailable while detail loaded; empty notes, documents, and task cards rendered. |
| Mobile | Donor and IP cards fit within a 390-pixel viewport; rich-text controls wrapped. IP header actions remained within the viewport. |

No JavaScript page errors were observed. Simulated error responses produced expected browser console errors. Directly inserted fixtures lacked initial stage-history rows; activity rendering was also checked with a donor created through the normal API. Its note and task events appeared under the correct stage, including the note-deletion event.

## Rendered evidence

The later [donor/IP design comparison](/Users/chason/GenAI-assited-CRM-Tool/output/donor-ip-design-qa/report.md) records twelve responsive/theme views, matched synthetic content, and visual consistency fixes. Its [paired gallery](/Users/chason/GenAI-assited-CRM-Tool/output/donor-ip-design-qa/index.html) supersedes the earlier donor/IP screenshots for current styling.

- [Donor desktop](/Users/chason/GenAI-assited-CRM-Tool/output/module-refactor-qa/donor-desktop.png)
- [Donor mobile](/Users/chason/GenAI-assited-CRM-Tool/output/module-refactor-qa/donor-mobile.png)
- [Intended-parent desktop](/Users/chason/GenAI-assited-CRM-Tool/output/module-refactor-qa/ip-desktop.png)
- [Intended-parent mobile](/Users/chason/GenAI-assited-CRM-Tool/output/module-refactor-qa/ip-mobile.png)
- [Surrogate notes](/Users/chason/GenAI-assited-CRM-Tool/output/module-refactor-qa/surrogate-notes.png)
- [Surrogate tasks](/Users/chason/GenAI-assited-CRM-Tool/output/module-refactor-qa/surrogate-tasks.png)
- [Sperm-donor durable activity](/Users/chason/GenAI-assited-CRM-Tool/output/module-refactor-qa/sperm-donor-activity.png)
- [Note failure with retained draft](/Users/chason/GenAI-assited-CRM-Tool/output/module-refactor-qa/ip-note-error.png)
- [Document error state](/Users/chason/GenAI-assited-CRM-Tool/output/module-refactor-qa/ip-documents-error.png)

## Production boundary

No commit, push, release, deployment, production data change, or external message occurred. Production canary checks, mixed-revision operation, and live provider behavior remain unverified. The [rollout document](/Users/chason/GenAI-assited-CRM-Tool/docs/shared-record-modules-rollout.md) specifies API-first rollout, worker completion, permission checks, preflight, and rollback without a database reset.

Task-owned API, frontend, Chrome session, and disposable PostgreSQL container were stopped. Synthetic session files, uploaded fixtures, and temporary QA scripts were removed; only the linked screenshots and reports remain.
