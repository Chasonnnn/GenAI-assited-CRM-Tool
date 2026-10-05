# Retire surrogate claim notifications

Date: 2026-10-04, America/New_York.

## Changes

- Approval no longer creates “ready for claiming” notifications.
- Existing claim notices are excluded from notification lists, unread counts, and action badges.
- Legacy queued notification jobs cannot create or push new claim notices.
- The notification Claim action and preference control are removed.
- Surrogate approval, pool assignment, and claiming behavior remain unchanged.

Historical notification rows are retained. The enum and settings field remain compatible with stored data and older queued jobs.

New daily digests use the filtered notification lists. Email bodies rendered and queued before deployment are not rewritten by this change.

## Verification

Before implementation, four backend cases and two frontend cases failed on the retired behavior.

After implementation:

- Backend: 92 tests passed across notification tiers, approval events, queued jobs, AI permissions, controls, pagination, donor isolation, digests, and email.
- Frontend: 50 tests passed across notification actions, settings, bell, email settings, and the full notification page.
- Application and test TypeScript checks passed.
- Focused ESLint, Ruff, Ruff format, and diff checks passed.
- React Doctor 0.9.14 found no issues in the five changed frontend files. Its score service was unavailable.
- Independent review found no further in-app delivery or count defects. It identified the pre-rendered email limitation recorded above.

Backend verification used `apps/api/run_tests.sh` with these files:

```text
tests/test_notification_tiers.py
tests/test_surrogate_status_events.py
tests/test_notification_job_handlers.py
tests/test_ai_actions_permission_v2.py
tests/test_notification_controls.py
tests/test_notifications_cursor_pagination.py
tests/test_donor_notifications.py
tests/test_notification_digest.py
tests/test_notification_email.py
```

Browser verification used actual notification components and styles with synthetic data in an isolated loopback harness.

| State | Result |
| --- | --- |
| Populated | Remaining task, workflow, status-change, and appointment actions render. |
| Task completion | Synthetic completion removes the task and reduces the badge from four to three. |
| Empty | No badge; “Nothing needs you” appears. |
| Loading | Loading indicator and text appear. |
| Error | Error message and Retry button appear. |
| Legacy claim fixture | No inline Claim button renders. Backend tests separately prove stored notices are excluded. |
| Settings | Claim preference is absent; remaining controls render. |
| Console | No warnings or errors observed. |

No production session, provider delivery, or production database was modified.

## Permission migration decisions

The user confirmed that Intake should retain access after approval.

Proposed simplification: preserve currently effective Intake access during activation and retain future handoffs automatically. Make restoration of previously lost access optional.

The earlier clone found three current post-approval Intake owners. Eligibility still requires current membership and permission checks in a fresh preview.

The choice between preserving current access and restoring former owners remains pending. No historical-review or activation behavior changed.

The meaning of “remain in the pool” also remains pending: shared Case Manager visibility versus removal of individual claiming and ownership.

## Cleanup and delivery

Both disposable test databases were confirmed absent. Temporary PostgreSQL adapters and test logs were removed.

The browser harness PID `72142` exited. Port `8768` has no listener. Its temporary directory and browser tab were removed.

Pre-existing PostgreSQL and dependency caches remain intact. No task-owned local service remains running.

Changes are local. No push, deployment, or V2 activation occurred.
