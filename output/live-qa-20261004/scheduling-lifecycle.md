# Scheduling lifecycle supplemental QA

Revision `65bca746e`; 2026-10-04. Browser checks use the isolated local QA database and synthetic Google provider.

## Finding

**SCHED-LIFE-01 — P2: No-show appointments disappear from list navigation.**

1. Open a confirmed past appointment and click No-show.
2. The dialog closes and the appointment disappears from Upcoming.
3. Past contains only completed appointments. There is no No-show or All status tab.
4. Reload and search for the no-show client: all five status counts are zero and Past shows `No matching appointments`.

The mutation succeeds: appointment `038d6d83-02da-4c0e-bb62-661473869bae` persists `status=no_show`, `revision=1`. `AppointmentsList.tsx:286` maps Past to the single `completed` status. Users cannot recover no-show records through the appointment list or its search. Calendar access was not used as a workaround in this check.

[Past outcomes](scheduling-past-outcomes.jpg) · [No-show search](scheduling-no-show-missing-search.jpg).

The Upcoming tab also includes past confirmed appointments until an outcome is recorded. This is recorded as label behavior, not a separate failure finding.

## Completed and expired states

Three independent fixtures belong to QA Review Admin, separate from the parent agent's scheduling records.

| Appointment | Initial fixture | Browser result |
| --- | --- | --- |
| `6579a2cf-1cc7-4312-80b4-dd9943624f9e` | Confirmed, Oct 2, QA Past Complete | Completed button succeeds; moves to Past with Completed label; persists after reload |
| `038d6d83-02da-4c0e-bb62-661473869bae` | Confirmed, Oct 3, QA Past No Show | No-show succeeds; SCHED-LIFE-01 |
| `607685a8-f74d-46b3-9fe3-b177f5bb3c77` | Expired request, Oct 6 | Expired tab/detail renders; no Approve, Cancel, Reschedule, Completed, or No-show actions |

[Expired detail](scheduling-expired-detail.jpg). Expired status was seeded directly; background TTL expiration was not exercised.

## Google Meet pending and recovery

- Public `/book/test-admin`: select QA Google Meet, Oct 20 10:00 AM Eastern, fill synthetic name/email/phone, confirm.
- Public page shows Appointment Confirmed with correct date/time/type and Add to Calendar.
- Synthetic provider returns conference pending during event creation. Only this appointment's job is processed through the production dispatcher.
- Staff appointment `75bfc1f5-7fce-470c-aa0e-259daa4c0197` shows Confirmed + Google updating, no join URL, and Cancel only while synchronization remains pending.
- The synthetic remote event is changed to contain a ready conference and provider mode returns to normal. Processing the same pending job observes the existing remote event and completes sync without recreating it.
- Reloaded staff detail shows Google Calendar synced, Join Google Meet, Cancel, and Reschedule. The link points to the synthetic `.test` host and was not opened.

[Conference pending](scheduling-conference-pending.jpg) · [Recovered conference](scheduling-conference-recovered.jpg).

Provider mode is normal after this pass. No unrelated scheduling jobs were claimed. No real Google invitations or external messages were sent. Console checks for completion/no-show/expired controls returned no captured errors or warnings.
