# Scheduling v2

Scheduling v2 is an opt-in scheduling and Google Calendar synchronization boundary. It is disabled by default through `SCHEDULING_V2_ENABLED=false`. The database migration is additive. Existing appointment rows are retained and receive `origin=legacy_unknown`; new ORM-created appointments use `origin=crm`.

## Ownership and data

`Appointment` is the canonical CRM record. It owns the host, client and record relationships, lifecycle, current interval, revision, availability override reason, and Google link fields. Pipeline stage remains a separate workflow state.

`CalendarBinding` is an explicit organization, owner, Google integration, and calendar selection. A binding records whether it contributes busy time, display projections, or booking writes. Database constraints scope bindings to an organization membership and the owner's integration; runtime queries require the membership to remain active. One active booking destination is allowed for each organization and owner.

`ExternalCalendarEvent` is a projection for one binding. It stores provider event metadata, interval or all-day dates, busy/private flags, and no event descriptions. Projections are never used to create CRM appointments.

`SchedulingRequestReceipt` stores the safe result of an accepted mutation. Its unique organization, actor scope, and request key fence makes an exact retry replay the accepted appointment result. Reusing a request key with a different payload is rejected. Public actor scopes use a hash; the token itself is not stored in the receipt.

## Command transactions and locks

V2 commands lock the appointment owner and active membership before the tenant-scoped appointment row. Commands validate the expected revision, availability, and required external busy data while the owner lock is held. Staff availability overrides require a non-empty reason; public booking cannot supply an override.

When an override is recorded, its audit details contain a SHA-256 digest and encrypted reason rather than the plaintext. The authorized audit response decrypts the reason and removes the encrypted value from its output; an unavailable decryption is returned as a placeholder.

The command transaction persists the appointment change, revision, audit record, scheduling receipt, email intent, reminder or expiry job, in-app notification job, and Google sync intent together. An error in a coupled audit or workflow operation rolls back these local changes. Idempotency replay does not repeat lifecycle side effects.

Google provider I/O is deferred to the existing job worker. V2 jobs carry the exact organization, binding, integration, account, calendar, deterministic event identity, target revision, and base snapshot. The worker checks the current link and binding before and after provider I/O, uses a short locked claim to persist its result, and does not hold a domain row lock while making the HTTP call.

CRM sends its own lifecycle email for local-only appointments. For a linked Google appointment, attendee-facing confirmation, reschedule, and cancellation email intents are suppressed; pending-request email remains CRM-owned. Reminder, expiry, and notification jobs are durable local intents.

## Google bindings and reconciliation

Binding discovery and replacement verify the connected user's Google calendar access. A writable booking destination must be active and have an owner or writer access role. Missing, disabled, or read-only destinations leave a Google Meet appointment unlinked rather than selecting a calendar implicitly.

Incremental binding synchronization reads Google outside a database transaction. It persists a projection and cursor only for a complete result from the exact bound calendar. An expired cursor rebuilds projections; a failed or incomplete read records a sanitized binding error and does not infer appointment deletion.

After the provider read, inbound synchronization locks in this order: active owner, binding, linked appointment. Staff commands and conflict resolution take the same owner-before-appointment order. A verified organizer event is compared with the last synchronized state, current CRM state, and provider ETag:

- Equal or one-sided changes converge.
- A valid organizer-only time or cancellation change is applied to the CRM appointment without an outbound echo and preserves its pipeline stage.
- Competing edits, invalid intervals, missing linked events, or identity mismatches are stored as a conflict.
- Conflict resolution rechecks the current revision, observed ETag, owner, link, and writable binding. Choosing Google applies the observed state locally; choosing CRM queues a revisioned Google intent. A deleted event selected for CRM resolution requires manual review.

Retry requeues a failed Google intent. An unlinked, confirmed CRM appointment without an event can also retry after a writable booking destination is configured. Retry changes delivery state only; it does not replay CRM lifecycle effects or notifications.

## Rollout and recovery

Keep `SCHEDULING_V2_ENABLED=false` until the organization inventory is reviewed and a separately authorized rollout plan exists. The inventory command is read-only, takes an explicit organization ID, and returns aggregate appointment provenance, link completeness and duplicates, binding readiness, and scheduling job state. It excludes client fields.

```bash
cd apps/api
mise exec -- uv run python scripts/scheduling_inventory.py --organization-id <organization-uuid>
```

Do not adopt, relink, or write Google events for `legacy_unknown` appointments based on inventory output. Ambiguous historical links require manual review. Recovery uses the persisted sync state and conflict record: restore or choose a writable binding, retry a failed delivery, resolve an observed conflict with a current revision and ETag, or manually review deleted and ambiguous resources. Disabling the flag prevents new V2 command and worker behavior; it does not remove migrated data or undo a provider operation already completed.

## Verification boundary

Implementation coverage includes migration invariants, command atomicity and idempotency, tenant and public-token boundaries, availability and override handling, durable job delivery, binding/watch behavior, incomplete sync recovery, and inbound/staff concurrency. Relevant coverage is in `tests/test_migration_20260922_scheduling_v2_schema.py`, `tests/test_scheduling_command_boundary.py`, `tests/test_scheduling_v2_domain.py`, `tests/test_scheduling_v2_api.py`, `tests/test_scheduling_google_provider_service.py`, `tests/test_scheduling_binding_watch.py`, `tests/test_scheduling_inbound_concurrency.py`, and `tests/test_scheduling_inventory.py`. Local verification uses mocked provider behavior and a disposable database.

Real Google OAuth authorization, calendar discovery, watch delivery, provider writes, and production rollout have not been locally verified by this implementation. Those require a separately authorized test account and environment.
