# Production delivery — October 4, 2026

The user authorized commit, push, release, and production activation after the initial audit. They selected each active booking user's connected primary Google calendar for Scheduling V2, approved converting two active Zoom booking types to Google Meet, and accepted managing 397 future legacy-linked appointments in Google until individual reconciliation.

## Delivered

- Cleanup PR [791](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/791) merged as `3645ea3110b8c36dc574af3c5e3ce2867375c6c4`. All exact-head CI checks passed; no review findings remained.
- Release PR [783](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/783) merged after all checks passed. Tag `surrogacy-crm-platform-v0.91.80` points to `b131746a0d9e15c3b6e14161353db7917ad53555`.
- Cloud Build API/worker build `478180f9-df50-457c-9e36-8a4aab71f258` and web build `226c1e41-b3e2-44c0-a3e3-c77cad976c61` succeeded.
- API health returned version `0.91.80`, database head `20261004_1300_organization_logo`, and healthy Redis. A transient migration-readiness 503 cleared when the compatible API revision took traffic.
- Workflow maintenance and approval expiry are enabled on worker `crm-worker-00305-66r`. Logs at 13:04:43 UTC confirm both schedulers ran across three organizations and created zero jobs; expiry ran again at 13:09:48 UTC.
- Match expansion is enabled on the worker and API `crm-api-00260-24b`, in that order. The controls support donor and repeat-case matching, not the removed new-attempt flow.
- Authenticated browser QA verified the workflow canvas, all five time-based trigger choices, and the before/after-appointment timing controls. The draft was not saved or launched.

## Production preparation

Read-only execution `crm-migrate-h2489` inventoried three organizations. There were no enabled maintenance workflows or overdue workflow approvals. All 88 populated legacy medical sections had imported records; no unchanged-record mismatch was detected. Automated Cloud SQL backup `1791082800000` completed successfully at 04:52:32 UTC before release.

Six active booking memberships had connected, writable primary Google calendars. Explicit bindings were created through the existing binding service. Initial synchronization completed for three calendars and failed for three. Historical ambiguous appointment links were not adopted or rewritten.

Diagnostic execution `crm-migrate-56q2f` found equal start/end timestamps in confirmed Google events on all three failing calendars. No event contents, contacts, provider credentials, or tokens were captured in the audit artifacts.

## Scheduling correction

PR [792](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/792) merged as `2866a6eb6e6b37ab788d24994e66ba10a0283eaa` after all 22 exact-head checks passed. It retains point events as projections with no busy interval, expands recurring instances, and rebuilds old unexpanded cursor snapshots. Google requires unchanged list parameters across incremental reads; the [provider contract](https://developers.google.com/workspace/calendar/api/v3/reference/events/list) defines recurrence expansion and cursor consistency.

Terraform now declares separate API/worker scheduling and match controls, validates that the API cannot be enabled without its worker, and orders worker updates first. Rollback disables API producers before draining consumer jobs and disabling the worker. The scoped `scripts/scheduling_prepare.py` operator command supports primary-calendar setup with production service flags still off. Six command tests cover preparation, cross-organization and inactive-membership/user denial, preservation of a different existing calendar choice, and suppression of appointment mutations/workflows. Projection-only preparation preserves the prior cursor so normal worker synchronization can still reconcile pending changes. Startup/help and sanitized missing-configuration behavior were also checked. The production workflow/match choices were recorded in the existing ignored `terraform.tfvars`.

Validation: both reported scheduling regressions failed before the fix; 119 focused checks and all 421 tests in affected scheduling, calendar, appointment, booking, and worker modules passed. Ruff and Terraform format/validate passed. Five isolated Terraform plan cases verified disabled, worker-only, and fully enabled states and denied API activation without its corresponding worker. Isolated execution `crm-migrate-5k4jn` then synchronized all six real calendars successfully (14,317 projected instances in total), with no calendar-event writes or historical link adoption. Release PR [794](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/794) passed all checks and merged as `83ec7910bd653c74e9f57bc3102a4f0aa86693b3`; tag `surrogacy-crm-platform-v0.91.81` was published at 13:53:58 UTC. Both production builds succeeded: API/worker `6fb43a0b-b65f-4c96-a3c7-441a2315ab60` at 14:02:09 UTC and web `4581dc64-8fbb-4776-9e33-fcf7d16faaf2` at 14:00:50 UTC.

## Scheduling V2 activation

Released operator execution `crm-migrate-qtlsw` refreshed all six primary calendars at 14:01:46–14:01:50 UTC without errors. Preparation changed projections only; it did not mutate appointments or fire workflows.

Worker `crm-worker-00307-dfk` activated first and scheduled six sync and six watch jobs at 14:03:31 UTC. During the brief revision overlap, retiring worker `crm-worker-00306-5tp` claimed three binding jobs and rejected their V2 payloads before provider access. Cloud Run marked that old revision retired at 14:03:44 UTC. Recovery execution `crm-migrate-4rtmq` replayed only those exact, tenant-scoped sync/watch jobs through the existing audited replay service. All three completed. At 14:13:30 UTC, all six calendars had fresh availability, writable destinations, and active watches; all 12 sync and six watch jobs in the verification window had completed, with no failed binding jobs.

API `crm-api-00262-spp` activated at 14:15:33 UTC after worker verification. API, worker, and web `crm-web-00237-ccw` each serve 100% of traffic. Health reports version `0.91.81`, matching database head, and healthy Redis. Workflow maintenance, approval expiry, and match expansion remain enabled. The ignored production Terraform variables record all activated controls.

Authenticated browser QA verified the active Google Meet booking type and the V2 Manage dialog: primary booking destination selected, conflict checking and event display enabled, recent binding sync, successful calendar discovery, Google Meet available, and no unsaved changes. No test booking, email, or invitation was sent. Historical legacy-linked appointments remain managed in Google as approved. The separate QA tab was closed; the user's active tab was preserved.

A bounded error query over the three active revisions from 14:15:34 to 14:18:00 UTC returned zero ERROR entries (limit 100). This is a short post-activation observation, not a long-term reliability claim. Existing local PostgreSQL was preserved; all task-created disposable test databases were removed, and no task-owned local server remains.

## Reported cancellation failure

Two cancellation requests returned HTTP 400 on API `crm-api-00260-24b` at 13:34:13 and 13:34:16 UTC. The UI mutation hook did not display failures. A regression using the real TanStack mutation and rejected API response reproduced the missing error; the fix displays the sanitized API detail and permits retry. All 34 focused appointment UI checks, both TypeScript checks, lint, and React Doctor (100/100) passed.

The user deleted the event in Google. Read-only diagnostic execution `crm-migrate-n4n6b` observed the exact tenant-scoped appointment as cancelled at 13:42:48 UTC, with `origin=google_import` and no verified calendar identity. No repair or provider write was needed. The diagnostic did not establish whether recurrence caused the original rejection. No client or event contents are included in this report.

## Booking-type preparation

The first conversion execution stopped before committing because one of the two active Zoom templates belongs to an inactive owner without a Google connection. Read-only execution `crm-migrate-ql95k` confirmed the other owner is active with a ready writable binding. Execution `crm-migrate-rsrkh` converted both templates at 13:53:47 UTC. The inactive owner remained inactive. No existing appointments or provider events changed; Scheduling V2 continues to deny bookings for inactive owners.

## Remaining prerequisites

Permission policy V2 still requires tenant-specific preview and review of changed access. Private tracing needs a collector endpoint and credentials. Gmail push needs Pub/Sub and webhook configuration. Meta CAPI needs account-specific conversion/provider readiness. These were not activated by a global flag change. Existing Next rendering/compiler experiments and legacy worker scaling remain disabled.

Display follow-up: the personal integration summary still uses its legacy user-level sync timestamp. The V2 Manage dialog shows the current binding sync timestamp.

Evidence: [final revisions and flags](release-0.91.81.json), [final calendar preparation](calendar-preparation-final.json), [worker readiness and recovery](scheduling-readiness-final.json), [aggregate inventory](activation-inventory.json), [calendar preparation](calendar-preparation.json), [0.91.80 revisions and flags](release-0.91.80.json), [initial audit](report.md).
