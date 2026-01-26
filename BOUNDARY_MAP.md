# Boundary Map — Surrogacy Force Platform

Purpose: clarify intended module boundaries and allowed dependencies to keep cohesion high and coupling low as the codebase scales.

## Current Intended Boundaries

### Backend layers
- Router/handler layer (`apps/api/app/routers/*`): owns request parsing, auth/CSRF dependencies, response shaping. Allowed deps: `app.core.*`, `app.schemas.*`, service layer. Must not own: business logic, direct DB writes, cross-domain orchestration.
- Service layer (`apps/api/app/services/*`): owns domain business rules and transactions. Allowed deps: `app.db.*`, `app.schemas.*`, `app.core.*`, integrations via adapters. Must not own: HTTP request/response details or FastAPI dependencies.
- Repository/DB layer (`apps/api/app/db/*`): owns models, enums, session, DB helpers. Allowed deps: SQLAlchemy, `app.db.types`. Must not depend on services or routers.
- Integrations/adapters (`app.services/*` for Gmail/Zoom/Meta/Resend/etc): owns external API calls + persistence of integration state. Allowed deps: config, HTTP clients, DB models. Must not orchestrate core domain flows beyond their integration.
- Jobs/worker (`apps/api/app/worker.py`, `apps/api/app/jobs/*`): owns background processing, retries, scheduled tasks. Allowed deps: services and adapters. Must not own HTTP routing logic.

### Frontend layers
- Pages/layouts (`apps/web/app/**`): owns route composition, view state, and calling domain hooks. Allowed deps: domain hooks, UI components, app context. Must not call API clients directly.
- Domain hooks (`apps/web/lib/hooks/**`): owns server-state fetching, mutations, cache invalidation. Allowed deps: API client + types. Must not own UI rendering or routing.
- API client (`apps/web/lib/api*`): owns HTTP calls, serialization, and error handling. Must not depend on UI or hooks.
- UI components (`apps/web/components/**`): owns rendering and local UI state. Must not call API clients or perform domain mutations directly.
- State stores (`apps/web/lib/store/**`): UI-only state; no server-state or domain rules.

### Domain modules (ownership + allowed dependencies)
- Auth & Identity: owns `auth_service`, `session_service`, `membership_service`, `routers/auth.py`, `routers/mfa.py`, `schemas/auth.py`, models `User/Membership/AuthIdentity/UserSession`. Allowed deps: core security/permissions, org lookup, audit. Must not own: domain entities (surrogates/matches/tasks).
- Organization & Settings: owns `org_service`, `routers/settings.py`, `routers/permissions.py`, `routers/invites.py`, models `Organization/OrgInvite/RolePermission`. Allowed deps: audit/compliance. Must not own: workflow or campaign execution logic.
- Surrogates: owns `surrogate_service`, `journey_service`, `profile_service`, `interview_service`, `routers/surrogates.py`, models `Surrogate/*StatusHistory/*ActivityLog`. Allowed deps: pipelines, queues, attachments, tasks (by ID), notifications (via facade). Must not own: email delivery, analytics aggregation, integrations.
- Imports & Custom Fields: owns `import_service`, `import_template_service`, `custom_field_service`, `routers/surrogates_import.py`, `routers/import_templates.py`, `routers/custom_fields.py`, models `SurrogateImport/ImportTemplate/CustomField/CustomFieldValue`. Allowed deps: surrogates via `surrogate_service`, audit, attachments. Must not own: direct surrogate status changes outside import approval flow.
- Intended Parents: owns `ip_service`, `routers/intended_parents.py`, models `IntendedParent/*StatusHistory`. Allowed deps: matching. Must not own: surrogate pipelines or tasks.
- Matching: owns `match_service`, `routers/matches.py`, models `Match/MatchEvent`. Allowed deps: surrogates + intended parents by ID. Must not own: workflow engine or email delivery.
- Tasks & Notes: owns `task_service`, `note_service`, `routers/tasks.py`, `routers/notes.py`, models `Task/EntityNote`. Allowed deps: notifications (via facade), surrogates/ips by ID. Must not own: pipeline or workflow execution logic.
- Pipelines & Status Changes: owns `pipeline_service`, `status_change_request_service`, `routers/pipelines.py`, `routers/status_change_requests.py`, models `Pipeline/PipelineStage/StatusChangeRequest`. Allowed deps: surrogates/ips by ID, audit/notification. Must not own: queue assignment or analytics.
- Forms & Submissions: owns `form_service`, `form_submission_service`, `routers/forms.py`, `routers/forms_public.py`, models `Form/FormSubmission/FormSubmissionFile/FormSubmissionToken`. Allowed deps: audit, attachments, surrogate updates via `surrogate_service`, notifications. Must not own: pipeline status transitions outside approved submission mapping.
- Workflows & Automation: owns `workflow_engine`, `workflow_triggers`, `workflow_service`, `routers/workflows.py`, `routers/templates.py`, `routers/campaigns.py`, models `AutomationWorkflow/*Execution/*Template/Campaign*`. Allowed deps: tasks/notifications/email via interfaces. Must not own: direct entity updates in other domains without going through their services.
- Communications & Email: owns `email_service`, `platform_email_service`, `gmail_service`, `invite_email_service`, `system_email_template_service`, models `EmailTemplate/EmailLog/EmailSuppression`. Allowed deps: org/user lookup, audit. Must not own: surrogate/task domain decisions.
- Appointments & Booking: owns `appointment_service`, `appointment_email_service`, `routers/appointments.py`, `routers/booking.py`, models `Appointment/*Availability*`. Allowed deps: integrations (Google/Zoom), notifications. Must not own: task or surrogate lifecycle rules.
- Integrations: owns `google_oauth.py`, `zoom_service.py`, `meta_*`, `routers/integrations.py`, `routers/webhooks.py`, models `UserIntegration/Meta*`. Allowed deps: http clients, config, audit. Must not own: core domain state transitions.
- AI: owns `ai_chat_service`, `ai_workflow_service`, `ai_interview_service`, `schedule_parser`, `routers/ai.py`, models `AI*`. Allowed deps: read-only access to domain data via services. Must not write domain entities directly.
- Analytics & Dashboard: owns `analytics_service`, `dashboard_service`, `routers/analytics.py`, `routers/dashboard.py`, models `AnalyticsSnapshot/RequestMetricsRollup`. Allowed deps: read-only queries to domain models. Must not mutate domain state.
- Compliance & Audit: owns `audit_service`, `compliance_service`, `pii_anonymizer`, `routers/audit.py`, `routers/compliance.py`, models `AuditLog/EntityVersion/DataRetentionPolicy/LegalHold`. Allowed deps: all domains for logging. Must not own: business rules.
- Platform/Ops: owns `platform_service`, `routers/platform.py`, `routers/ops.py`, models `AdminActionLog/OrganizationSubscription/SystemAlert`. Allowed deps: org/auth/email/compliance. Must not own: surrogate/task domain rules.
- Files & Attachments: owns `attachment_service`, `media_service`, `routers/attachments.py`, models `Attachment/*File`. Allowed deps: storage clients, scanning jobs. Must not own: domain workflows.
- Queues: owns `queue_service`, `routers/queues.py`, models `Queue`. Allowed deps: surrogates/tasks by ID, activity logging. Must not own: notifications or workflows directly.
- Jobs/Background: owns `worker.py`, `jobs/*`. Allowed deps: services/adapters. Must not own: router-level behaviors.
