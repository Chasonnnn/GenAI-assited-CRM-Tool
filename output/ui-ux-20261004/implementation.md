# Approved UI changes — 2026-10-04

Implemented proposals 1, 2 and 3 from the [approved comparisons](comparisons.html). Includes F2 and SCHED-01, the functional prerequisites identified in those proposals. Proposals 4–6 and all other QA repairs remain outside this change.

Local commits on `main`: `ae6864b36` availability; `0627b049f` submission review. No push, pull request or deployment.

## Changes

| Proposal | Implemented behavior |
| --- | --- |
| 1. Submission queues | Pending and processed totals replace five summary cards. Each review queue shows its count once. Successfully loaded empty queues collapse; populated, loading and failed queues remain visible. Failed loads retain Retry. |
| 2. Submission history | Mapped identity appears first, with contact details, submission time and both matching/review statuses. Open record links to the linked profile. Technical matching details use a disclosure; recovery actions use the existing menu primitive. Review Candidates stays directly accessible. |
| 3. Weekly availability | One schedule surface uses day dividers. Timezone sits beside the heading on desktop and beneath it on phones. Enabled days require an end time after the start time. Invalid ranges block saving and identify the end-time control. Save failures show a safe error while retaining the draft for retry. |

F2 uses the submission's mapping snapshot on the standalone page, without requesting form-management permissions. Builder and standalone pages share the updated panel. Donor approval/rejection confirmations, permission conditions, file-rescan actions and existing recovery payloads remain covered by their behavior tests.

## Rendered evidence

- [Submission workspace, desktop](implemented/submissions-desktop.jpg)
- [Submission workspace, phone](implemented/submissions-mobile.jpg)
- [Empty queues, desktop](implemented/empty-queues-desktop.jpg)
- [Matching details and record actions](implemented/history-details.jpg)
- [Weekly availability, desktop](implemented/availability-desktop.jpg)
- [Weekly availability, phone](implemented/availability-mobile.jpg)

Screenshots contain synthetic records only. The history-detail capture follows an intentional re-run of matching, so its pending count differs from the initial workspace capture.

## Validation

`cd apps/web && mise exec -- pnpm run check` passed: route generation, production and test TypeScript checks, ESLint, and **385 files / 3,041 tests**.

- F2 regression failed on the prior implementation because mapped identity was absent, then passed with the snapshot mapping fix.
- Three availability regressions failed on the prior implementation after actual Base UI selection was asserted: reversed range, equal range, and failed-save feedback/retry. All passed after the fix.
- Existing submission behavior tests were adapted to the disclosures and menus. Builder tests exercise loading, failure, retry and recovery for all three queues. Standalone tests cover mapped identity and review permissions. Donor link accessible names include the visible Open record label.
- Independent reviews covered the availability and submission changes. One donor link accessible-name issue was corrected before the final full check.
- React Doctor 0.9.14 reported no errors and one existing complexity warning in the builder hook. A baseline scan confirmed that warning already exists: cyclomatic/cognitive complexity decreased from 57/50 to 54/46 after extracting the shared queue-state calculation. Telemetry and dependency scanning were disabled; no new package was installed.
- No backend source, API contracts, database migrations or dependencies changed. The prior backend test-isolation failure remains unresolved; no new backend suite result is claimed.

## Live browser checks

The real local frontend and API used a migrated disposable PostgreSQL database, synthetic records and existing session/CSRF checks. Outbound delivery was blocked and no workers ran.

| Surface | Observed result |
| --- | --- |
| Availability validation | Monday 09:00–08:00 and 09:00–09:00 showed an inline alert and disabled Save. Disabling Monday removed the invalid range from validation. |
| Save failure and retry | A synthetic HTTP 503 showed Couldn't save availability. Try again. The Monday 16:30 end time and Pacific timezone remained selected. Retrying against the normal API saved both, and reload preserved them. A read-only database check confirmed the stored values. |
| Availability reads | Failed GET showed Couldn't load availability and Try again. Delayed retry withheld the editor, then restored the saved schedule. A successful empty response displayed all seven days as unavailable. |
| Responsive availability | At 390px and 800px, the document width matched the viewport and all controls remained visible. |
| Standalone submissions | Custom mapped names, emails and phones rendered. Pending and Processed selected the expected histories. Matching details exposed technical information only after expansion. Open record loaded the linked surrogate profile. |
| Recovery menu | Enter opened Actions, Escape returned focus to its trigger. Re-run Auto-Match in the builder reached the real local API, showed its success message and updated the matching outcome. |
| Candidate review | The direct Review Candidates action opened the existing candidate controls and two synthetic candidates. Hide Candidates closed the detail surface. |
| Empty queues | The builder's empty fixture initially showed three collapsed rows. Mouse and keyboard expansion revealed each queue's empty state. |
| Failed routing queue | A synthetic HTTP 503 kept the queue expanded with Retry and no misleading zero count. A delayed retry showed loading; recovery restored its two rows. |
| Responsive submissions | The populated standalone workspace fit at 390px with no document-level horizontal overflow. Identity, status badges and action controls remained readable. |
| Browser console | Final warning/error reads were empty. Intentional failed HTTP requests were recorded separately by the API harness. |

Donor branches, other queue load failures and permission variants were covered by automated tests in this follow-up; they were not all repeated manually. This is a focused implementation verification, not a new claim that every earlier QA limitation is resolved.

The harness recorded 308 requests and no unexpected HTTP 5xx responses. Seven HTTP 503 responses were intentional fault injection. Background unauthenticated dashboard polling produced 76 HTTP 401 responses; an initial helper-login HTTP 422 was corrected in the private harness. One HTTP 400 from workflow-metrics telemetry occurred alongside successful record-detail requests; its cause remains unclassified because sanitized logs did not retain the response body.

## Cleanup

Task API PID 3153, frontend PID 1220, launcher PID 1212 and their wrappers exited. Ports 3000 and 8000 have no listeners. The disposable database and private harness were removed. Existing PostgreSQL remains running. Browser viewport overrides were reset and the active app/control QA tabs closed. Only the durable report and synthetic screenshots remain in the repository.

## Remaining issue decision

ROLE-01 was outside this UI change. The user subsequently approved creator access in both permission versions: Case Managers see Approved-and-later surrogates plus surrogates they created, including after reassignment. The [creator-access follow-up](../permissions-creator-20261004/README.md) records that implementation and verification.

The other confirmed issues have scoped fixes that do not require a new product-policy decision. They remain in the [original QA findings](../live-qa-20261004/README.md).
