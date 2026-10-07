---
status: accepted
---

# Notification email is opt-in per notification type

In-app notifications can also go to the recipient's account email. Each email channel is a separate boolean on `user_notification_settings`, mapped from a notification type in `notification_service.EMAIL_SETTING_BY_TYPE`. The first and only channel is `email_workflow_notifications`, for `workflow_notification` notifications created by the workflow Send Notification action (new applications, new leads). Types without a mapping never send email. Every email column defaults to false in the model and in the database, so no one receives notification email after deploy until they turn it on.

`create_notification` queues the email in the transaction that creates the notification, through `platform_email_service.queue_email_logged` into the transactional email outbox; the outbox worker sends it with leased, bounded retries. The idempotency key is `notification-email:{notification_id}`, so re-queueing the same notification returns the existing delivery. A failed enqueue rolls back only its savepoint; the in-app notification still commits. The email is queued only when the recipient's user and membership in the notification's organization are active, and the outbox re-checks membership, the toggle, and the recipient address before sending. Existing suppressions and opt-outs apply.

The email renders the `staff_notification` platform system template. Its From address comes from the template's `from_email` (set in Ops) or `PLATFORM_EMAIL_FROM`; without either, no email is queued.

## Daily digest

`email_daily_digest` is a separate opt-in, also default false. It is not mapped from a notification type. Once per day, between 08:00 and 12:00 in the organization's time zone, the worker queues one `notification_digest` job per organization with opted-in members (idempotency key `notification-digest:{org_id}:{local_date}`). The job queues one email per opted-in member that lists their open action items (ADR 0009) and their unread updates from the last 24 hours, at most 10 of each. A member with neither gets no email. The email reuses the `staff_notification` template, its idempotency key is `notification-digest:{org_id}:{user_id}:{local_date}`, and the outbox re-checks membership, the toggle, and the address before sending. `NOTIFICATION_DIGEST_ENABLED=false` stops the scheduling.

## Considered Options

- One email toggle for every existing in-app toggle: deferred. Most in-app toggles group several notification types and nobody asked for email on them; each new channel is one column, one mapping entry, and one UI row.
- One global "email me my notifications" toggle: rejected. It would email every task, reminder, and status notification at once.
- Default on: rejected. Existing users would start receiving email without choosing it.
