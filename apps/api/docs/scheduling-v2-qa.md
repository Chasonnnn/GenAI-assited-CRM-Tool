# Scheduling v2 local QA — September 22, 2026

Verification used disposable PostgreSQL databases, the local web app, and the synthetic Google transport in `tests/support/scheduling_v2_qa.py`. The API and restricted worker blocked non-loopback network traffic. Email delivery jobs were retained but not executed.

## Browser and persisted results

| Flow | Result |
| --- | --- |
| Staff reschedule from an available slot | Saved in CRM and applied to the existing Google event. |
| Staff availability override | Required a reason; saved the selected time and reason; Google delivery completed. |
| Empty or stale availability | Empty dates disabled confirmation. Stale Google data rejected normal booking while staff override remained available. After synchronization, Retry availability loaded the same date successfully. |
| Public booking | Created a confirmed appointment from an available slot without staff override controls. |
| Public self-service reschedule | Saved the new time; the old token could no longer load the appointment after rotation. |
| Incoming Google edit | Updated the CRM interval without an outbound echo. A replay with deliberately stale cached availability passed after the reconciliation-order fix. |
| Competing edits | Displayed both times. Both “Use Google schedule” and “Keep CRM schedule” were exercised successfully. |
| Provider failure and retry | Exhausted only the target synthetic job, showed the failed state, retried from the UI, and completed delivery. |
| Interview stage scheduling | Created an interview and displayed Upcoming and Manage in surrogate details. |
| Cancel before Google creation | Cancelled the interview and atomically moved the surrogate to Reschedule Needed; delivery completed without creating an orphan event. |
| Replacement interview | Scheduled a new interview after cancellation and returned the surrogate to Interview Scheduled. |
| Cancel an existing Google event | CRM became cancelled and the worker deleted the synthetic Google event with attendee updates enabled. |
| Calendar binding settings | Loaded the explicit binding, queued synchronization, and persisted its display preference. Last sync showed completed binding work; the manual-sync toast said Calendar sync queued without advancing that timestamp. |
| Dialog layout | Checked desktop 1280 × 800 and narrow 390 × 844 layouts, populated/loading/empty/error states, native date entry, close/back controls, and visible action buttons. |

## Regression fixes found during browser QA

- Rescheduling used a compact action form instead of stacking the full appointment details above it. The dialog has a bounded scrolling body, fixed header/footer, mobile margins, and shared checkbox controls.
- Complete Google projections and their freshness are flushed before applying any incoming appointment changes. Availability validation sees every event from the completed response.
- Interview actions honor server capabilities, including cancellation while Google creation is pending.
- A cancelled appointment's reschedule capability no longer prevents scheduling its replacement after delivery completes.
- Availability request errors provide a retry action for the same date. The cancellation textarea has an associated label.
- Sync status uses completed binding timestamps. Manual synchronization reports queued calendars separately from completed appointment changes.

## Automated verification

- Full frontend check: 272 files and 1,619 tests passed, with type checking and lint.
- Full backend run: 3,449 passed. Four existing `test_orb_setup.py` cases failed because `dpkg` is absent on the macOS host.
- Final affected backend matrix after the reconciliation fix: 311 passed, including appointments, booking, calendar bindings, Google sync, interviews, worker jobs, migration, watch, concurrency, inventory, and request-boundary tests.
- Final sync-status contract follow-up: 41 API tests, 93 frontend tests, type checking, lint, and the OpenAPI contract test passed.
- Added coverage includes migration upgrade/downgrade invariants, tenant and CSRF denial, request replay and divergent payloads, public token rotation, recorded overrides, provider ETag conflicts, incomplete sync recovery, watch binding identity, and inbound versus staff booking concurrency.

## Limits

Google OAuth, real invitation delivery, Google push delivery, and real account permissions were not exercised. No production data, deployment, provider activation, commit, or PR was part of this QA. Scheduling v2 remains disabled by default.

The temporary API and web servers were stopped. The task-owned PostgreSQL container, disposable databases, private fixture environment, and synthetic provider state were removed.
