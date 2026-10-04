# UI/UX optimization review — 2026-10-04

[Current versus proposed mockups](comparisons.html)

Six focused comparisons use screenshots captured during the same local QA at `65bca746e`. The proposed panels retain Noto Sans, the existing neutral surfaces and magenta/violet actions. Application source is unchanged. These are recommendations, not implemented fixes.

## Prioritized comparisons

| Step | Current health | Proposed change | Trade-off or prerequisite | Comparison |
| --- | --- | --- | --- | --- |
| 1. Submission queues | Working but repetitive. Five summary cards repeat counts from three queue panels; two large panels are empty. | Keep pending/processed totals; show each queue count once. Collapse only successfully loaded, empty queues into rows. | Empty detail takes one click. Preserve loading, error and Retry states; populated queues stay expanded. | [Queue comparison](01-submission-queues.jpg) |
| 2. Submission history | Recovery controls compete with review work. Raw UUIDs occupy primary space; F2 hides mapped identity. | Lead with identity and both match/review statuses. Use Open record for the record link; move technical details and recovery actions into disclosures/Actions. | Recovery takes one extra click. Restore identity through F2 first. Keep Review Candidates visible where applicable, confirmations and permission conditions intact. | [Action comparison](02-submission-actions.jpg) |
| 3. Weekly availability | Controls work; invalid ranges fail silently. Every day has another bordered container. | Use dividers within one schedule surface. Put timezone beside the heading. Show an end-time error and disable invalid Save. | The validation behavior requires SCHED-01 fixed; it is not cosmetic. Keep every day, timezone, dirty-state and save behavior. | [Availability comparison](03-availability.jpg) |
| 4. Appointment outcomes | Incomplete navigation: No-show cannot be found; Past means Completed only. | Keep Upcoming/Pending; combine Past/Cancelled/Expired into History with an All outcomes selector including No-show. | This is the largest workflow choice. It requires history data and counts across terminal statuses; individual outcomes take one extra filter selection. | [History comparison](04-appointment-history.jpg) |
| 5. Report summary | Mixed metric scopes and incorrect date ranges; five cards wrap as four plus one. | Keep three core metrics together. Use one no-data Meta row only when both datasets are confirmed absent; retain metric definitions in a disclosure. | Fix REPORT-01/02 before trusting period labels/counts. Preserve independently available Meta metrics, provider errors, loading and AI Usage when enabled. | [Report comparison](05-reports.jpg) |
| 6. Pipeline settings | Functional, but fixed rules look editable and long mobile selections truncate. | Show fixed rules as read-only values in a disclosure, group technical mappings, and give long selections a full mobile row. | Advanced inspection takes a click. Preserve fixed values, lock explanations, dependencies, stage actions, reorder and save/discard behavior. | [Pipeline comparison](06-pipeline-settings.jpg) |

## Source evidence

1. Submission overview: `apps/web/components/forms/builder/AutomationFormSubmissionsPanel.tsx:434`, `:608`, `:749`, `:832`. [QA capture](../live-qa-20261004/screenshots/forms-standalone-missing-identity.jpg).
2. History identity/actions: `apps/web/components/forms/builder/AutomationFormSubmissionsPanel.tsx:975`, `:1074`. Existing menu pattern: `FormBuilderHeader.tsx:110`. [QA capture](../live-qa-20261004/screenshots/forms-standalone-missing-identity.jpg).
3. Availability: `apps/web/components/appointments/AppointmentSettings.tsx:467`, `:477`, `:538`, `:577`. [QA capture](../live-qa-20261004/screenshots/scheduling-invalid-availability.jpg).
4. Appointment tabs: `apps/web/components/appointments/AppointmentsList.tsx:284`. [QA capture](../live-qa-20261004/scheduling-past-outcomes.jpg), [lifecycle reproduction](../live-qa-20261004/scheduling-lifecycle.md).
5. Report cards: `apps/web/app/(app)/reports/page.tsx:383`, `:422`, `:452`, `:483`, `:539`. [QA capture](../live-qa-20261004/screenshots/reports-today-period.jpg), [date defects](../live-qa-20261004/reports-dashboard.md).
6. Pipeline controls: `apps/web/components/pipelines/stage-settings.tsx:311`, `:345`, `:401`, `:470`. [QA capture](../live-qa-20261004/settings-evidence/pipeline-mobile-stage.jpg).

## Additional small opportunities

| Surface | Current → proposed | Evidence / source |
| --- | --- | --- |
| Form preview | Repeated Preview eyebrow, heading, in-frame label and Builder preview chip → one heading and Desktop/Mobile controls. Preserve the actual applicant form content and any readiness errors. | [Capture](../live-qa-20261004/screenshots/forms-builder-mobile-preview.jpg); `FormBuilderPreviewPane.tsx:39`, `FormBuilderCanvasPreview.tsx:165` |
| Application tables | Structured answers squeezed beside a scalar label; Identity stretches to its neighbor's height → put tables below their labels at full card width and align cards at the top. | [Capture](../live-qa-20261004/screenshots/forms-approved-application.jpg); `SurrogateApplicationTab.tsx:1119`, `:1206` |
| Appointment phones | Two phone icons with different numbers → concise Dial-in and Client phone labels. Keep both numbers and telephone links. | [Capture](../live-qa-20261004/screenshots/scheduling-pending-detail.jpg); `AppointmentDetailDialog.tsx:481`, `:501` |
| Account settings | General tab plus General card heading and broad Managed via Google SSO hint → remove the repeated heading and broad hint. Keep the email-specific SSO explanation and Duo information. | [Capture](../live-qa-20261004/settings-evidence/sessions.jpg); `apps/web/app/(app)/settings/page.tsx:692`, `:1438` |
| Mobile performance | Unlabelled 5.3% badge plus Match conversion 5.3% tile → keep the labelled tile only. This loses the top-of-card percentage scan. | [Capture](../live-qa-20261004/reports-mobile-performance.jpg); `TeamPerformanceTable.tsx:279` |

The six primary proposals are mocked. Additional opportunities above are documented with current captures and specific changes; they are not separate rendered mockups.

## Recommended scope

- Start with empty-queue compaction, duplicate preview labels, duplicate conversion badges and redundant settings copy. These remove repetition without changing workflow semantics.
- Group recovery controls and improve mobile pipeline labels next. Use the existing Base UI components, preserve keyboard focus and retain accessible names for every action.
- Keep functional QA repairs separate: mapped identity, form autosave, no-show visibility, silent mutation errors, report date ranges and role-aware actions. A cleaner screen does not resolve those failures.
- Treat the three-tab appointment proposal as a workflow decision; merely restoring No-show access is the smaller functional fix.

## Verification and limits

- Inspected all six current screenshot regions and compared them with rendered proposals in the in-app browser. Current screenshots are embedded unchanged; cropping is presentation-only and Full capture opens the original image.
- Desktop panels use the same source content width and display scale. Full-size panels provides readable detail. Narrow preview changes the proposed container, not the original screenshot or the browser device.
- Verified navigation, full-size/narrow controls, empty queue expansion, submission filtering, recovery menu keyboard activation, mock-only action dialog and Escape dismissal, original-image modal, invalid-time blocking, valid-time Save, No-show filtering, metric definitions, and pipeline fixed/technical disclosures.
- The narrow availability panel measured 408 CSS pixels with no horizontal overflow. The pipeline comparison uses 390px panels. [Narrow availability](07-availability-narrow.jpg).
- Final mockup browser console check returned no warnings or errors. JavaScript syntax validation passed. No full application suites were rerun because this change contains only isolated review artifacts.
- This is not a complete accessibility audit. Production implementation still needs focus management, screen-reader error announcements, zoom/reflow and status-specific regression checks. Read-only fixed values must remain readable rather than disabled low-contrast text.
- Mock interactions change only in-memory sample state. They make no API calls and do not persist settings. Record names are synthetic. The proposed report count illustrates the earlier trend evidence and is not a new verified API result.
- The broader local functional QA, provider boundaries and unverified scenarios remain in the [QA report](../live-qa-20261004/README.md).

## Preview lifecycle

The browser rejected direct file URLs. Verification used a loopback-only HTTP endpoint serving exactly this artifact, with no directory listing, arbitrary file routes, external assets or API access. Preview PIDs 80164 and 80753 were stopped; the final process exited with status 143 and port 8767 has no listener. The self-contained HTML and captured comparisons remain available. The loaded browser tab remains interactive until refreshed or closed.
