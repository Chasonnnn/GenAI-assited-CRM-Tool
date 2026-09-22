# Scheduling UI polish — September 22, 2026

Implemented the eight approved scheduling designs using the existing component system. Google Calendar remains the supported provider for this work; Scheduling V2 remains disabled by default.

| Surface | Changes and verification |
| --- | --- |
| Appointment details | Appointment status and compact Google sync status share the header row; actionable errors and conflicts remain in the body. Contact links, meeting link, bounded dialog and reachable actions. Inspected at 1280×720 and 390×844. |
| Reschedule | Shared date and time picker, timezone labels, selected-slot semantics, retry, and a separate manual-time mode with a required reason. Browser saves succeeded for an available slot and an after-hours override. |
| Interview cancellation | Default move to Reschedule Needed and explicit keep-current-stage choice. First booking from New Unread succeeded; cancellation persisted and changed the stage to Reschedule Needed. |
| Google synchronization | Quiet success/pending states, retry/setup actions, amber conflict choices, explicit Apply, and revision/ETag-bound selection. A synthetic 412 conflict was resolved through the UI and delivery completed. |
| Calendar settings | Google uses the same compact card layout as the other integrations. Manage opens calendar selection, sync details, conflict/display toggles, dirty Save, and Disconnect in a bounded dialog. Saving a display toggle persisted; Sync queued and processed through the normal service. |
| Record scheduling | Shared picker, manual date/time plus reason, and retained Match/Attempt controls. A weekend intended-parent appointment saved without selecting an available slot. |
| Public booking | Compact type, time, contact, and confirmation steps; timezone-aware summaries; initial availability retry; visible submission errors. A rejected email produced an inline error, retained the form, and confirmed after correction. |
| Public manage | Token-permitted actions, timezone-aware appointment and slot display, weekend selection, keyed availability requests, named month controls, and recoverable load errors. Pacific-time rescheduling confirmed the selected local date/time on mobile. |

## Additional QA fixes

- Dialog width defaults squeezed the calendar into the time choices. Explicit scheduling widths and container-based stacking now prevent overlap. The measured desktop dialog is 672px wide with two 308px columns and a 16px gap.
- Empty slot panels now distinguish an unselected date from a date without available times.
- The public booking form previously gave no visible feedback for a server-side validation rejection. It now displays sanitized errors and supports correction and retry.
- Conflict selection no longer switches the Base UI radio group from uncontrolled to controlled.
- Public manage capabilities are returned in both feature-flag modes. Each link permits only its token's action; server routes enforce the same restriction. A cancellation link is required to cancel, including when V2 is disabled.
- Interview preview uses the same host and appointment defaults as booking, checks authenticated access, excludes the active appointment, and does not create database records during preview.
- Switching the booking destination between existing Google calendars now clears the previous destination before enabling the replacement in the same transaction. The regression reproduced the unique-index failure and passes after the fix.

## Validation

- Frontend type checking, ESLint, and full Vitest suite passed: 275 files, 1,640 tests.
- Aggregate affected backend scheduling suites passed: 169 tests, including API contracts, tenant boundaries, commands, Google concurrency, bindings, migration, and inventory.
- Interview API and OpenAPI contract validation passed: 54 tests.
- Independent review found no actionable P1/P2 issues in the changed UI surfaces.
- React Doctor 0.9.14 reported no errors. Remaining diagnostics concern component complexity and the intentional form `preventDefault`; the remote score endpoint was unavailable.
- Mobile details and public manage measured 390px document width at a 390px viewport, with no horizontal overflow. Dialog actions stayed reachable.
- Final integration cards measured the same 314.7px width and 246px height at 1280×720, with aligned button bottoms. The Google details dialog measured 358px wide at a 390px viewport; saving preferences inside it succeeded.
- Header status follow-up passed type checking, ESLint, and 38 focused appointment/sync/calendar tests. Pending and completed sync headers were checked in the local browser; both badges fit one row at 390px without dialog overflow.
- Pre-publication backend validation passed 323 affected scheduling, migration, provider, worker, and API-convention tests in a disposable database. Ruff passed on all changed Python files.

## Limits

QA used a disposable PostgreSQL database and a synthetic Google transport with external HTTP blocked. Only calendar jobs were drained; email delivery jobs were not executed. Real Google OAuth, invitations, push delivery, and account permissions were not exercised. No production data, deployment, feature activation, commit, push, or PR is included in this round.

The local preview was retained for review. QA-created browser tabs were closed and temporary viewport overrides were reset; user-owned tabs remained open. Reusable synthetic harness instructions are in `tests/support/README.md`.
