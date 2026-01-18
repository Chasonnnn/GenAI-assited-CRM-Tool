# PRODUCT_E2E_AUDIT

## 1) Repo Inventory (Proof)
- Total files reviewed: 1103 (906 text, 197 binary)
- Excluded artifact directories: `.git/`, `node_modules/`, `.next/`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`, `__pycache__/`, `build/`, `dist/`
- Review included committed artifacts and archives such as `apps/api/alembic/versions_archive/`, `apps/web/tsconfig.tsbuildinfo`, and `apps/web/node-compile-cache/` (present in repo)

Directory/module overview:
- Root: product docs (`README.md`, `CHANGELOG.md`, `LAUNCH_READINESS.md`, `REVIEW.md`, etc), CI/CD (`.github/workflows/*`), infra (`docker-compose.yml`, `zap-baseline.conf`), tooling (`scripts/`, `load-tests/`)
- `apps/api`: FastAPI backend, SQLAlchemy models, Alembic migrations, worker, services, tests
- `apps/web`: Next.js 16 App Router frontend, components, React Query hooks, tests
- `docs`: design docs, automation guide, OAuth guide, deployment runbook

## 2) Feature Catalog (Complete)

### Authentication, Sessions, MFA, Invites
- Description: Login via Google OAuth, MFA (TOTP + Duo), session management, org invites
- UI entry points: `/login` (`apps/web/app/login/page.tsx`), `/mfa` (`apps/web/app/mfa/page.tsx`), `/auth/duo/callback` (`apps/web/app/auth/duo/callback/page.tsx`), `/invite/[id]` (`apps/web/app/invite/[id]/page.tsx`)
- API entry points: `/auth/*` (`apps/api/app/routers/auth.py`), `/mfa/*` (`apps/api/app/routers/mfa.py`), `/settings/invites/*` (`apps/api/app/routers/invites.py`)
- Data models: `User`, `Membership`, `UserSession`, `AuthIdentity`, `OrgInvite`
- Jobs/queues: session cleanup in `apps/api/app/worker.py`
- External integrations: Google OAuth, Duo
- Primary risks: session fixation, MFA bypass, invite token leakage

### Organization Settings, Team, RBAC, Queues, Pipelines
- Description: Org profile, team management, roles/permissions, queues, pipeline configuration
- UI entry points: `/settings` (`apps/web/app/(app)/settings/page.tsx`), `/settings/team/*`, `/settings/queues`, `/settings/pipelines`, `/settings/security`
- API entry points: `/settings/*` (`apps/api/app/routers/settings.py`), `/settings/permissions/*`, `/queues/*`, `/settings/pipelines/*`, `/metadata/*`
- Data models: `Organization`, `Membership`, `RolePermission`, `UserPermissionOverride`, `Queue`, `QueueMember`, `Pipeline`, `PipelineStage`, `UserNotificationSettings`
- Jobs/queues: none
- External integrations: none
- Primary risks: RBAC drift, pipeline versioning regressions

### Surrogate Intake and Management (Core CRM)
- Description: Surrogate CRUD, assignment/queue ownership, status changes, contact attempts, imports
- UI entry points: `/surrogates` (`apps/web/app/(app)/surrogates/page.tsx`), `/surrogates/[id]` (`apps/web/app/(app)/surrogates/[id]/page.tsx`)
- API entry points: `/surrogates/*` (`apps/api/app/routers/surrogates.py`), `/status-change-requests/*`, `/surrogates/import/*`
- Data models: `Surrogate`, `SurrogateStatusHistory`, `SurrogateActivityLog`, `SurrogateContactAttempt`, `SurrogateImport`, `OrgCounter`, `StatusChangeRequest`
- Jobs/queues: `CSV_IMPORT`, `CONTACT_REMINDER_CHECK`, `SEND_EMAIL`, `REMINDER`, `NOTIFICATION`
- External integrations: email provider (Resend), Meta lead ingestion (via jobs)
- Primary risks: owner-based access leakage, stage transition correctness

### Surrogate Journey + Profile
- Description: Journey timeline, featured images, profile overrides and PDF export
- UI entry points: journey tab in surrogate detail (`apps/web/components/surrogates/journey/*`), print view (`apps/web/app/(print)/surrogates/[id]/journey/print/page.tsx`)
- API entry points: `/journey/*` (`apps/api/app/routers/journey.py`), `/surrogates/{id}/profile*` (`apps/api/app/routers/profile.py`)
- Data models: `JourneyFeaturedImage`, `SurrogateProfileState`, `SurrogateProfileOverride`, `SurrogateProfileHiddenField`, `FormSubmission`
- Jobs/queues: none
- External integrations: Playwright PDF export
- Primary risks: access control, profile sync accuracy

### Intended Parents
- Description: Intended parent CRUD and status tracking
- UI entry points: `/intended-parents`, `/intended-parents/[id]`
- API entry points: `/intended-parents/*` (`apps/api/app/routers/intended_parents.py`)
- Data models: `IntendedParent`, `IntendedParentStatusHistory`
- Jobs/queues: none
- External integrations: none
- Primary risks: cross-entity linking correctness

### Matches and Match Events
- Description: Match management, events, acceptance/rejection, cancel requests
- UI entry points: `/matches`, `/intended-parents/matches`, `/intended-parents/matches/[id]`
- API entry points: `/matches/*` (`apps/api/app/routers/matches.py`)
- Data models: `Match`, `MatchEvent`
- Jobs/queues: notifications, workflow actions
- External integrations: none
- Primary risks: conflicting match state, audit consistency

### Tasks and Approvals
- Description: Task creation, assignment, bulk actions, workflow approval tasks
- UI entry points: `/tasks`, task calendars inside surrogate and match pages
- API entry points: `/tasks/*` (`apps/api/app/routers/tasks.py`), workflow approval actions in `/workflows/*`
- Data models: `Task`, `WorkflowExecution`, `WorkflowResumeJob`
- Jobs/queues: `REMINDER`, `NOTIFICATION`, `WORKFLOW_APPROVAL_EXPIRY`, `WORKFLOW_RESUME`
- External integrations: email provider
- Primary risks: access scoping for surrogate-linked tasks

### Notes and Activity
- Description: Notes and activity timeline across surrogates, matches, interviews
- UI entry points: surrogate detail notes, match detail notes
- API entry points: `/surrogates/{id}/notes`, `/notes/{note_id}`, `/interviews/{id}/notes`
- Data models: `EntityNote`, `SurrogateActivityLog`, `InterviewNote`
- Jobs/queues: none
- External integrations: none
- Primary risks: PII exposure in logs and exports

### Attachments and Files
- Description: File uploads for surrogates, intended parents, interviews, and forms
- UI entry points: upload dialogs in surrogate/match/interview views
- API entry points: `/attachments/*`, `/interviews/{id}/attachments`, `/forms/submissions/{id}/files`
- Data models: `Attachment`, `InterviewAttachment`, `FormSubmissionFile`
- Jobs/queues: virus scanning (manual job in `apps/api/app/jobs/scan_attachment.py`)
- External integrations: S3/local storage, ClamAV
- Primary risks: malware scanning gaps, download authorization

### Interviews and Transcripts
- Description: Interview records, transcript versions, annotations, AI summaries
- UI entry points: interview tab in surrogate detail (`apps/web/components/surrogates/interviews/*`)
- API entry points: `/surrogates/{id}/interviews`, `/interviews/{id}`, `/interviews/{id}/versions`, `/interviews/{id}/ai/summarize`
- Data models: `SurrogateInterview`, `InterviewTranscriptVersion`, `InterviewNote`, `InterviewAttachment`
- Jobs/queues: `INTERVIEW_TRANSCRIPTION`
- External integrations: AI provider / transcription services
- Primary risks: PII handling in transcripts, version drift

### Appointments and Public Booking
- Description: Appointment types, availability, booking link, self-service reschedule/cancel
- UI entry points: `/appointments`, `/settings/appointments`, `/book/[slug]`, `/book/self-service/[orgId]/reschedule/[token]`, `/book/self-service/[orgId]/cancel/[token]`
- API entry points: `/appointments/*` (`apps/api/app/routers/appointments.py`), `/book/*` (`apps/api/app/routers/booking.py`)
- Data models: `Appointment`, `AppointmentType`, `AvailabilityRule`, `AvailabilityOverride`, `BookingLink`, `AppointmentEmailLog`, `ZoomMeeting`, `ZoomWebhookEvent`
- Jobs/queues: `SEND_EMAIL`, `REMINDER`
- External integrations: Google Calendar, Zoom
- Primary risks: double-booking, token leakage, timezone errors

### Forms and Applications
- Description: Form builder, publish, submission tokens, approvals, public applications
- UI entry points: `/automation/forms`, `/automation/forms/[id]`, `/apply/[token]`
- API entry points: `/forms/*` (`apps/api/app/routers/forms.py`), `/forms/public/*` (`apps/api/app/routers/forms_public.py`)
- Data models: `Form`, `FormFieldMapping`, `FormLogo`, `FormSubmission`, `FormSubmissionToken`, `FormSubmissionFile`
- Jobs/queues: `EXPORT_GENERATION`
- External integrations: file storage
- Primary risks: token reuse, attachment safety

### Automation Workflows and Templates
- Description: Workflow builder, triggers, approvals, templates, executions
- UI entry points: `/automation`, `/automation/ai-builder`, `/automation/templates`, `/automation/executions`
- API entry points: `/workflows/*` (`apps/api/app/routers/workflows.py`), `/templates/*` (`apps/api/app/routers/templates.py`)
- Data models: `AutomationWorkflow`, `WorkflowExecution`, `WorkflowTemplate`, `WorkflowResumeJob`, `UserWorkflowPreference`
- Jobs/queues: `WORKFLOW_SWEEP`, `WORKFLOW_EMAIL`, `WORKFLOW_APPROVAL_EXPIRY`, `WORKFLOW_RESUME`
- External integrations: email provider
- Primary risks: trigger loops, approval leakage

### Campaigns, Email Templates, Tracking
- Description: Bulk email campaigns, templates, suppression, open/click tracking
- UI entry points: `/automation/campaigns`, `/automation/campaigns/[id]`, `/automation/email-templates`
- API entry points: `/campaigns/*`, `/email-templates/*`, `/tracking/*`
- Data models: `Campaign`, `CampaignRun`, `CampaignRecipient`, `CampaignTrackingEvent`, `EmailTemplate`, `EmailLog`, `EmailSuppression`
- Jobs/queues: `CAMPAIGN_SEND`, `SEND_EMAIL`
- External integrations: Resend
- Primary risks: suppression compliance, tracking privacy

### Notifications and Alerts
- Description: In-app notifications, alerting, realtime updates
- UI entry points: `/notifications`, `/settings/notifications`, `/settings/alerts`
- API entry points: `/me/notifications*`, `/ops/alerts*`, `/ws/notifications`
- Data models: `Notification`, `UserNotificationSettings`, `SystemAlert`, `IntegrationHealth`, `IntegrationErrorRollup`
- Jobs/queues: `NOTIFICATION`, `REMINDER`
- External integrations: none
- Primary risks: missed or duplicate notifications

### Analytics and Reports
- Description: Dashboards, analytics breakdowns, PDF exports, Meta spend dashboards
- UI entry points: `/dashboard`, `/reports`
- API entry points: `/analytics/*`, `/dashboard/upcoming`, `/ops/sli`, `/admin/exports/analytics`
- Data models: `AnalyticsSnapshot`, `MetaDailySpend`, `RequestMetricsRollup`
- Jobs/queues: `META_SPEND_SYNC`, `ADMIN_EXPORT`
- External integrations: Meta Insights API
- Primary risks: data freshness, query performance

### Search
- Description: Global full-text search across surrogates, notes, attachments, intended parents
- UI entry points: `/search`
- API entry points: `/search` (`apps/api/app/routers/search.py`)
- Data models: `Surrogate`, `EntityNote`, `Attachment`, `IntendedParent`
- Jobs/queues: none
- External integrations: Postgres FTS
- Primary risks: access filters, performance

### AI Assistant and AI Ops
- Description: AI chat (sync/async), summarization, email drafting, schedule parsing, workflow generation
- UI entry points: `/ai-assistant` (`apps/web/app/(app)/ai-assistant/page.tsx`), AI drawer components
- API entry points: `/ai/*` (`apps/api/app/routers/ai.py`)
- Data models: `AISettings`, `AIConversation`, `AIMessage`, `AIActionApproval`, `AIUsageLog`, `AIEntitySummary`, `AIBulkTaskRequest`
- Jobs/queues: `AI_CHAT`
- External integrations: AI providers via `apps/api/app/services/ai_provider.py`
- Primary risks: consent enforcement, PII anonymization, action approval integrity

### Integrations (Meta, Gmail, Calendar, Zoom)
- Description: OAuth connections, Meta lead ingestion and analytics, Zoom meetings
- UI entry points: `/settings/integrations`, `/settings/integrations/meta`, `/settings/integrations/zoom`
- API entry points: `/integrations/*`, `/webhooks/meta`, `/admin/meta-pages`
- Data models: `UserIntegration`, `MetaLead`, `MetaForm`, `MetaFormVersion`, `MetaPageMapping`, `MetaAdAccount`, `MetaCampaign`, `MetaAdSet`, `MetaAd`, `MetaDailySpend`, `ZoomMeeting`, `ZoomWebhookEvent`, `IntegrationHealth`, `IntegrationErrorRollup`
- Jobs/queues: `META_LEAD_FETCH`, `META_CAPI_EVENT`, `META_HIERARCHY_SYNC`, `META_SPEND_SYNC`, `META_FORM_SYNC`
- External integrations: Meta Graph API + CAPI, Gmail/Calendar, Zoom
- Primary risks: webhook verification, token storage, rate limits

### Compliance and Audit
- Description: Audit logs, retention policies, legal holds, data purge, exports
- UI entry points: `/settings/compliance`, `/settings/audit`
- API entry points: `/compliance/*`, `/audit/*`
- Data models: `AuditLog`, `DataRetentionPolicy`, `LegalHold`, `ExportJob`, `EntityVersion`
- Jobs/queues: `DATA_PURGE`, `EXPORT_GENERATION`
- External integrations: none
- Primary risks: retention misconfig, audit chain integrity

### Admin Imports and Exports
- Description: Admin-level config and analytics exports, bulk imports
- UI entry points: `/settings/admin`, `/settings/import`
- API entry points: `/admin/exports/*`, `/admin/imports/*`, `/jobs/*`
- Data models: `ExportJob`, `SurrogateImport`, `Job`
- Jobs/queues: `ADMIN_EXPORT`, `CSV_IMPORT`
- External integrations: none
- Primary risks: large data operations, rollback safety

## 3) End-to-End Flow Maps (Text)

### Lead Intake -> Surrogate -> Match -> Delivery
UI: `/surrogates` -> `/surrogates/[id]` -> `/matches`
API: `/surrogates` -> `/surrogates/{id}/status` -> `/matches`
Data: `Surrogate` -> `SurrogateStatusHistory` -> `Match`
Side effects: activity logs, tasks, notifications
Flow:
```
Lead source (Meta/Form/CSV/Manual)
  -> Create Surrogate (surrogates.py)
  -> Queue/Owner assignment (queues.py, surrogate_access.py)
  -> Status changes + history (surrogates.py, stage_rules.py)
  -> Tasks/Notes/Interviews (tasks.py, notes.py, interviews.py)
  -> Match proposal + acceptance (matches.py)
  -> Appointments + care milestones (appointments.py)
  -> Delivery + terminal stage
```

### Public Application Form -> Profile Sync
UI: `/apply/[token]` -> `/surrogates/[id]` profile tab
API: `/forms/public/{token}/submit` -> `/forms/{form_id}/submissions/*` -> `/surrogates/{id}/profile/sync`
Data: `FormSubmission` -> `SurrogateProfileState`/`SurrogateProfileOverride`
Side effects: audit logs, workflow triggers
Flow:
```
Public form submit
  -> FormSubmission + FormSubmissionFile
  -> Review/approve submission
  -> Profile sync (profile_service)
  -> Surrogate detail updated
```

### Appointment Booking (Public)
UI: `/book/[slug]` -> `/book/self-service/...`
API: `/book/{slug}/slots` -> `/book/{slug}/book` -> `/appointments/{id}`
Data: `Appointment`, `AppointmentType`, `AvailabilityRule`
Side effects: email logs, Zoom meeting creation (optional)
Flow:
```
Public booking page
  -> Slot query
  -> Appointment creation
  -> Email confirmation + reminders
  -> Optional Zoom/Calendar integration
```

### AI Chat -> Proposed Actions -> Approval
UI: `/ai-assistant` drawer
API: `/ai/chat` or `/ai/chat/async` -> `/ai/actions/{approval_id}/approve`
Data: `AIConversation` -> `AIMessage` -> `AIActionApproval`
Side effects: task creation, workflow actions
Flow:
```
User prompt
  -> AI response + proposed actions
  -> Approval record (if needed)
  -> Approved action executes (tasks/workflows/email)
```

### Campaign Send
UI: `/automation/campaigns/[id]`
API: `/campaigns/{id}/send` -> job queue -> `/tracking/*`
Data: `Campaign` -> `CampaignRun` -> `CampaignRecipient` -> `EmailLog`
Side effects: emails sent via Resend, tracking events logged
Flow:
```
Campaign configured
  -> Preview recipients
  -> Send (job queued)
  -> EmailLog + tracking open/click
```

## 4) Findings (Ranked by Severity)

### Critical
- None observed in this pass.

### High
1) Surrogate journey endpoint skips owner-based access checks
- Impact: Any user with `surrogates.view` can read journey data for surrogates outside their ownership rules within the org
- Scenario: Intake specialist fetches journey for a case managed by another user and receives status/milestone history
- Location: `apps/api/app/routers/journey.py:78` (no `check_surrogate_access`), `apps/api/app/services/journey_service.py:316` (org-only filter)
- Recommendation: Add `check_surrogate_access` in `get_surrogate_journey` and/or enforce in `journey_service.get_journey`
- Tests: add access tests to `apps/api/tests/test_journey.py` for owner/role restrictions

2) AI draft email endpoint does not enforce surrogate access rules
- Impact: Users with `AI_USE` can draft emails for surrogates they cannot access
- Scenario: Case manager drafts email for a surrogate owned by another queue/user
- Location: `apps/api/app/routers/ai.py:1360` (surrogate lookup without `check_surrogate_access`)
- Recommendation: Apply `check_surrogate_access` after surrogate load and before prompt construction
- Tests: add `apps/api/tests/test_ai_access.py` or extend `test_ai_contract.py` for access enforcement

3) Job queue processing is not atomic across workers
- Impact: Multiple worker processes can pick the same pending job, causing duplicate side effects (emails, webhooks, AI actions)
- Scenario: Two workers call `get_pending_jobs` concurrently and both process the same `Job`
- Location: `apps/api/app/services/job_service.py:41`, `apps/api/app/worker.py:737`
- Recommendation: Use `SELECT ... FOR UPDATE SKIP LOCKED` or update status in the same query before returning jobs
- Tests: add a concurrency test with two sessions to ensure only one worker claims a job

### Medium
4) AI draft email crashes due to missing PII anonymizer import
- Impact: `POST /ai/draft-email` raises `NameError` before generating content
- Scenario: Any call to `draft_email` reaches `PIIMapping()` without import
- Location: `apps/api/app/routers/ai.py:1348` and `apps/api/app/routers/ai.py:1375`
- Recommendation: Import `PIIMapping`/`anonymize_text` or move anonymization to shared helper
- Tests: add endpoint test for `draft-email` success path (both anonymized and non-anonymized settings)

5) AI dashboard analysis bypasses consent checks
- Impact: AI analysis can run even when consent is required but not accepted
- Scenario: Org has AI enabled but has not accepted consent; `POST /ai/analyze-dashboard` still runs
- Location: `apps/api/app/routers/ai.py:1475`
- Recommendation: Mirror consent checks used in `/ai/chat` and `/ai/summarize-surrogate`
- Tests: add consent gating test in `apps/api/tests/test_ai_access.py`

6) Attachment scanning is not queued when scanning is enabled
- Impact: With `ATTACHMENT_SCAN_ENABLED=true`, files remain quarantined and never scanned unless a manual job runs
- Scenario: Upload file; download is blocked because scan job is only logged
- Location: `apps/api/app/services/attachment_service.py:294`
- Recommendation: Enqueue a scan job in worker (`JobType`) or document and enforce the external cron path
- Tests: add `apps/api/tests/test_media_service.py` coverage for scan-enabled flows

### Low
7) Documentation/version drift across README and frontend docs
- Impact: Conflicting version and stack info can mislead maintainers and release automation
- Scenario: README says version 0.16.0 and docs/agents.md exists; CHANGELOG shows 0.19.3 and file lives at repo root
- Location: `README.md:3`, `README.md:96`, `apps/web/README.md:3`, `apps/api/app/core/config.py:27`, `CHANGELOG.md:6`
- Recommendation: Align README and frontend README to actual versions and file locations
- Tests: none (documentation update)

## 5) Redundancy and Architecture Drift Map
- Duplicate helper: `_type_to_read` in both `apps/api/app/routers/appointments.py` and `apps/api/app/routers/booking.py`
- Duplicate checks/imports: repeated `PIIMapping` import and `check_surrogate_access` calls in `apps/api/app/routers/ai.py` (`summarize_surrogate`), repeated consent check in `draft_email`
- OAuth state handling split between `apps/api/app/routers/auth.py` and `apps/api/app/routers/integrations.py` with similar cookie logic
- Mixed frontend API access patterns: `apps/web/lib/api.ts` wrapper and direct `fetch` in `apps/web/lib/api/*` (inconsistent headers and error handling)

## 6) Pre-Ship Gate Checklist

Top 10 fixes (in order):
1) Add `check_surrogate_access` to journey endpoint
2) Add `check_surrogate_access` to AI draft email
3) Fix `draft-email` PII import crash
4) Enforce AI consent in `analyze-dashboard`
5) Make job claim atomic (`FOR UPDATE SKIP LOCKED` or status update in query)
6) Implement/queue attachment scanning when enabled
7) Add tests for AI access/consent and journey access
8) Add tests for job queue claim behavior
9) Align README + frontend README versions and agents doc location
10) Review documentation drift in `docs/DESIGN.md` vs current code paths

Minimal test plan:
- Backend: `cd apps/api && .venv/bin/python -m pytest -v tests/test_ai_access.py tests/test_journey.py tests/test_media_service.py`
- Backend full: `cd apps/api && .venv/bin/python -m pytest -v`
- Frontend: `cd apps/web && pnpm test --run`

Migration/rollback risks:
- Recent migrations in `apps/api/alembic/versions/20260117_*` update journey featured images and pipeline stage labels; verify downgrade/rollback plan before production release

Observability gaps:
- No explicit queue backlog metrics for `Job` processing (consider gauges for pending/running/failure counts)
- Limited AI latency/usage metrics per route beyond AI usage logs
- No monitoring on attachment scan backlog when scanning is enabled
