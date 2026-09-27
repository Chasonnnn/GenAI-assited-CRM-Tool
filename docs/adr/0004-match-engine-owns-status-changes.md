---
status: accepted
---

# Match engine owns every match status change

Every change to a match's status, including decline and the cancellation outcomes handled in the approvals queue, goes through one match lifecycle engine: a transition table with a lock, checks, audit, activity, and a single after-commit effect dispatcher. The approvals queue keeps the request record and UI but calls engine transitions instead of writing match status itself. Before this decision, the approvals service reset cancellation-pending matches directly, without the match lock, audit, or activity, and follow-up effects were fired separately from the router, the match service, and the approvals service.

## Considered Options

- Keep the approvals system writing match status for its own outcomes: rejected because status rules, locking, and audit would again live in two places.
- A durable event queue for follow-up effects: deferred. The in-request dispatcher isolates each effect so one failure does not fail an applied transition, and it can later hand events to a queue without changing callers.
