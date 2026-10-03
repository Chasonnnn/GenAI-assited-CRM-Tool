---
status: accepted
---

# Notification action items are computed on read

Notifications have two tiers. `ACTION_NOTIFICATION_TYPES` in `app/db/enums/notifications.py` lists the types that ask the recipient to do something; every other type is an update. The bell badge counts open action items only. Updates count only as unread.

An action item is open while its work is outstanding. `notification_service._action_open_condition` decides that in SQL from live domain state on every list and count:

- Workflow approval: the task is still pending, not completed, and owned by the recipient.
- Task assigned: unread, younger than 14 days, and the task is still open and owned by the recipient.
- Task overdue: the task is still open, owned by the recipient, and its due date is before today (UTC).
- Status change request: a pending request on the same entity exists that was made at or before the notification.
- Claim available: the surrogate is still in a queue and not archived.
- Appointment request: the appointment is still pending.
- Match conflict: the proposal is still under review.
- Contact reminder: the recipient still owns the surrogate and no contact attempt was logged after the notification.
- Surrogate assigned, attachment quarantined: unread and younger than 14 days.

A newer notification of the same type for the same user and entity supersedes older ones, so daily contact reminders and repeated task notices show once.

No column stores resolution. Nothing writes when the work finishes, and no migration or backfill is needed.

## Considered Options

- Store `resolved_at` and set it from each completion path: rejected. It needs hooks in every task, request, claim, appointment, match, and contact path, plus a backfill. A missed path leaves a stale item and a wrong badge, which is the problem this change fixes.
- Computed on read (chosen): always matches domain state on any code path. Costs: when a teammate finishes the work, other users see it on their next count refetch (tab focus or 60 seconds), not by push; and an item does not record who resolved it.

A new action type must get a clause in `_action_open_condition`; a type without one never shows as open.

The tier split and panel design were chosen from the prototype at https://claude.ai/artifact/MKuXvJKy2zRuPTzArsdnMp (variant A, side panel).
