# CODEMAP

## System Architecture Overview
- Frontend: Next.js 16 App Router in `apps/web` (SSR + client components, React Query, Zustand)
- Backend: FastAPI app in `apps/api/app/main.py` with thin routers and service layer
- Background jobs: polling worker in `apps/api/app/worker.py` processing `Job` rows; scheduled triggers via `/internal/scheduled/*`
- Database: PostgreSQL with SQLAlchemy models in `apps/api/app/db/models.py`, migrations in `apps/api/alembic/versions` (archive in `apps/api/alembic/versions_archive`)
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
- Core utilities: `apps/api/app/core/*` (config, deps, csrf, rate limits, permissions, policies, logging, stage rules, async_utils)
- DB: `apps/api/app/db/*` (models, enums, session)
- Utils: `apps/api/app/utils/*` (normalization, pagination)
- Routers: `apps/api/app/routers/*` (see API Index)
- Services: `apps/api/app/services/*` (surrogates, matches, workflows, AI, analytics, integrations, compliance)
- Service events: `apps/api/app/services/dashboard_events.py`, `apps/api/app/services/task_events.py`
- Notification facade: `apps/api/app/services/notification_facade.py`
- Email sender interface: `apps/api/app/services/email_sender.py`
- Surrogate status helper: `apps/api/app/services/surrogate_status_service.py`
- Form submissions: `apps/api/app/services/form_submission_service.py`
- CSV import pipeline: `apps/api/app/services/import_service.py`, `apps/api/app/routers/surrogates_import.py`
- Import templates: `apps/api/app/services/import_template_service.py`, `apps/api/app/routers/import_templates.py`
- Custom fields: `apps/api/app/services/custom_field_service.py`, `apps/api/app/routers/custom_fields.py`
- Schemas: `apps/api/app/schemas/*`
- Jobs: `apps/api/app/jobs/*`
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
- Components: `apps/web/components/*` (surrogates, interviews, matches, tasks, appointments, AI, reports)
- Surrogate tabs: `apps/web/components/surrogates/tabs/*`
- API + hooks: `apps/web/lib/api.ts`, `apps/web/lib/api/*` (includes `platform.ts` for ops console), `apps/web/lib/hooks/*` (includes `use-unified-calendar-data.ts`)
- Context/state: `apps/web/lib/auth-context.tsx`, `apps/web/lib/context/ai-context.tsx`, `apps/web/lib/store/*`
- UI utilities: `apps/web/lib/utils/task-due.ts`
- Routing: `apps/web/next.config.js` rewrites (host-based routing for ops subdomain)
- Tests: `apps/web/tests/*`

---

## Feature -> Module Mapping
- Authentication + MFA: UI in `apps/web/app/login/page.tsx`, `apps/web/app/mfa/page.tsx`; API in `apps/api/app/routers/auth.py`, `apps/api/app/routers/mfa.py`; services in `apps/api/app/services/auth_service.py`, `apps/api/app/services/session_service.py`
- Surrogates (Surrogacy Force): UI in `apps/web/app/(app)/surrogates/page.tsx`, `apps/web/app/(app)/surrogates/[id]/page.tsx`; API in `apps/api/app/routers/surrogates.py`; services in `apps/api/app/services/surrogate_service.py`
- Journey timeline: UI in `apps/web/components/surrogates/journey/*`; API in `apps/api/app/routers/journey.py`; service in `apps/api/app/services/journey_service.py`
- Surrogate profile: UI in `apps/web/components/surrogates/SurrogateProfileCard.tsx`; API in `apps/api/app/routers/profile.py`; service in `apps/api/app/services/profile_service.py`
- Intended parents: UI in `apps/web/app/(app)/intended-parents/page.tsx`; API in `apps/api/app/routers/intended_parents.py`; service in `apps/api/app/services/ip_service.py`
- Matches: UI in `apps/web/app/(app)/matches/page.tsx` and `apps/web/app/(app)/intended-parents/matches/*`; API in `apps/api/app/routers/matches.py`; service in `apps/api/app/services/match_service.py`
- Tasks: UI in `apps/web/app/(app)/tasks/page.tsx`; API in `apps/api/app/routers/tasks.py`; service in `apps/api/app/services/task_service.py`
- Interviews: UI in `apps/web/components/surrogates/interviews/*`; API in `apps/api/app/routers/interviews.py`; service in `apps/api/app/services/interview_service.py`
- Appointments/booking: UI in `apps/web/app/(app)/appointments/page.tsx`, `apps/web/app/book/*`; API in `apps/api/app/routers/appointments.py`, `apps/api/app/routers/booking.py`; service in `apps/api/app/services/appointment_service.py`
- Forms: UI in `apps/web/app/(app)/automation/forms/*`, public in `apps/web/app/apply/[token]/page.tsx`; API in `apps/api/app/routers/forms.py`, `apps/api/app/routers/forms_public.py`; services in `apps/api/app/services/form_service.py`, `apps/api/app/services/form_submission_service.py`
- CSV imports + templates: API in `apps/api/app/routers/surrogates_import.py`, `apps/api/app/routers/import_templates.py`, `apps/api/app/routers/custom_fields.py`; services in `apps/api/app/services/import_service.py`, `apps/api/app/services/import_template_service.py`, `apps/api/app/services/custom_field_service.py`
- Automation/workflows: UI in `apps/web/app/(app)/automation/*`; API in `apps/api/app/routers/workflows.py`, `apps/api/app/routers/templates.py`; services in `apps/api/app/services/workflow_engine.py`, `apps/api/app/services/workflow_triggers.py`
- Campaigns + email templates: UI in `apps/web/app/(app)/automation/campaigns/*`, `apps/web/app/(app)/automation/email-templates/page.tsx`; API in `apps/api/app/routers/campaigns.py`, `apps/api/app/routers/email_templates.py`; services in `apps/api/app/services/campaign_service.py`, `apps/api/app/services/email_service.py`
- AI assistant: UI in `apps/web/app/(app)/ai-assistant/page.tsx`; API in `apps/api/app/routers/ai.py`; services in `apps/api/app/services/ai_chat_service.py`, `apps/api/app/services/ai_workflow_service.py`, `apps/api/app/services/ai_interview_service.py`
- Analytics + reports: UI in `apps/web/app/(app)/reports/page.tsx`, `apps/web/app/(app)/dashboard/page.tsx`; API in `apps/api/app/routers/analytics.py`, `apps/api/app/routers/dashboard.py`; services in `apps/api/app/services/analytics_service.py`
- Notifications: UI in `apps/web/app/(app)/notifications/page.tsx`; API in `apps/api/app/routers/notifications.py`, `apps/api/app/routers/websocket.py`; services in `apps/api/app/services/notification_service.py`
- Integrations: UI in `apps/web/app/(app)/settings/integrations/*`; API in `apps/api/app/routers/integrations.py`, `apps/api/app/routers/webhooks.py`; services in `apps/api/app/services/google_oauth.py`, `apps/api/app/services/gmail_service.py`, `apps/api/app/services/zoom_service.py`, `apps/api/app/services/meta_*`
- Compliance + audit: UI in `apps/web/app/(app)/settings/compliance/page.tsx`, `apps/web/app/(app)/settings/audit/page.tsx`; API in `apps/api/app/routers/compliance.py`, `apps/api/app/routers/audit.py`; services in `apps/api/app/services/compliance_service.py`, `apps/api/app/services/audit_service.py`
- Platform admin (Ops Console): UI in `apps/web/app/ops/*`; API in `apps/api/app/routers/platform.py`; services in `apps/api/app/services/platform_service.py`; cross-org management of agencies, subscriptions, members, invites, alerts, and admin action logs

---

## Data Model Index
Models live in `apps/api/app/db/models.py` with migrations in `apps/api/alembic/versions/*`.

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
See each router for full endpoint list.

- Auth: `apps/api/app/routers/auth.py` (prefix `/auth`)
- MFA: `apps/api/app/routers/mfa.py` (prefix `/mfa`)
- Surrogates: `apps/api/app/routers/surrogates.py` (prefix `/surrogates`)
- Journey: `apps/api/app/routers/journey.py` (prefix `/journey`)
- Profile: `apps/api/app/routers/profile.py` (prefix `/surrogates/{id}/profile*`)
- Intended Parents: `apps/api/app/routers/intended_parents.py` (prefix `/intended-parents`)
- Matches: `apps/api/app/routers/matches.py` (prefix `/matches`)
- Tasks: `apps/api/app/routers/tasks.py` (prefix `/tasks`)
- Notes: `apps/api/app/routers/notes.py` (mixed paths)
- Interviews: `apps/api/app/routers/interviews.py` (mixed paths)
- Attachments: `apps/api/app/routers/attachments.py` (prefix `/attachments`)
- Appointments: `apps/api/app/routers/appointments.py` (prefix `/appointments`)
- Booking (public): `apps/api/app/routers/booking.py` (prefix `/book`)
- Forms: `apps/api/app/routers/forms.py` (prefix `/forms`)
- Forms public: `apps/api/app/routers/forms_public.py` (prefix `/forms/public`)
- Workflows: `apps/api/app/routers/workflows.py` (prefix `/workflows`)
- Templates: `apps/api/app/routers/templates.py` (prefix `/templates`)
- Campaigns: `apps/api/app/routers/campaigns.py` (prefix `/campaigns`)
- Email templates: `apps/api/app/routers/email_templates.py` (prefix `/email-templates`)
- Tracking: `apps/api/app/routers/tracking.py` (prefix `/tracking`)
- AI: `apps/api/app/routers/ai.py` (prefix `/ai`)
- Analytics: `apps/api/app/routers/analytics.py` (prefix `/analytics`)
- Dashboard: `apps/api/app/routers/dashboard.py` (prefix `/dashboard`)
- Search: `apps/api/app/routers/search.py` (prefix `/search`)
- Notifications: `apps/api/app/routers/notifications.py` (prefix `/me`)
- WebSocket: `apps/api/app/routers/websocket.py` (prefix `/ws`)
- Ops: `apps/api/app/routers/ops.py` (prefix `/ops`)
- Compliance: `apps/api/app/routers/compliance.py` (prefix `/compliance`)
- Audit: `apps/api/app/routers/audit.py` (prefix `/audit`)
- Integrations: `apps/api/app/routers/integrations.py` (prefix `/integrations`)
- Webhooks: `apps/api/app/routers/webhooks.py` (prefix `/webhooks`)
- Queues: `apps/api/app/routers/queues.py` (prefix `/queues`)
- Pipelines: `apps/api/app/routers/pipelines.py` (prefix `/settings/pipelines`)
- Permissions: `apps/api/app/routers/permissions.py` (prefix `/settings/permissions`)
- Settings: `apps/api/app/routers/settings.py` (prefix `/settings`)
- Invites: `apps/api/app/routers/invites.py` (prefix `/settings/invites`)
- Status change requests: `apps/api/app/routers/status_change_requests.py` (prefix `/status-change-requests`)
- Admin exports: `apps/api/app/routers/admin_exports.py` (prefix `/admin/exports`)
- Admin imports: `apps/api/app/routers/admin_imports.py` (prefix `/admin/imports`)
- Admin meta: `apps/api/app/routers/admin_meta.py` (prefix `/admin/meta-pages` + meta sync)
- Admin versions: `apps/api/app/routers/admin_versions.py` (prefix `/admin/versions`)
- Jobs list: `apps/api/app/routers/jobs.py` (prefix `/jobs`)
- Internal schedules: `apps/api/app/routers/internal.py` (prefix `/internal/scheduled`) - includes subscription-sweep
- Monitoring alerts: `apps/api/app/routers/monitoring.py` (prefix `/internal/alerts`)
- Platform admin: `apps/api/app/routers/platform.py` (prefix `/platform`) - cross-org management
- Metadata: `apps/api/app/routers/metadata.py` (prefix `/metadata`)
- Dev-only: `apps/api/app/routers/dev.py` (prefix `/dev`)

---

## Job/Worker Index
Job types defined in `apps/api/app/db/enums.py` and processed in `apps/api/app/worker.py`.

- Email + notifications: `SEND_EMAIL`, `REMINDER`, `NOTIFICATION`
- Webhooks: `WEBHOOK_RETRY`
- Meta: `META_LEAD_FETCH`, `META_CAPI_EVENT`, `META_HIERARCHY_SYNC`, `META_SPEND_SYNC`, `META_FORM_SYNC`
- Workflows: `WORKFLOW_SWEEP`, `WORKFLOW_EMAIL`, `WORKFLOW_APPROVAL_EXPIRY`, `WORKFLOW_RESUME`
- Imports/exports: `CSV_IMPORT`, `EXPORT_GENERATION`, `ADMIN_EXPORT`
- Compliance: `DATA_PURGE`
- Campaigns: `CAMPAIGN_SEND`
- AI: `AI_CHAT`
- Other: `CONTACT_REMINDER_CHECK`, `INTERVIEW_TRANSCRIPTION`

Scheduled triggers live in `apps/api/app/routers/internal.py`.

---

## Integration Index
- Google OAuth + Gmail/Calendar: `apps/api/app/services/google_oauth.py`, `apps/api/app/services/gmail_service.py`, `apps/api/app/services/calendar_service.py`, `apps/api/app/routers/integrations.py`
- Zoom: `apps/api/app/services/zoom_service.py`, `apps/api/app/routers/integrations.py`, `apps/api/app/routers/webhooks.py`
- Meta Lead Ads + CAPI + Insights: `apps/api/app/services/meta_*`, `apps/api/app/routers/webhooks.py`, `apps/api/app/routers/admin_meta.py`
- Email provider (Resend): `apps/api/app/services/email_service.py`, `apps/api/app/worker.py`
- File storage: `apps/api/app/services/media_service.py`, `apps/api/app/services/attachment_service.py`
- AI providers: `apps/api/app/services/ai_provider.py`, `apps/api/app/services/ai_chat_service.py`
- PDF export: `apps/api/app/services/pdf_export_service.py`

---

## Security/Permissions Touchpoints
- Session + permissions: `apps/api/app/core/deps.py`
- RBAC + policies: `apps/api/app/core/permissions.py`, `apps/api/app/core/policies.py`
- Surrogate ownership checks: `apps/api/app/core/surrogate_access.py`
- CSRF enforcement: `apps/api/app/core/csrf.py`, middleware in `apps/api/app/main.py`, client headers in `apps/web/lib/csrf.ts`
- Encryption and hashing: `apps/api/app/core/encryption.py`, `apps/api/app/db/types.py`, `apps/api/app/services/pii_anonymizer.py`
- Audit logging: `apps/api/app/services/audit_service.py`

---

## Testing and Tooling
- Backend tests: `apps/api/tests/*`
- Frontend tests: `apps/web/tests/*`
- Load tests: `load-tests/*`
- Lint/format: `apps/api/pyproject.toml`, `apps/web/eslint.config.mjs`
