# Scheduling browser QA — 2026-10-04

Revision: `65bca746e`. Local Next dev server, disposable migrated PostgreSQL, synthetic Google transport. No external delivery.

## Confirmed findings

- **SCHED-01 — Invalid availability save fails without visible feedback (medium).** Scheduling Settings → Availability → Monday start 9:00 AM, end 8:00 AM → Save availability. `POST /appointments/availability` returns HTTP 400. The form stays editable with Save enabled, but no inline error or toast explains the failure. Browser console has no error. Screenshot: `screenshots/scheduling-invalid-availability.jpg`. Production handler `saveRules` in `AppointmentSettings.tsx` only attaches an `onSuccess`; confirm the mutation hook's feedback contract before fixing.

## Executed checks

- Initial local profile completion saved and opened dashboard; normal app auth and CSRF retained.
- Availability loads weekday 9–5 schedule, Eastern Time labels, weekend unavailable switches and disabled unchanged Save.
- Saturday enable → Save → reload persisted checked state; restored Saturday disabled and saved.
- Appointment Types tab rendered seeded phone and Google Meet types with active/auto-approve labels.
- Add type dialog: blank-name Create focused Name and showed “Enter a name.”
- Last selected meeting format cannot be unchecked; adding Phone first permits deselecting Zoom.
- Phone + In-Person selection exposes required dial-in and location. Submit without location focuses Location.
- Confirmed-message switch disables its template picker. Reminder timing options show labels; selected 2 hours before.

## Additional executed checks

- Created QA Scheduling Multi-format (Phone + In-Person), required location/dial-in, manual approval, Confirmed messages off, 2-hour reminder. Reopened: all settings persisted. Selected named Appointment Reminder (24h) template and saved.
- Booking Link copy matched `http://localhost:3000/book/test-admin`.
- Public booking type/format selection worked. Stale calendar snapshot showed explicit error and Retry; after synthetic binding sync, Retry enabled weekday dates/slots.
- Public blank contact submit displayed name/email/phone errors; malformed email received native validation; `.test` email was rejected by server validation and `example.com` fixture accepted. Too-short phone produced generic details error; valid contact submitted.
- Public multi-format In-Person request succeeded for Oct 7 10:00 Eastern. Staff pending list/detail retained name, note, format and location. Linked an intended parent and approved; Upcoming count updated.
- Staff rescheduled an existing appointment from Oct 13 09:00 to 10:00; row showed Google updating, then synthetic drain produced Google Calendar synced.
- Staff Saturday date showed no available times and disabled save; selecting a weekday restored slots.
- Self-service rescheduled public appointment to Oct 8 11:00 Eastern. Reloading the old reschedule URL returned Appointment not found (token rotated). Separate cancel-token flow accepted optional reason and showed Appointment Cancelled.
- Staff custom-time form disabled Save without a reason. Native keyboard date input plus a reason saved Nov 13 08:00 Eastern outside weekly hours.
- Search no-match state displayed No matching appointments and Clear filters. In-Person filter displayed human-readable trigger/chip and only matching record. Reset restored all types.
- Calendar Month and Week rendered appointments; Next period navigation and event detail opening worked.
- Add to Calendar was clicked, but the browser download event timed out; file download is not verified. No console error was observed.
- Public management immediately after approval temporarily displayed This appointment can no longer be changed while Google delivery was pending; after drain/reload rescheduling became available. This wording is misleading for a temporary synchronization state.
- Invalid availability did not persist: read-only database check still showed Monday09:00–17:00.
- Synthetic Google update failure exhausted the scoped appointment job, displayed Google update failed, and exposed Retry Google update after a fresh detail load. Returning the provider to normal, clicking Retry, and draining only calendar jobs restored Google Calendar synced.
- A remote event edit followed by a CRM reschedule produced Google conflict. Both schedules appeared with local times and timezone. Apply stayed disabled until a radio choice. Keeping Google restored its09:00 time; a second conflict kept CRM13:00 and synced successfully after the guarded drain.
- Concurrent inbound changes caused “Appointment changed; refresh and try again.” Reload showed the current revision, and a new reschedule succeeded. Provider-unavailable save also displayed an alert and retained the chosen slot.
- Combined Tasks calendar rendered three recurring Google instances on Oct7/14/21, an Oct8 point event, and an Oct9 all-day event. The dedicated Appointments calendar continued to show CRM appointments. Screenshot: `screenshots/scheduling-external-calendar.jpg`.
- Edited the synthetic multi-format type from30 to45minutes and buffer5 to15minutes; save succeeded and the list displayed45minutes.
- Deactivate dialog named the synthetic type and its booking-page effect. Confirm removed the type from both settings and the public booking page. Inactive types have no visible restore path in the current settings screen; this is recorded as a product limitation, not a demonstrated data-loss defect.
- Mobile public booking validation is recorded in `communications.md` with390px calendar and details screenshots.

## Diagnostics and limits

- Final browser console review: no error entries in either scheduling or public-booking tab. One notification WebSocket fallback warning at20:04:09UTC coincided with the task API restart at20:04:13UTC; the UI continued through polling.
- Google transport was synthetic. Retry, conflict, and snapshot state were exercised with the real service/job code; no real Google account, invite delivery, email, or SMS was verified.
- Add to Calendar download bytes remain unverified because the browser download event timed out.
- IAB mobile emulation changed DOM dimensions to390px but returned mismatched screenshots. Its overrides were reset; the separate Chrome pass supplied the mobile evidence.
- This ledger records executed scenarios. It does not claim every possible date, role, provider, or scheduling combination.
