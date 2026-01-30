# CODEMAP

## System Architecture Overview
- Frontend: Next.js 16 App Router in `apps/web` (SSR + client components, TanStack Query, Zustand)
- Backend: FastAPI app in `apps/api/app/main.py` with thin routers and service layer
- Background jobs: polling worker in `apps/api/app/worker.py` processing `Job` rows; scheduled triggers via `/internal/scheduled/*`
- Database: PostgreSQL with SQLAlchemy models in `apps/api/app/db/models/*` (re-exported in `apps/api/app/db/models/__init__.py`), migrations in `apps/api/alembic/versions` (archive in `apps/api/alembic/versions_archive`)
- Storage: attachments via `apps/api/app/services/attachment_service.py` and `apps/api/app/services/media_service.py`, optional ClamAV scanning in `apps/api/app/jobs/scan_attachment.py`

### Request Flow (HTTP)
Browser -> Next.js route -> `apps/web/lib/api.ts` or `apps/web/lib/api/*` -> FastAPI middleware -> router -> service -> DB -> jobs/external APIs

### Auth + Security Flow
- Cookie sessions + CSRF: `apps/api/app/core/csrf.py`, middleware in `apps/api/app/main.py`, client headers in `apps/web/lib/csrf.ts`
- Cookie domain sharing: `COOKIE_DOMAIN` setting for cross-subdomain auth (app/ops)
- RBAC + policies: `apps/api/app/core/permissions.py`, `apps/api/app/core/policies.py`, `apps/api/app/services/permission_service.py`
- Platform admin access: `require_platform_admin` in `apps/api/app/core/deps.py` (DB flag + email allowlist)
- Owner-based surrogate access: `apps/api/app/core/surrogate_access.py`
- Encryption: `apps/api/app/core/encryption.py`, `apps/api/app/db/types.py`
- Audit logging: `apps/api/app/services/audit_service.py`, `apps/api/app/services/platform_service.py` (admin actions)

---

## Repo Map
- Root docs and audits: `README.md`, `CHANGELOG.md`, `REVIEW.md`, `LAUNCH_READINESS.md`, `ENTERPRISE_GAPS.md`, `CLAUDE.md`, `code_reviews.md`, `database_optimization.md`, `deployment.md`, `terraform.md`
- CI/CD: `.github/workflows/*`, `cloudbuild/*`
- Infra: `docker-compose.yml`, `infra/terraform/*`, `release-please-config.json`, `zap-baseline.conf`, `zap-baseline-report.html`, `zap.yaml`
- Scripts/tests: `scripts/`, `load-tests/`
- Backend: `apps/api`
- Frontend: `apps/web`
- Docs: `docs/`

---

## Backend Map (`apps/api`)
- App entry: `apps/api/app/main.py`
- Worker: `apps/api/app/worker.py`
- CLI: `apps/api/app/cli.py`
- Core utilities: `apps/api/app/core/*` (20 files: config, deps, csrf, rate limits, permissions, policies, logging, stage rules, async_utils, redis, telemetry, websocket, encryption, security, etc.)
- DB: `apps/api/app/db/*` (models package with 22 files, enums package with 17 files, session, types, base)
- Utils: `apps/api/app/utils/*` (normalization, pagination, datetime_parsing, business_hours)
- Routers: `apps/api/app/routers/*` (75 router files - see API Index)
- Services: `apps/api/app/services/*` (100+ service files - see Services Index)
- Service events: `apps/api/app/services/dashboard_events.py`, `apps/api/app/services/task_events.py`, `apps/api/app/services/surrogate_events.py`
- Email providers: `apps/api/app/services/email_provider_service.py`, `apps/api/app/services/resend_email_service.py`, `apps/api/app/services/email_sender.py`
- Webhook handlers: `apps/api/app/services/webhooks/*` (base, registry, meta, zoom, resend, zapier)
- Appointment integrations: `apps/api/app/services/appointment_integrations.py`
- Surrogate status helper: `apps/api/app/services/surrogate_status_service.py`
- CSV import pipeline: `apps/api/app/services/import_service.py`, `apps/api/app/routers/surrogates_import.py`
- Import templates: `apps/api/app/services/import_template_service.py`, `apps/api/app/routers/import_templates.py`
- Custom fields: `apps/api/app/services/custom_field_service.py`, `apps/api/app/routers/custom_fields.py`
- Schemas: `apps/api/app/schemas/*` (22 Pydantic schema files)
- Jobs: `apps/api/app/jobs/*` (registry, utils, scan_attachment, handlers/)
- Job handlers: `apps/api/app/jobs/handlers/*` (15 handler files)
- Migrations: `apps/api/alembic/*`
- Tests: `apps/api/tests/*`

---

## Frontend Map (`apps/web`)
- App entry: `apps/web/app/layout.tsx`
- Authenticated layout: `apps/web/app/(app)/layout.tsx`
- Public routes: `apps/web/app/login/page.tsx`, `apps/web/app/mfa/page.tsx`, `apps/web/app/invite/[id]/page.tsx`, `apps/web/app/apply/[token]/page.tsx`, `apps/web/app/book/*`, `apps/web/app/auth/*`, `apps/web/app/org-not-found/page.tsx`
- Print routes: `apps/web/app/(print)/*`
- Core pages: `apps/web/app/(app)/dashboard/page.tsx`, `apps/web/app/(app)/surrogates/page.tsx`, `apps/web/app/(app)/surrogates/[id]/page.tsx`, `apps/web/app/(app)/intended-parents/page.tsx`, `apps/web/app/(app)/matches/page.tsx`, `apps/web/app/(app)/tasks/page.tsx`, `apps/web/app/(app)/ai-assistant/page.tsx`, `apps/web/app/(app)/reports/page.tsx`, `apps/web/app/(app)/automation/page.tsx`, `apps/web/app/(app)/settings/*`, `apps/web/app/(app)/search/page.tsx`, `apps/web/app/(app)/welcome/page.tsx`
- Ops Console (platform admin): `apps/web/app/ops/layout.tsx`, `apps/web/app/ops/page.tsx`, `apps/web/app/ops/login/page.tsx`, `apps/web/app/ops/agencies/*`, `apps/web/app/ops/alerts/page.tsx`
- Dashboard widgets: `apps/web/app/(app)/dashboard/components/*` (KPI cards, trend chart, stage chart, attention panel)
- Dashboard state: `apps/web/app/(app)/dashboard/context/dashboard-filters.tsx`
- Components: `apps/web/components/*` (35 directories: surrogates, interviews, matches, tasks, appointments, AI, reports, ui, ops, import, etc.)
- Surrogate tabs: `apps/web/components/surrogates/tabs/*`
- API + hooks: `apps/web/lib/api.ts`, `apps/web/lib/api/*` (40 API files), `apps/web/lib/hooks/*` (44 hook files)
- Context/state: `apps/web/lib/auth-context.tsx`, `apps/web/lib/context/ai-context.tsx`, `apps/web/lib/store/*`
- UI utilities: `apps/web/lib/utils/task-due.ts`, `apps/web/lib/utils/task-recurrence.ts`, `apps/web/lib/utils/date.ts`
- Routing: `apps/web/next.config.js` rewrites (host-based routing for ops subdomain)
- Tests: `apps/web/tests/*`

---

## Feature -> Module Mapping
- Authentication + MFA: UI in `apps/web/app/login/page.tsx`, `apps/web/app/mfa/page.tsx`; API in `apps/api/app/routers/auth.py`, `apps/api/app/routers/mfa.py`; services in `apps/api/app/services/auth_service.py`, `apps/api/app/services/session_service.py`, `apps/api/app/services/mfa_service.py`, `apps/api/app/services/duo_service.py`
- Surrogates (Surrogacy Force): UI in `apps/web/app/(app)/surrogates/page.tsx`, `apps/web/app/(app)/surrogates/[id]/page.tsx`; API in `apps/api/app/routers/surrogates.py`, `apps/api/app/routers/surrogates_read.py`, `apps/api/app/routers/surrogates_write.py`, `apps/api/app/routers/surrogates_status.py`, `apps/api/app/routers/surrogates_shared.py`; services in `apps/api/app/services/surrogate_service.py`, `apps/api/app/services/surrogate_status_service.py`, `apps/api/app/services/surrogate_events.py`
- Journey timeline: UI in `apps/web/components/surrogates/journey/*`; API in `apps/api/app/routers/journey.py`; service in `apps/api/app/services/journey_service.py`
- Surrogate profile: UI in `apps/web/components/surrogates/SurrogateProfileCard.tsx`; API in `apps/api/app/routers/profile.py`; service in `apps/api/app/services/profile_service.py`
- Intended parents: UI in `apps/web/app/(app)/intended-parents/page.tsx`; API in `apps/api/app/routers/intended_parents.py`; services in `apps/api/app/services/ip_service.py`, `apps/api/app/services/intended_parent_status_service.py`
- Matches: UI in `apps/web/app/(app)/matches/page.tsx` and `apps/web/app/(app)/intended-parents/matches/*`; API in `apps/api/app/routers/matches.py`; service in `apps/api/app/services/match_service.py`
- Status change requests: UI in `apps/web/components/status-change-requests/*`; API in `apps/api/app/routers/status_change_requests.py`; service in `apps/api/app/services/status_change_request_service.py`
- Tasks: UI in `apps/web/app/(app)/tasks/page.tsx`, `apps/web/components/tasks/*`; API in `apps/api/app/routers/tasks.py`; services in `apps/api/app/services/task_service.py`, `apps/api/app/services/task_events.py`
- Interviews: UI in `apps/web/components/surrogates/interviews/*`; API in `apps/api/app/routers/interviews.py`; services in `apps/api/app/services/interview_service.py`, `apps/api/app/services/interview_note_service.py`, `apps/api/app/services/interview_attachment_service.py`
- Appointments/booking: UI in `apps/web/app/(app)/appointments/page.tsx`, `apps/web/app/book/*`, `apps/web/components/appointments/*`; API in `apps/api/app/routers/appointments.py`, `apps/api/app/routers/booking.py`; services in `apps/api/app/services/appointment_service.py`, `apps/api/app/services/appointment_integrations.py`, `apps/api/app/services/appointment_email_service.py`
- Forms: UI in `apps/web/app/(app)/automation/forms/*`, public in `apps/web/app/apply/[token]/page.tsx`; API in `apps/api/app/routers/forms.py`, `apps/api/app/routers/forms_public.py`, `apps/api/app/routers/meta_forms.py`; services in `apps/api/app/services/form_service.py`, `apps/api/app/services/form_submission_service.py`
- CSV imports + templates: UI in `apps/web/app/(app)/surrogates/import/page.tsx`, `apps/web/components/import/*`; API in `apps/api/app/routers/surrogates_import.py`, `apps/api/app/routers/import_templates.py`, `apps/api/app/routers/custom_fields.py`; services in `apps/api/app/services/import_service.py`, `apps/api/app/services/import_template_service.py`, `apps/api/app/services/custom_field_service.py`, `apps/api/app/services/import_detection_service.py`, `apps/api/app/services/import_ai_mapper_service.py`, `apps/api/app/services/import_transformers.py`
- Automation/workflows: UI in `apps/web/app/(app)/automation/*`; API in `apps/api/app/routers/workflows.py`, `apps/api/app/routers/templates.py`; services in `apps/api/app/services/workflow_engine.py`, `apps/api/app/services/workflow_triggers.py`, `apps/api/app/services/workflow_action_preview.py`, `apps/api/app/services/workflow_access.py`, `apps/api/app/services/workflow_service.py`, `apps/api/app/services/workflow_email_provider.py`
- Campaigns + email templates: UI in `apps/web/app/(app)/automation/campaigns/*`, `apps/web/app/(app)/automation/email-templates/page.tsx`; API in `apps/api/app/routers/campaigns.py`, `apps/api/app/routers/email_templates.py`; services in `apps/api/app/services/campaign_service.py`, `apps/api/app/services/email_service.py`, `apps/api/app/services/template_service.py`, `apps/api/app/services/system_email_template_service.py`
- AI assistant: UI in `apps/web/app/(app)/ai-assistant/page.tsx`, `apps/web/components/ai/*`; API in `apps/api/app/routers/ai.py`, `apps/api/app/routers/ai_chat.py`, `apps/api/app/routers/ai_actions.py`, `apps/api/app/routers/ai_tasks.py`, `apps/api/app/routers/ai_workflows.py`, `apps/api/app/routers/ai_conversations.py`, `apps/api/app/routers/ai_settings.py`, `apps/api/app/routers/ai_focus.py`, `apps/api/app/routers/ai_schedule.py`, `apps/api/app/routers/ai_consent.py`, `apps/api/app/routers/ai_usage.py`; services in `apps/api/app/services/ai_service.py`, `apps/api/app/services/ai_chat_service.py`, `apps/api/app/services/ai_workflow_service.py`, `apps/api/app/services/ai_interview_service.py`, `apps/api/app/services/ai_task_service.py`, `apps/api/app/services/ai_action_executor.py`, `apps/api/app/services/ai_provider.py`, `apps/api/app/services/ai_response_validation.py`, `apps/api/app/services/ai_settings_service.py`, `apps/api/app/services/ai_usage_service.py`, `apps/api/app/services/ai_prompt_schemas.py`, `apps/api/app/services/schedule_parser.py`
- Analytics + reports: UI in `apps/web/app/(app)/reports/page.tsx`, `apps/web/app/(app)/dashboard/page.tsx`, `apps/web/components/reports/*`; API in `apps/api/app/routers/analytics.py`, `apps/api/app/routers/dashboard.py`; services in `apps/api/app/services/analytics_service.py`, `apps/api/app/services/analytics_shared.py`, `apps/api/app/services/analytics_surrogate_service.py`, `apps/api/app/services/analytics_meta_service.py`, `apps/api/app/services/analytics_usage_service.py`, `apps/api/app/services/dashboard_service.py`, `apps/api/app/services/dashboard_events.py`
- Notifications: UI in `apps/web/app/(app)/notifications/page.tsx`, `apps/web/components/notification-bell.tsx`; API in `apps/api/app/routers/notifications.py`, `apps/api/app/routers/websocket.py`; services in `apps/api/app/services/notification_service.py`, `apps/api/app/services/notification_facade.py`
- Integrations: UI in `apps/web/app/(app)/settings/integrations/*`; API in `apps/api/app/routers/integrations.py`, `apps/api/app/routers/webhooks.py`, `apps/api/app/routers/meta_oauth.py`, `apps/api/app/routers/zapier.py`, `apps/api/app/routers/resend.py`; services in `apps/api/app/services/google_oauth.py`, `apps/api/app/services/gmail_service.py`, `apps/api/app/services/calendar_service.py`, `apps/api/app/services/zoom_service.py`, `apps/api/app/services/meta_api.py`, `apps/api/app/services/meta_capi.py`, `apps/api/app/services/meta_token_service.py`, `apps/api/app/services/oauth_service.py`, `apps/api/app/services/webhooks/*`, `apps/api/app/services/zapier_settings_service.py`, `apps/api/app/services/zapier_outbound_service.py`, `apps/api/app/services/resend_settings_service.py`
- Compliance + audit: UI in `apps/web/app/(app)/settings/compliance/page.tsx`, `apps/web/app/(app)/settings/audit/page.tsx`; API in `apps/api/app/routers/compliance.py`, `apps/api/app/routers/audit.py`; services in `apps/api/app/services/compliance_service.py`, `apps/api/app/services/audit_service.py`, `apps/api/app/services/pii_anonymizer.py`, `apps/api/app/services/version_service.py`
- Pipelines + Queues: UI in `apps/web/app/(app)/settings/pipelines/page.tsx`, `apps/web/app/(app)/settings/queues/page.tsx`; API in `apps/api/app/routers/pipelines.py`, `apps/api/app/routers/queues.py`; services in `apps/api/app/services/pipeline_service.py`, `apps/api/app/services/queue_service.py`
- Platform admin (Ops Console): UI in `apps/web/app/ops/*`, `apps/web/components/ops/*`; API in `apps/api/app/routers/platform.py`, `apps/api/app/routers/ops.py`; services in `apps/api/app/services/platform_service.py`, `apps/api/app/services/ops_service.py`, `apps/api/app/services/platform_email_service.py`

---

## Data Model Index
Models live in `apps/api/app/db/models/*` with migrations in `apps/api/alembic/versions/*`.

### Auth + Org
- `Organization` (organizations)
- `OrganizationSubscription` (organization_subscriptions) - plan, status, auto_renew, period dates
- `User` (users) - includes `is_platform_admin` flag
- `Membership` (memberships)
- `AuthIdentity` (auth_identities)
- `UserSession` (user_sessions)
- `OrgInvite` (org_invites)
- `RolePermission` (role_permissions)
- `UserPermissionOverride` (user_permission_overrides)
- `UserNotificationSettings` (user_notification_settings)
- `OrgCounter` (org_counters)
- `AdminActionLog` (admin_action_logs) - platform admin audit trail with HMAC'd IP/UA

### Surrogates + Journey + Profile
- `Surrogate` (surrogates)
- `SurrogateStatusHistory` (surrogate_status_history)
- `SurrogateActivityLog` (surrogate_activity_logs)
- `SurrogateContactAttempt` (surrogate_contact_attempts)
- `SurrogateImport` (surrogate_imports)
- `ImportTemplate` (import_templates)
- `CustomField` (custom_fields)
- `CustomFieldValue` (custom_field_values)
- `SurrogateInterview` (surrogate_interviews)
- `SurrogateProfileState` (surrogate_profile_state)
- `SurrogateProfileOverride` (surrogate_profile_overrides)
- `SurrogateProfileHiddenField` (surrogate_profile_hidden_fields)
- `JourneyFeaturedImage` (journey_featured_images)

### Intended Parents + Matches
- `IntendedParent` (intended_parents)
- `IntendedParentStatusHistory` (intended_parent_status_history)
- `Match` (matches)
- `MatchEvent` (match_events)
- `StatusChangeRequest` (status_change_requests)

### Tasks + Notes
- `Task` (tasks)
- `EntityNote` (entity_notes)

### Interviews + Attachments
- `InterviewNote` (interview_notes)
- `InterviewTranscriptVersion` (interview_transcript_versions)
- `InterviewAttachment` (interview_attachments)
- `Attachment` (attachments)

### Appointments + Booking
- `AppointmentType` (appointment_types)
- `AvailabilityRule` (availability_rules)
- `AvailabilityOverride` (availability_overrides)
- `BookingLink` (booking_links)
- `Appointment` (appointments)
- `AppointmentEmailLog` (appointment_email_logs)
- `ZoomMeeting` (zoom_meetings)
- `ZoomWebhookEvent` (zoom_webhook_events)

### Forms
- `Form` (forms)
- `FormLogo` (form_logos)
- `FormFieldMapping` (form_field_mappings)
- `FormSubmission` (form_submissions)
- `FormSubmissionToken` (form_submission_tokens)
- `FormSubmissionFile` (form_submission_files)

### Workflows + Automation
- `AutomationWorkflow` (automation_workflows)
- `WorkflowExecution` (workflow_executions)
- `WorkflowTemplate` (workflow_templates)
- `WorkflowResumeJob` (workflow_resume_jobs)
- `UserWorkflowPreference` (user_workflow_preferences)

### Campaigns + Email
- `Campaign` (campaigns)
- `CampaignRun` (campaign_runs)
- `CampaignRecipient` (campaign_recipients)
- `CampaignTrackingEvent` (campaign_tracking_events)
- `EmailTemplate` (email_templates)
- `EmailLog` (email_logs)
- `EmailSuppression` (email_suppressions)

### AI
- `AISettings` (ai_settings)
- `AIConversation` (ai_conversations)
- `AIMessage` (ai_messages)
- `AIActionApproval` (ai_action_approvals)
- `AIEntitySummary` (ai_entity_summaries)
- `AIUsageLog` (ai_usage_logs)
- `AIBulkTaskRequest` (ai_bulk_task_requests)

### Integrations + Meta
- `UserIntegration` (user_integrations)
- `MetaLead` (meta_leads)
- `MetaForm` (meta_forms)
- `MetaFormVersion` (meta_form_versions)
- `MetaPageMapping` (meta_page_mappings)
- `MetaAdAccount` (meta_ad_accounts)
- `MetaCampaign` (meta_campaigns)
- `MetaAdSet` (meta_ad_sets)
- `MetaAd` (meta_ads)
- `MetaDailySpend` (meta_daily_spend)
- `IntegrationHealth` (integration_health)
- `IntegrationErrorRollup` (integration_error_rollups)

### Pipelines + Queues
- `Pipeline` (pipelines)
- `PipelineStage` (pipeline_stages)
- `Queue` (queues)

### Notifications
- `Notification` (notifications)

### Compliance + Audit + Ops
- `AuditLog` (audit_logs)
- `EntityVersion` (entity_versions)
- `DataRetentionPolicy` (data_retention_policies)
- `LegalHold` (legal_holds)
- `ExportJob` (export_jobs)
- `Job` (jobs)
- `SystemAlert` (system_alerts)
- `AnalyticsSnapshot` (analytics_snapshots)
- `RequestMetricsRollup` (request_metrics_rollups)

---

## API Index (Routers)
See each router for full endpoint list. Total: 75 router files.

### Authentication & Security
- Auth: `apps/api/app/routers/auth.py` (prefix `/auth`)
- MFA: `apps/api/app/routers/mfa.py` (prefix `/mfa`)
- OIDC: `apps/api/app/routers/oidc.py` (prefix `/oidc`)

### Core Entities
- Surrogates: `apps/api/app/routers/surrogates.py` (prefix `/surrogates`)
- Surrogates read: `apps/api/app/routers/surrogates_read.py`
- Surrogates write: `apps/api/app/routers/surrogates_write.py`
- Surrogates status: `apps/api/app/routers/surrogates_status.py`
- Surrogates shared: `apps/api/app/routers/surrogates_shared.py`
- Surrogates email: `apps/api/app/routers/surrogates_email.py`
- Surrogates contact attempts: `apps/api/app/routers/surrogates_contact_attempts.py`
- Journey: `apps/api/app/routers/journey.py` (prefix `/journey`)
- Profile: `apps/api/app/routers/profile.py` (prefix `/surrogates/{id}/profile*`)
- Intended Parents: `apps/api/app/routers/intended_parents.py` (prefix `/intended-parents`)
- Matches: `apps/api/app/routers/matches.py` (prefix `/matches`)
- Status change requests: `apps/api/app/routers/status_change_requests.py` (prefix `/status-change-requests`)
- Tasks: `apps/api/app/routers/tasks.py` (prefix `/tasks`)
- Notes: `apps/api/app/routers/notes.py` (mixed paths)
- Interviews: `apps/api/app/routers/interviews.py` (mixed paths)
- Attachments: `apps/api/app/routers/attachments.py` (prefix `/attachments`)

### Appointments & Booking
- Appointments: `apps/api/app/routers/appointments.py` (prefix `/appointments`)
- Booking (public): `apps/api/app/routers/booking.py` (prefix `/book`)

### Forms & Import
- Forms: `apps/api/app/routers/forms.py` (prefix `/forms`)
- Forms public: `apps/api/app/routers/forms_public.py` (prefix `/forms/public`)
- Meta forms: `apps/api/app/routers/meta_forms.py` (prefix `/meta-forms`)
- Surrogates import: `apps/api/app/routers/surrogates_import.py` (prefix `/surrogates/import`)
- Import templates: `apps/api/app/routers/import_templates.py` (prefix `/import-templates`)
- Custom fields: `apps/api/app/routers/custom_fields.py` (prefix `/custom-fields`)

### Automation & Campaigns
- Workflows: `apps/api/app/routers/workflows.py` (prefix `/workflows`)
- Templates: `apps/api/app/routers/templates.py` (prefix `/templates`)
- Campaigns: `apps/api/app/routers/campaigns.py` (prefix `/campaigns`)
- Email templates: `apps/api/app/routers/email_templates.py` (prefix `/email-templates`)
- Tracking: `apps/api/app/routers/tracking.py` (prefix `/tracking`)
- Unsubscribe: `apps/api/app/routers/unsubscribe.py` (prefix `/unsubscribe`)

### AI
- AI root: `apps/api/app/routers/ai.py` (prefix `/ai`)
- AI chat: `apps/api/app/routers/ai_chat.py`
- AI actions: `apps/api/app/routers/ai_actions.py`
- AI tasks: `apps/api/app/routers/ai_tasks.py`
- AI workflows: `apps/api/app/routers/ai_workflows.py`
- AI conversations: `apps/api/app/routers/ai_conversations.py`
- AI settings: `apps/api/app/routers/ai_settings.py`
- AI focus: `apps/api/app/routers/ai_focus.py`
- AI schedule: `apps/api/app/routers/ai_schedule.py`
- AI consent: `apps/api/app/routers/ai_consent.py`
- AI usage: `apps/api/app/routers/ai_usage.py`

### Analytics & Dashboard
- Analytics: `apps/api/app/routers/analytics.py` (prefix `/analytics`)
- Dashboard: `apps/api/app/routers/dashboard.py` (prefix `/dashboard`)
- Search: `apps/api/app/routers/search.py` (prefix `/search`)

### Notifications & WebSocket
- Notifications: `apps/api/app/routers/notifications.py` (prefix `/me`)
- WebSocket: `apps/api/app/routers/websocket.py` (prefix `/ws`)

### Integrations
- Integrations: `apps/api/app/routers/integrations.py` (prefix `/integrations`)
- Webhooks: `apps/api/app/routers/webhooks.py` (prefix `/webhooks`)
- Meta OAuth: `apps/api/app/routers/meta_oauth.py` (prefix `/integrations/meta`)
- Zapier: `apps/api/app/routers/zapier.py` (prefix `/zapier`)
- Resend: `apps/api/app/routers/resend.py` (prefix `/resend`)

### Settings & Configuration
- Settings: `apps/api/app/routers/settings.py` (prefix `/settings`)
- Pipelines: `apps/api/app/routers/pipelines.py` (prefix `/settings/pipelines`)
- Queues: `apps/api/app/routers/queues.py` (prefix `/queues`)
- Permissions: `apps/api/app/routers/permissions.py` (prefix `/settings/permissions`)
- Invites: `apps/api/app/routers/invites.py` (prefix `/settings/invites`)

### Compliance & Audit
- Compliance: `apps/api/app/routers/compliance.py` (prefix `/compliance`)
- Audit: `apps/api/app/routers/audit.py` (prefix `/audit`)

### Admin & Operations
- Admin exports: `apps/api/app/routers/admin_exports.py` (prefix `/admin/exports`)
- Admin imports: `apps/api/app/routers/admin_imports.py` (prefix `/admin/imports`)
- Admin meta: `apps/api/app/routers/admin_meta.py` (prefix `/admin/meta-pages` + meta sync)
- Admin versions: `apps/api/app/routers/admin_versions.py` (prefix `/admin/versions`)
- Ops: `apps/api/app/routers/ops.py` (prefix `/ops`)
- Platform admin: `apps/api/app/routers/platform.py` (prefix `/platform`) - cross-org management

### System & Internal
- Jobs list: `apps/api/app/routers/jobs.py` (prefix `/jobs`)
- Internal schedules: `apps/api/app/routers/internal.py` (prefix `/internal/scheduled`) - includes subscription-sweep
- Monitoring alerts: `apps/api/app/routers/monitoring.py` (prefix `/internal/alerts`)
- Metadata: `apps/api/app/routers/metadata.py` (prefix `/metadata`)
- Public: `apps/api/app/routers/public.py` (prefix `/public`)
- Dev-only: `apps/api/app/routers/dev.py` (prefix `/dev`)

---

## Services Index
Services live in `apps/api/app/services/*`. Total: 100+ service files.

### Core Services
- `auth_service.py` - User authentication, invite handling
- `session_service.py` - Session management
- `user_service.py` - User CRUD and profile management
- `org_service.py` - Organization creation and retrieval
- `membership_service.py` - Membership management
- `permission_service.py` - RBAC query/grant service
- `invite_service.py` - Team invites
- `invite_email_service.py` - Invite email notifications

### Entity Services
- `surrogate_service.py` - Surrogate CRUD, status management
- `surrogate_status_service.py` - Status transition logic
- `surrogate_events.py` - Surrogate event publishing
- `ip_service.py` - Intended parent management
- `intended_parent_status_service.py` - IP status transitions
- `match_service.py` - Match creation, lifecycle
- `status_change_request_service.py` - Status change request workflow
- `task_service.py` - Task CRUD and assignment
- `task_events.py` - Task event publishing
- `note_service.py` - Entity notes management
- `interview_service.py` - Interview creation and transcript handling
- `interview_note_service.py` - Interview notes
- `interview_attachment_service.py` - Interview file attachments
- `profile_service.py` - Surrogate profile data management
- `journey_service.py` - Journey timeline management
- `contact_attempt_service.py` - Contact attempt tracking
- `contact_reminder_service.py` - Contact reminders
- `activity_service.py` - Activity logging

### Appointment Services
- `appointment_service.py` - Appointment CRUD
- `appointment_email_service.py` - Appointment notifications
- `appointment_integrations.py` - Calendar/booking integrations

### Form Services
- `form_service.py` - Form CRUD and configuration
- `form_submission_service.py` - Form submission processing
- `import_template_service.py` - CSV import template management
- `import_service.py` - CSV import pipeline orchestration
- `import_detection_service.py` - Field mapping detection
- `import_ai_mapper_service.py` - AI-assisted field mapping
- `import_transformers.py` - Data transformation during import
- `custom_field_service.py` - Custom field CRUD

### Automation/Workflow Services
- `workflow_engine.py` - Core workflow execution engine
- `workflow_triggers.py` - Workflow trigger evaluation
- `workflow_action_preview.py` - Action preview generation
- `workflow_service.py` - Workflow CRUD
- `workflow_access.py` - Workflow access control
- `workflow_email_provider.py` - Workflow email sending
- `campaign_service.py` - Campaign management
- `template_service.py` - Email template management
- `system_email_template_service.py` - System template seeding
- `template_seeder.py` - System template initialization
- `signature_template_service.py` - Signature templates

### AI Services
- `ai_service.py` - Main AI orchestration
- `ai_chat_service.py` - AI chat conversations
- `ai_interview_service.py` - AI interview analysis
- `ai_task_service.py` - AI task generation
- `ai_workflow_service.py` - AI workflow assistance
- `ai_action_executor.py` - AI action execution (approval workflow)
- `ai_provider.py` - AI provider abstraction (Claude, etc.)
- `ai_response_validation.py` - Response validation and safety
- `ai_settings_service.py` - AI settings management
- `ai_usage_service.py` - AI usage tracking
- `ai_prompt_schemas.py` - Prompt validation schemas
- `schedule_parser.py` - Schedule parsing from natural language

### Email Services
- `email_service.py` - Email sending orchestration
- `email_sender.py` - Email provider abstraction
- `resend_email_service.py` - Resend API integration
- `email_provider_service.py` - Email provider management
- `resend_settings_service.py` - Resend configuration
- `platform_email_service.py` - Platform admin emails

### Integration Services
- `google_oauth.py` - Google OAuth flow and token exchange
- `gmail_service.py` - Gmail API integration
- `calendar_service.py` - Google Calendar integration
- `zoom_service.py` - Zoom API integration (meetings, webhooks)
- `meta_api.py` - Meta API client
- `meta_capi.py` - Meta Conversions API
- `meta_token_service.py` - Meta token management
- `oauth_service.py` - OAuth provider abstraction
- `zapier_settings_service.py` - Zapier configuration
- `zapier_outbound_service.py` - Zapier outbound events

### Webhook Handlers (`webhooks/`)
- `base.py` - Base webhook handler
- `registry.py` - Webhook handler registry
- `meta.py` - Meta webhook handler
- `zoom.py` - Zoom webhook handler
- `resend.py` - Resend webhook handler
- `zapier.py` - Zapier webhook handler

### Analytics Services
- `analytics_service.py` - Analytics data aggregation
- `analytics_shared.py` - Shared analytics utilities
- `analytics_surrogate_service.py` - Surrogate analytics
- `analytics_meta_service.py` - Meta analytics
- `analytics_usage_service.py` - Usage analytics
- `dashboard_service.py` - Dashboard data aggregation
- `dashboard_events.py` - Dashboard event publishing
- `metrics_service.py` - Request metrics and performance tracking

### Compliance/Admin Services
- `compliance_service.py` - Compliance logic and checks
- `audit_service.py` - Audit logging
- `version_service.py` - Data versioning
- `pii_anonymizer.py` - PII anonymization for purge
- `admin_export_service.py` - Data export functionality
- `admin_import_service.py` - Data import functionality
- `platform_service.py` - Platform admin operations (cross-org)
- `ops_service.py` - Operations service
- `alert_service.py` - System alert management
- `tracking_service.py` - Campaign/form tracking
- `unsubscribe_service.py` - Email unsubscribe handling

### Pipeline & Queue Services
- `pipeline_service.py` - Pipeline configuration
- `queue_service.py` - Queue management

### Utility Services
- `attachment_service.py` - File attachment handling
- `storage_client.py` - S3 storage management
- `storage_url_service.py` - Storage URL generation
- `media_service.py` - Media file handling
- `pdf_export_service.py` - PDF generation
- `transcription_service.py` - Interview transcription
- `transcript_storage_service.py` - Transcript storage
- `notification_service.py` - Notification routing
- `notification_facade.py` - Notification facade
- `search_service.py` - Full-text search
- `http_service.py` - HTTP utility methods
- `tiptap_service.py` - Rich text editing support
- `dev_service.py` - Development utilities
- `job_service.py` - Job queue management
- `mfa_service.py` - MFA management
- `duo_service.py` - Duo MFA integration
- `wif_oidc_service.py` - WIF OIDC setup

---

## Job/Worker Index
Job types defined in `apps/api/app/db/enums/jobs.py` and processed in `apps/api/app/worker.py`.

### Job Handlers (`apps/api/app/jobs/handlers/`)
- `email.py` - Email sending (SEND_EMAIL)
- `notifications.py` - Notifications (NOTIFICATION, REMINDER)
- `reminders.py` - Contact reminders (CONTACT_REMINDER_CHECK)
- `campaigns.py` - Campaign execution (CAMPAIGN_SEND)
- `workflows.py` - Workflow sweeps and approvals (WORKFLOW_SWEEP, WORKFLOW_EMAIL, WORKFLOW_APPROVAL_EXPIRY, WORKFLOW_RESUME)
- `meta.py` - Meta Lead Ads sync (META_LEAD_FETCH, META_CAPI_EVENT, META_HIERARCHY_SYNC, META_SPEND_SYNC, META_FORM_SYNC)
- `imports.py` - CSV import (CSV_IMPORT)
- `exports.py` - Data export (EXPORT_GENERATION, ADMIN_EXPORT)
- `interviews.py` - Interview transcription (INTERVIEW_TRANSCRIPTION)
- `webhooks.py` - Webhook retries (WEBHOOK_RETRY)
- `attachments.py` - Attachment scanning (ClamAV)
- `data_purge.py` - Data retention purges (DATA_PURGE)
- `ai.py` - AI operations (AI_CHAT)
- `orgs.py` - Organization jobs
- `zapier.py` - Zapier operations

### Support Files
- `registry.py` - Job type registry and metadata
- `utils.py` - Job utility functions
- `scan_attachment.py` - ClamAV integration

Scheduled triggers live in `apps/api/app/routers/internal.py`.

---

## Integration Index
- Google OAuth + Gmail/Calendar: `apps/api/app/services/google_oauth.py`, `apps/api/app/services/gmail_service.py`, `apps/api/app/services/calendar_service.py`, `apps/api/app/routers/integrations.py`
- Zoom: `apps/api/app/services/zoom_service.py`, `apps/api/app/routers/integrations.py`, `apps/api/app/routers/webhooks.py`
- Meta Lead Ads + CAPI + Insights: `apps/api/app/services/meta_*`, `apps/api/app/routers/webhooks.py`, `apps/api/app/routers/admin_meta.py`, `apps/api/app/routers/meta_oauth.py`, `apps/api/app/routers/meta_forms.py`
- Email provider (Resend): `apps/api/app/services/email_service.py`, `apps/api/app/services/resend_email_service.py`, `apps/api/app/worker.py`
- File storage: `apps/api/app/services/media_service.py`, `apps/api/app/services/attachment_service.py`, `apps/api/app/services/storage_client.py`
- AI providers: `apps/api/app/services/ai_provider.py`, `apps/api/app/services/ai_chat_service.py`
- PDF export: `apps/api/app/services/pdf_export_service.py`
- Zapier: `apps/api/app/services/zapier_*`, `apps/api/app/routers/zapier.py`
- MFA (Duo): `apps/api/app/services/duo_service.py`, `apps/api/app/services/mfa_service.py`

---

## Security/Permissions Touchpoints
- Session + permissions: `apps/api/app/core/deps.py`
- RBAC + policies: `apps/api/app/core/permissions.py`, `apps/api/app/core/policies.py`
- Surrogate ownership checks: `apps/api/app/core/surrogate_access.py`
- CSRF enforcement: `apps/api/app/core/csrf.py`, middleware in `apps/api/app/main.py`, client headers in `apps/web/lib/csrf.ts`
- Rate limiting: `apps/api/app/core/rate_limit.py`, `apps/api/app/core/redis_client.py`
- Encryption and hashing: `apps/api/app/core/encryption.py`, `apps/api/app/db/types.py`, `apps/api/app/services/pii_anonymizer.py`
- Security utilities: `apps/api/app/core/security.py`
- Audit logging: `apps/api/app/services/audit_service.py`

---

## Frontend API + Hooks Index

### API Clients (`apps/web/lib/api/*`) - 40 files
- `ai.ts` - AI chat and actions
- `admin-meta.ts` - Admin Meta sync
- `analytics.ts` - Analytics data
- `appointments.ts` - Appointment operations
- `attachments.ts` - File attachments
- `audit.ts` - Audit log queries
- `campaigns.ts` - Campaign management
- `compliance.ts` - Compliance operations
- `dashboard.ts` - Dashboard data
- `email-templates.ts` - Email template management
- `forms.ts` - Form operations
- `import.ts` - CSV import
- `integrations.ts` - Integration management
- `intended-parents.ts` - IP operations
- `interviews.ts` - Interview operations
- `invites.ts` - Team invites
- `journey.ts` - Journey timeline
- `matches.ts` - Match operations
- `meta-forms.ts` - Meta form configuration
- `meta-oauth.ts` - Meta OAuth flow
- `mfa.ts` - MFA operations
- `notes.ts` - Note operations
- `notifications.ts` - Notifications
- `ops.ts` - Ops console operations
- `permissions.ts` - Permission queries
- `pipelines.ts` - Pipeline configuration
- `platform.ts` - Platform admin operations
- `profile.ts` - User profile
- `resend.ts` - Resend configuration
- `schedule-parser.ts` - AI schedule parsing
- `search.ts` - Global search
- `settings.ts` - Settings management
- `signature.ts` - Signature templates
- `status-change-requests.ts` - Status change requests
- `surrogates.ts` - Surrogate operations
- `system.ts` - System metadata
- `tasks.ts` - Task operations
- `workflows.ts` - Workflow operations
- `zapier.ts` - Zapier configuration

### React Hooks (`apps/web/lib/hooks/*`) - 44 files
- `use-ai.ts` - AI queries and mutations
- `use-admin-meta.ts` - Admin Meta queries
- `use-analytics.ts` - Analytics data
- `use-appointments.ts` - Appointment queries
- `use-attachments.ts` - Attachment queries
- `use-audit.ts` - Audit log queries
- `use-browser-notifications.ts` - Browser notification API
- `use-campaigns.ts` - Campaign queries
- `use-compliance.ts` - Compliance queries
- `use-dashboard.ts` - Dashboard data
- `use-dashboard-socket.ts` - Dashboard WebSocket
- `use-debounced-value.ts` - Debounce utility
- `use-email-templates.ts` - Email template queries
- `use-forms.ts` - Form queries
- `use-import.ts` - Import queries
- `use-intended-parents.ts` - IP queries
- `use-interviews.ts` - Interview queries
- `use-invites.ts` - Invite queries
- `use-journey.ts` - Journey queries
- `use-matches.ts` - Match queries
- `use-media-query.ts` - CSS media query hook
- `use-meta-forms.ts` - Meta form queries
- `use-meta-oauth.ts` - Meta OAuth queries
- `use-mfa.ts` - MFA queries
- `use-notes.ts` - Note queries
- `use-notification-socket.ts` - Notification WebSocket
- `use-notifications.ts` - Notification queries
- `use-ops.ts` - Ops console queries
- `use-permissions.ts` - Permission queries
- `use-pipelines.ts` - Pipeline queries
- `use-profile.ts` - User profile queries
- `use-queues.ts` - Queue queries
- `use-resend.ts` - Resend queries
- `use-schedule-parser.ts` - Schedule parser
- `use-sessions.ts` - Session management
- `use-signature.ts` - Signature queries
- `use-status-change-requests.ts` - Status change request queries
- `use-surrogates.ts` - Surrogate queries
- `use-system.ts` - System metadata
- `use-tasks.ts` - Task queries
- `use-unified-calendar-data.ts` - Calendar data aggregation
- `use-user-integrations.ts` - Integration queries
- `use-workflows.ts` - Workflow queries
- `use-zapier.ts` - Zapier queries

---

## Testing and Tooling
- Backend tests: `apps/api/tests/*`
- Frontend tests: `apps/web/tests/*`
- Load tests: `load-tests/*`
- Lint/format: `apps/api/pyproject.toml`, `apps/web/eslint.config.mjs`
