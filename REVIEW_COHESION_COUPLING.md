# Cohesion/Coupling Review — Surrogacy Force Platform

## Executive Summary
- Core domain logic is concentrated in a small set of “god” services/routers (surrogate, analytics, workflow, AI, worker), creating high blast radius for routine changes.
- Cross‑domain service calls are pervasive (notifications, workflows, queues, meta, email), and `app.services` re‑exports hide true coupling in static analysis.
- Router‑level model imports have been removed and guarded by tests, but a few routers still orchestrate heavy cross‑domain flows (integrations/platform).
- Several frontend pages are monoliths that orchestrate many domains (surrogate detail, ops org page, tasks), increasing regression risk and merge conflicts.
- Notification/email/webhook interfaces now exist (facade/adapter/registry), reducing direct coupling, but large service files still hide cross‑domain effects.

## Current Intended Boundaries

### Backend layers
- Router/handler layer (`apps/api/app/routers/*`): request parsing, auth/CSRF dependencies, response shaping. Allowed deps: `app.core.*`, `app.schemas.*`, services. Must not own business logic or DB writes.
- Service layer (`apps/api/app/services/*`): domain rules, transactions, orchestration inside a domain. Allowed deps: `app.db.*`, `app.schemas.*`, `app.core.*`, integration adapters. Must not own HTTP concerns.
- Repository/DB layer (`apps/api/app/db/*`): models, enums package, session, DB helpers. Must not depend on services/routers.
- Integrations/adapters (`app.services/*` for Gmail/Zoom/Meta/Resend/etc): external API calls + persisted integration state. Must not orchestrate core domain rules.
- Jobs/worker (`apps/api/app/worker.py`, `apps/api/app/jobs/*`): background processing that calls services/adapters. Must not include routing logic.

### Frontend layers
- Pages/layouts (`apps/web/app/**`): route composition and view state; call domain hooks. Must not call API clients directly.
- Domain hooks (`apps/web/lib/hooks/**`): server‑state + mutations + cache invalidation. Must not render UI.
- API client (`apps/web/lib/api*`): HTTP calls + serialization. Must not depend on UI.
- UI components (`apps/web/components/**`): rendering and local UI state only. Must not trigger domain mutations directly.
- State stores (`apps/web/lib/store/**`): UI‑only state.

### Domain modules (ownership + allowed dependencies)
- Auth & Identity: owns auth/session/membership services, auth routers, auth schemas, models `User/Membership/AuthIdentity`. Allowed deps: core security, org lookup, audit. Must not own domain entities.
- Organization & Settings: owns org/invite/permissions services + routers, models `Organization/OrgInvite/RolePermission`. Allowed deps: audit/compliance. Must not own workflow/campaign execution.
- Surrogates: owns surrogate/journey/profile/interview services + routers, models `Surrogate/*StatusHistory/*ActivityLog`. Allowed deps: pipelines, queues, attachments, tasks by ID, notifications via facade. Must not own email delivery/integrations.
- Intended Parents: owns IP services + routers, models `IntendedParent/*StatusHistory`. Allowed deps: matching. Must not own surrogate pipeline rules.
- Matching: owns match services + routers, models `Match/MatchEvent`. Allowed deps: surrogates + IPs by ID. Must not own workflow execution.
- Tasks & Notes: owns task/note services + routers, models `Task/EntityNote`. Allowed deps: notifications via facade, surrogate/IP IDs. Must not own pipeline/workflow rules.
- Pipelines & Status Changes: owns pipeline/stage + status‑change services, routers, models `Pipeline/PipelineStage/StatusChangeRequest`. Allowed deps: surrogates/IPs by ID. Must not own queue assignment.
- Workflows & Automation: owns workflow engine/triggers, templates/campaigns, models `AutomationWorkflow/*`. Allowed deps: tasks/notifications/email via interfaces. Must not directly mutate other domains without their service.
- Communications & Email: owns email senders/templates/logs, models `EmailTemplate/EmailLog/EmailSuppression`. Allowed deps: org/user lookup, audit. Must not decide domain behavior.
- Appointments & Booking: owns appointment services + routers, models `Appointment/*Availability*`. Allowed deps: integrations, notifications. Must not own task/surrogate lifecycle rules.
- Integrations: owns OAuth/Zoom/Meta adapters + webhooks. Allowed deps: config/HTTP/audit. Must not own core domain state transitions.
- AI: owns AI services/routers/models. Allowed deps: read‑only domain access through services. Must not write domain entities directly.
- Analytics & Dashboard: owns analytics/dashboard services + routers. Allowed deps: read‑only queries. Must not mutate domain state.
- Compliance & Audit: owns audit/compliance services + routers. Allowed deps: all domains for logging. Must not own business rules.
- Platform/Ops: owns platform services + routers. Allowed deps: org/auth/email/compliance. Must not own core domain rules.
- Files & Attachments: owns attachment/media services + routers. Allowed deps: storage/scan jobs. Must not own workflows.
- Queues: owns queue service + routers. Allowed deps: surrogates/tasks by ID, activity logging. Must not own notification/workflow rules.

## Audit Methodology
- Static dependency inspection: repo‑wide import scans for `apps/api/app` and `apps/web` plus file size hotspots; inbound/outbound dependencies inferred from import graph.
- Change‑flow inspection: traced 3 end‑to‑end stories (A/B/C below), enumerating backend + frontend touchpoints.
- Note on coverage: I did not read every line in the repository (the codebase is too large to do so reliably). I scanned all files for imports/structure and deep‑read the hotspot and flow‑related modules listed in this report.
- Limitation: `from app.services import X` re‑exports reduce the accuracy of inbound counts in static analysis; coupling is likely under‑reported for services.

## Change‑Flow Inspection

### Flow A — Update surrogate stage + log it + update dashboard
Files touched (frontend):
- `apps/web/app/(app)/surrogates/[id]/page.tsx`
- `apps/web/components/surrogates/ChangeStageModal.tsx`
- `apps/web/lib/hooks/use-surrogates.ts`
- `apps/web/lib/api/surrogates.ts`
- `apps/web/lib/hooks/use-dashboard-socket.ts`
- `apps/web/app/(app)/dashboard/page.tsx`

Files touched (backend):
- `apps/api/app/routers/surrogates.py` (PATCH `/{id}/status` + dashboard push)
- `apps/api/app/services/surrogate_service.py` (`change_status`, `_apply_status_change`)
- `apps/api/app/services/status_change_request_service.py` (regression approval)
- `apps/api/app/services/notification_service.py` (status + queue notifications)
- `apps/api/app/services/queue_service.py` (pool assignment)
- `apps/api/app/services/workflow_triggers.py` (workflow trigger)
- `apps/api/app/services/job_service.py` + `services/meta_capi.py` (Meta CAPI)
- `apps/api/app/services/dashboard_service.py` + `core/websocket.py` (stats push)
- `apps/api/app/routers/websocket.py`
- `apps/api/app/db/models/*`, `apps/api/app/db/enums/*`

Coupling notes:
- `surrogate_service.change_status` orchestrates queues, notifications, workflows, and Meta CAPI — cross‑domain effects are embedded in the core domain method.
- Router directly triggers dashboard stats push, mixing domain action with UI update concerns.

### Flow B — Send org invite / system email
Files touched (frontend):
- `apps/web/app/(app)/settings/team/page.tsx`
- `apps/web/lib/hooks/use-invites.ts`
- `apps/web/lib/api/invites.ts`
- `apps/web/app/invite/[id]/page.tsx` (accept view)
- `apps/web/app/ops/agencies/[orgId]/page.tsx` + `apps/web/lib/api/platform.ts` (platform invites)

Files touched (backend):
- `apps/api/app/routers/invites.py` (create/resend/revoke)
- `apps/api/app/services/invite_service.py` (invite lifecycle)
- `apps/api/app/services/invite_email_service.py` (template + send)
- `apps/api/app/services/system_email_template_service.py`
- `apps/api/app/services/platform_email_service.py` / `services/gmail_service.py`
- `apps/api/app/services/email_service.py` (template render)
- `apps/api/app/services/org_service.py` (portal URL)
- `apps/api/app/services/oauth_service.py` (Gmail integration check)
- `apps/api/app/services/audit_service.py` + `services/alert_service.py`
- `apps/api/app/db/models/*`

Coupling notes:
- Router validates integration availability and domain constraints; invite email service depends on multiple services (org, template, email providers, audit, alert), making invites a cross‑domain orchestration point.

### Flow C — Create/assign task + show in UI + notify
Files touched (frontend):
- `apps/web/app/(app)/tasks/page.tsx`
- `apps/web/components/tasks/AddTaskDialog.tsx`
- `apps/web/components/tasks/TaskEditModal.tsx`
- `apps/web/components/appointments/UnifiedCalendar.tsx`
- `apps/web/lib/hooks/use-tasks.ts`
- `apps/web/lib/api/tasks.ts`

Files touched (backend):
- `apps/api/app/routers/tasks.py`
- `apps/api/app/services/task_service.py`
- `apps/api/app/services/notification_service.py`
- `apps/api/app/services/dashboard_service.py`
- `apps/api/app/services/ip_service.py` (intended parent validation)
- `apps/api/app/core/surrogate_access.py`
- `apps/api/app/db/models/*`

Coupling notes:
- Task creation triggers notifications and dashboard stats; router directly couples task mutations to dashboard updates.
- Frontend task hooks invalidate surrogate stats, tying tasks to surrogate analytics.

## Top 20 Coupling Hotspots

| Module / File | Why hotspot | Inbound dependencies | Outbound dependencies | Cohesion grade | Coupling grade | Risk if left as‑is | Best next refactor |
|---|---|---|---|---|---|---|---|
| `apps/api/app/db/models/*` | Models are split by domain, but `db/models/__init__.py` re‑exports keep global imports common | Most routers/services/jobs (≈94) | `db/enums/*`, `db/types.py` | B (domain grouping) | D (global re‑export) | Global imports still blur boundaries | Prefer per‑domain imports (`app.db.models.<domain>`) and limit `app.db.models` to bootstrapping |
| `apps/api/app/db/enums/*` | Split enum registry by domain (re-exported) | Most modules (≈94) | None | B (domain grouping) | D (still widely imported) | Enum churn still has broad impact | Continue reducing cross-domain enum usage |
| `apps/api/app/core/deps.py` | Central auth/permission deps used everywhere | All routers (≈50) | `core/*`, `db/*` | B (auth/permission only) | C (system‑wide usage) | Auth change risks wide regression | Split into auth/permission/platform deps modules |
| `apps/api/app/services/surrogate_service.py` | 1.6k LOC; status, assignment, meta, workflows | Routers, status_change_request_service, matches, forms, dashboard | Pipeline, queue, notifications, workflow_triggers, job_service | D (god service) | D | Status change affects queues/workflows/notifications | Extract status + assignment submodules and add event dispatch |
| `apps/api/app/services/analytics_service.py` | Split into `analytics_surrogate_service`, `analytics_meta_service`, `analytics_usage_service` + shared helpers | `routers/analytics.py`, worker, exports, AI | Pipeline, meta_api, models | B (facade only) | C | Analytics change breaks exports/AI | ✅ Completed: domain split + facade |
| `apps/api/app/services/workflow_engine.py` | Orchestrates workflow actions across domains | `routers/workflows.py`, worker | Models, schemas, action preview | C (engine + domain actions) | D | Workflow edits impact tasks/approvals | ✅ Completed: core engine + domain adapters (2026-01-29) |
| `apps/api/app/services/notification_service.py` | Settings + dispatch + event types in one file | Many services (surrogate/task/queue/etc.) | Models, websocket | C (mixed concerns) | D | Notification change breaks multiple flows | Split settings vs dispatch; add `notification_events` facade |
| `apps/api/app/services/task_service.py` | Task CRUD + notification + workflow approvals | `routers/tasks.py`, workflow engine | Models, notifications, queue | C (CRUD + side‑effects) | C | Task changes ripple to notifications | Move notification dispatch to task events module |
| `apps/api/app/services/form_service.py` | Builder + submissions + auto‑mapping | `routers/forms*.py`, workflows | Surrogate, audit, notification, attachments | D (builder + ingestion) | D | Form changes can mutate surrogates incorrectly | Split builder vs submission pipeline |
| `apps/api/app/services/appointment_service.py` | Scheduling + integrations in one file | `routers/appointments.py`, booking | Integrations, models, async utils | C (core + integrations) | C/D | Integration changes regress scheduling | Extract `appointment_integrations` module |
| `apps/api/app/services/platform_service.py` | Platform admin operations across orgs | `routers/platform.py`, internal | Org, security, models | C (multi‑concern admin) | C | Cross‑org changes risk isolation | Split by concern (orgs/invites/billing) |
| `apps/api/app/worker.py` | 1.7k LOC job switchboard | Scheduled triggers/internal | Many services + integrations | D (multi‑domain handlers) | D | Adding jobs risks regressions | ✅ Completed: per-domain job handlers + registry (2026-01-29) |
| `apps/api/app/routers/surrogates.py` | 1.4k LOC router; direct model use + side‑effects | main app | Surrogate services + models + dashboard | C (many endpoints + logic) | C/D | Endpoint changes ripple across domain | Split into sub‑routers; move model access to services |
| `apps/api/app/routers/ai.py` | 2.1k LOC router; heavy orchestration | main app | AI services + models + rate limits | D (router + logic) | D | AI changes impact tasks/workflows | Split into smaller routers + move logic to services |
| `apps/api/app/routers/integrations.py` | Multi‑provider flows in one file | main app | OAuth/Gmail/Zoom/Meta services | C (multiple integrations) | C/D | Integration changes affect all providers | Split routers per integration |
| `apps/api/app/routers/webhooks.py` | Multi‑provider webhook handler with direct DB | main app | Models + services + rate limits | D (multi‑provider + DB) | D | Webhook change breaks campaigns/Zoom/Email | Create per‑integration handlers + adapter interface |
| `apps/web/app/(app)/surrogates/[id]/page.tsx` | 1.8k LOC page orchestrating many domains | Route only | 40+ imports (tasks, AI, queues, notes, meetings) | D (god page) | D | Any domain tweak breaks page | Split into tab‑level containers + data hooks |
| `apps/web/app/(app)/tasks/page.tsx` | List + calendar + approvals in one file | Route only | Tasks hooks + approvals + calendar | C/D | C | Changes affect approvals/calendar | Extract list and calendar containers |
| `apps/web/app/ops/agencies/[orgId]/page.tsx` | Ops console + invites + templates in one file | Route only | Platform API + templates + UI | D | C/D | Ops changes have large UI blast radius | Split into tab components per concern |
| `apps/web/components/appointments/UnifiedCalendar.tsx` | Cross‑domain calendar with data fetching | Tasks page + surrogate calendar | Tasks, appointments, surrogates, IP hooks | C (UI + data) | C/D | Changes in tasks/appointments ripple | Move data fetch to `useUnifiedCalendarData` |

## Boundary Violations & Leaks

Remaining (as of 2026-01-30):
- `apps/web/app/(app)/surrogates/[id]/page.tsx` → mixes AI, tasks, notes, meetings, queues logic. Correct direction: page composes domain sub‑containers. Status: partially split (2026-01-28), still large.
- `apps/web/app/(app)/tasks/page.tsx` → list + calendar + approvals in one file. Correct direction: extract list and calendar containers.
- `apps/web/app/ops/agencies/[orgId]/page.tsx` → ops console mixes org/invites/templates. Correct direction: split tab‑level containers.

Resolved:
- Router model imports moved into services (journey/forms/profile/matches/webhooks/platform/websocket/admin_meta/internal + settings/attachments/zapier/meta_oauth/surrogates_read/ai_tasks/meta_forms). Guarded by `tests/test_router_model_imports.py`. Status: completed (2026-01-30).
- `apps/api/app/services/status_change_request_service.py` → private status helpers → public status services. Status: completed (2026-01-28).
- `apps/api/app/services/task_service.py` → notification formatting moved to `task_events`. Status: completed (2026-01-28).
- `apps/api/app/services/surrogate_service.py` → side-effects moved to `surrogate_events`. Status: completed (2026-01-29).
- `apps/web/components/appointments/UnifiedCalendar.tsx` → data fetching moved to `useUnifiedCalendarData()`. Status: completed (2026-01-28).

## Refactor Candidates (grouped)

### Extract module
- **R1 — Surrogate status module**
  Files to change: `apps/api/app/services/surrogate_service.py`, `apps/api/app/services/status_change_request_service.py`, `apps/api/app/routers/surrogates.py`.
  Create/Delete: create `apps/api/app/services/surrogate_status_service.py`; no deletes.
  Expected blast radius: medium (status change + approvals).
  Test plan: unit tests for status change rules; integration tests for `/surrogates/{id}/status` and approval flow.
  Status: completed (2026-01-28).
  Notes: moved change-status orchestration into `surrogate_status_service` and added service-level tests.

- **R2 — Form submission pipeline**
  Files to change: `apps/api/app/services/form_service.py`, `apps/api/app/routers/forms.py`, `apps/api/app/routers/forms_public.py`.
  Create/Delete: create `apps/api/app/services/form_submission_service.py`.
  Expected blast radius: medium (forms submit + auto‑map).
  Test plan: integration tests for form submission + mapping; regression on attachments.
  Status: completed (2026-01-28).
  Notes: moved submission/token/review/file logic into `form_submission_service` and added service-level tests.

- **R3 — Appointment integrations**
  Files to change: `apps/api/app/services/appointment_service.py`, `apps/api/app/services/appointment_email_service.py`.
  Create/Delete: create `apps/api/app/services/appointment_integrations.py`.
  Expected blast radius: medium (calendar + Zoom/GCal sync).
  Test plan: unit tests for integration adapters; integration tests for appointment create/update.
  Status: completed (Week 3).

- **R4 — Task notification events**
  Files to change: `apps/api/app/services/task_service.py`, `apps/api/app/services/notification_service.py`.
  Create/Delete: create `apps/api/app/services/task_events.py`.
  Expected blast radius: low‑medium (task assignment notifications).
  Test plan: unit tests for notification payloads; integration test for task assignment flow.
  Status: completed (2026-01-28).
  Notes: added `task_events` and switched task_service callers.

### Introduce boundary / interface
- **R5 — Notification dispatch facade**
  Files to change: services calling `notification_service` directly (e.g., `surrogate_service.py`, `task_service.py`, `status_change_request_service.py`).
  Create/Delete: create `apps/api/app/services/notification_facade.py` and event helpers; no deletes.
  Expected blast radius: medium (central notifications).
  Test plan: unit tests per event; smoke tests for websocket and in‑app notifications.
  Status: completed (2026-01-28).
  Notes: introduced `notification_facade` and switched service-layer callers to use it.

- **R6 — Email sender interface**
  Files to change: `invite_email_service.py`, `email_service.py`, `platform_email_service.py`, `gmail_service.py`.
  Create/Delete: create `apps/api/app/services/email_sender.py` interface + concrete adapters.
  Expected blast radius: medium (invites + system emails).
  Test plan: integration tests for invite email path + Resend/Gmail fallback.
  Status: completed (2026-01-28).
  Notes: introduced `email_sender` selection helper and sender adapters for platform/Gmail.

- **R7 — Webhook handler registry**
  Files to change: `apps/api/app/routers/webhooks.py`, provider services (`zoom_service.py`, `campaign_service.py`, `email_service.py`).
  Create/Delete: create `apps/api/app/services/webhooks/` registry + handlers.
  Expected blast radius: medium (webhook flows).
  Test plan: integration tests for each webhook payload fixture.
  Status: completed (Week 3).

### Move code to correct layer
- **R8 — Remove direct model use in routers**
  Files to change: `apps/api/app/routers/journey.py`, `forms.py`, `matches.py`, `profile.py`, `webhooks.py`, `platform.py`, `websocket.py`.
  Create/Delete: create small service methods or repositories for each query; no deletes.
  Expected blast radius: low‑medium (endpoint refactors).
  Test plan: endpoint integration tests for each affected router.
  Status: completed (2026-01-28).
  Notes: extended cleanup to `admin_meta.py` + `internal.py` by introducing `meta_admin_service`.

- **R9 — Dashboard stats push via service/event**
  Files to change: `apps/api/app/routers/surrogates.py`, `apps/api/app/routers/tasks.py`, `apps/api/app/services/dashboard_service.py`.
  Create/Delete: create `apps/api/app/services/dashboard_events.py` and call from services instead of routers.
  Expected blast radius: low (dashboard updates).
  Test plan: integration tests for status change and task create; verify websocket `stats_update`.
  Status: completed (2026-01-28).

### Delete/merge duplicates
- **R10 — Calendar data adapter consolidation**
  Files to change: `apps/web/components/appointments/UnifiedCalendar.tsx`, `apps/web/components/surrogates/SurrogateTasksCalendar.tsx`.
  Create/Delete: create `apps/web/lib/hooks/use-unified-calendar-data.ts`; remove duplicated mapping logic.
  Expected blast radius: low (calendar rendering only).
  Test plan: frontend integration tests for tasks + appointments rendering.

- **R11 — Consolidate invite template rendering**
  Files to change: `apps/api/app/services/invite_email_service.py`, `apps/api/app/services/system_email_template_service.py`.
  Create/Delete: move fallback HTML into system template defaults; remove duplicate HTML builder.
  Expected blast radius: low (invite email only).
  Test plan: unit test for template rendering; smoke test for invite send.
  Status: completed (2026-01-29).

## Prioritized Plan

### Week 1 (safe refactors)
- [x] R4 — Task notification events (low‑medium blast radius, improves separation).
- [x] R8 — Remove direct model use in routers (start with journey/profile/forms).
- [x] R10 — Calendar data adapter consolidation.
- [x] R9 — Dashboard stats push via service/event.

### Weeks 2–3 (structural)
- [x] R1 — Surrogate status module.
- [x] R2 — Form submission pipeline split.
- [x] R5 — Notification dispatch facade.
- [x] R6 — Email sender interface.

### Later (optional)
- [x] R3 — Appointment integrations module.
- [x] R7 — Webhook handler registry.
- [x] Split `db/models.py` into domain modules (re‑exported via `db/models/__init__.py`).

## Progress Log
- 2026-01-28: Split `routers/surrogates.py` into sub-routers; list/create routes stay on the aggregator to preserve `/surrogates`.
- 2026-01-28: Split `surrogates/[id]/page.tsx` by extracting the header, history tab, and AI tab components.
- 2026-01-29: Consolidated org invite fallback HTML into system template defaults (R11).
- 2026-01-29: Split `routers/ai.py` into sub-routers for settings, chat, actions, usage, workflows, schedule parsing, and bulk tasks.
- 2026-01-29: Split workflow engine into core (`workflow_engine_core`) and domain adapter (`workflow_engine_adapters`) modules.
- 2026-01-29: Split worker jobs into per-domain handlers with a central registry.
- 2026-01-29: Added surrogate status side-effects event bus (`surrogate_events`) and moved notifications/queues/workflows/Meta CAPI hooks into it.
- 2026-01-30: Removed remaining router model imports (settings/attachments/zapier/meta_oauth/surrogates_read/ai_tasks/meta_forms/internal) and added `tests/test_router_model_imports.py` guard.
