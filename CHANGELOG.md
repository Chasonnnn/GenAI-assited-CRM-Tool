# Changelog

All notable changes to this project will be documented in this file.

## [0.22.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.21.0...surrogacy-crm-platform-v0.22.0) (2026-01-19)


### Features

* **api:** add cursor-based pagination for high-volume lists ([f0ef13b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f0ef13b65139f677908ff1d9cc78888312fa88cd))
* **db:** add indexes for analytics and activity log queries ([e647930](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e6479302aab34f0e5d9f60b43e5981e3129d594d))
* **email:** add email service enhancements ([f5f24aa](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f5f24aa46e3514ab17f37b7e48d69285e24edef2))
* **import:** store CSV content in DB and improve import handling ([237cedc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/237cedc0537387d1aa81614400843fcb65592bba))
* **org:** add portal domain support and bootstrap tests ([2c1945d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2c1945d06ccef97dec1b82ef2f574dd7919b866d))
* **realtime:** add Redis pub/sub backplane for WebSocket ([e4ee1a5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e4ee1a507b89370b489e0a25f6f41ad2a0da84e3))
* **tasks:** add task service improvements ([96d5256](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/96d525646eaf24c15e709e391582aa506f99d296))
* **worker:** add job type segregation for priority handling ([f317b8d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f317b8d940656ad604b087efcc3956314b75f1f2))


### Bug Fixes

* **api:** minor router and security fixes ([c8d2aec](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c8d2aec0d1cb0a6c7942c7e02911e8a91c782649))


### Performance Improvements

* **analytics:** optimize date queries with expression indexes ([05cca34](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/05cca344266c200e5a9249f0360ca072b06e4909))
* **campaigns:** batch recipient processing and reduce commits ([cf8c7ba](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cf8c7ba36c1142d5b4f14b37aa435fcad459e81b))
* **worker:** optimize task sweep with SQL date filtering ([d35bdd1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d35bdd1995d009399f695108b66173cc7896cfa2))

## [0.21.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.20.0...surrogacy-crm-platform-v0.21.0) (2026-01-19)


### Features

* auto-load app version from release-please manifest ([58e95a5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/58e95a5f73cf383b36636f9939969f7f6f6b52b3))


### Bug Fixes

* guard bundle analyzer in prod ([cce7d8b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cce7d8b9f387f354866c9acdc8114979f32bddf6))

## [0.20.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.7...surrogacy-crm-platform-v0.20.0) (2026-01-19)


### Features

* **infra:** add public invoker toggle and improve Docker build ([b700924](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b700924ec4b8601c4707f49ab9d0925a0ec85a08))
* **infra:** migrate Cloud Build triggers to 2nd gen repository connections ([35157a5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/35157a5b9f00ad352e7e04e32bea8e33ff9f6415))


### Bug Fixes

* set cloud build logging to cloud logging only ([188dfe8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/188dfe8b0742fe6b64c7e1c4a609dd585ef888ab))
* use js next config to avoid runtime typescript install ([6921397](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/69213975b530c9e8a1a9781b49422ed2083b106e))

## [0.19.7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.6...surrogacy-crm-platform-v0.19.7) (2026-01-19)


### Features

* **analytics:** add monitoring endpoints and improve analytics ([b7faaa1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b7faaa187d9dea3d821e0f020d4068e99a01e9e1))

## [0.19.6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.5...surrogacy-crm-platform-v0.19.6) (2026-01-18)


### Features

* **auth:** improve auth router and MFA service ([b7ca5b0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b7ca5b0a6df0b981176db18a974d243c8c3c895d))

## [0.19.5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.4...surrogacy-crm-platform-v0.19.5) (2026-01-18)


### Features

* **admin:** enhance import/export services ([51837fd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/51837fd89f2c0e6a8325f6d1ffcff763088d24c8))
* **infra:** add GCP Cloud Run deployment infrastructure ([1f9fce9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1f9fce9bae2f6e41f19e39ed024352bca9c05ee3))


### Bug Fixes

* fix f-string syntax for Python 3.11 compatibility ([c05a6d1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c05a6d18d5ffcf2b5ec56758c257463e97df61d4))

## [0.19.4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.3...surrogacy-crm-platform-v0.19.4) (2026-01-18)


### Features

* **ai:** enhance AI assistant with privacy and access controls ([ebfa84a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ebfa84a547421823a596f5b8699c7be3c1955e0b))
* **attachments:** add attachment scanning service ([c2b8c6a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c2b8c6a26e957fe699e46e4e58ae349588361ee8))
* **compliance:** enhance compliance service with activity tracking ([c9acc95](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c9acc95a0c8a3f9e990d3586a93179d9ee17952f))
* **integrations:** enhance OAuth and integrations management ([682f6ed](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/682f6ed02212d0bc59d8cabe942a2d740c001d16))
* **jobs:** enhance job service with retry and monitoring ([71191a5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/71191a55f3da12383ffdcd54bbf4e3ebc74b918f))
* **journey:** add surrogate journey timeline ([2f395fb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2f395fb95c1110d3233285ca88666944370a5440))
* **journey:** enhance journey timeline with featured images and PDF export ([761d02a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/761d02a93ea28b646fa78e583a04726fc2561498))
* **surrogates:** add actual delivery date tracking ([b8cf3ce](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b8cf3cef249494a6a497d7613bc079ba81123338))
* **surrogates:** add import page and improve surrogate list ([bc94a3b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bc94a3bf86870df85fe2a4eeea4436697b29312f))


### Bug Fixes

* **surrogates:** add agency source and improve list fields ([dea2807](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dea2807cb8bd733e9bcd57aed1275d24d86d1d09))

## [0.19.3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.2...surrogacy-crm-platform-v0.19.3) (2026-01-17)


### Features

* add Zoom and Google Meet integration for appointments ([f3b8886](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f3b88861e2b593b4b7e94a3b4f77fe7223a47846))
* **matches:** add cancel match request workflow ([e2552d5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e2552d5260e00dd8b7d897ef3dcdf7390056db51))
* **matches:** add cancel match UI ([0ef3282](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0ef328222d335b5870bc4d03c3e5f4a0a45716fa))
* **notifications:** enhance notification system ([ef4c004](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ef4c00495807632e8441a6a1e1b6404108d4ad02))
* **surrogate-detail:** add tab navigation and activity timeline ([9b08885](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9b08885f4fc370ee111f3376fc3ff79388f2a504))


### Bug Fixes

* add missing partial indexes to StatusChangeRequest model ([9805c45](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9805c45913d2d942081a9e8ace9f9faee92d4c25))
* **chart:** fix ChartContainer rendering in JSDOM tests ([d8f453b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d8f453b6968eda1c9e542b478b31ad6fec561566))
* **chart:** improve ResponsiveContainer size handling ([4fcf0d0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4fcf0d036f821e452b3e287f8d0c36de5ebece1a))
* create session record on dev login ([62c295a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/62c295a532f7951eb2d8bacd2ad16c523ab61a2f))
* enable dev login from browser ([0018dee](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0018dee28ce7150a705bd9840c04b565df9c23d0))

## [0.19.2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.1...surrogacy-crm-platform-v0.19.2) (2026-01-17)


### Features

* add backdated status changes with admin approval workflow ([413a1c1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/413a1c16084d4926d18ab54a1c7d93280c2db8e2))
* Add default sorting to entity tables, center align table content, and enable match number sorting in the API. ([f9222fa](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f9222fabfa1adf8b1851d0e10c382067d4e9800c))
* enforce org-scoped lookups and cross-org isolation for AI/workflow actions ([797a621](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/797a621dc95821a4d6004ad4c28849768283a3e6))
* expand surrogate overview and medical data ([11b22a4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/11b22a4aff53490409b2ff2075038a8e0d27347e))
* proxy headers, DB-backed idempotency, and server-side auth gating ([1bc7988](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1bc798866071f45cec1f3832fe5bbfac3188fd94))
* security hardening and ops readiness for launch ([d09ad0e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d09ad0e8a2358aafb4ce96d886da1fd6bc72b935))
* **security:** implement double-submit CSRF token pattern ([80f52e9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/80f52e944759f9ccb7d477eb3f9a32d1ad72f476))

## [0.19.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.0...surrogacy-crm-platform-v0.19.1) (2026-01-15)


### Features

* add IP/match numbering, update docs, fix inline editing ([a68cb3a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a68cb3acecb4534de9917196e87d944dd7e88196))

## [0.19.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.18.1...surrogacy-crm-platform-v0.19.0) (2026-01-15)


### ⚠ BREAKING CHANGES

* Full rename of Cases entity to Surrogates across the stack.

### Features

* **analytics:** add Meta analytics enhancement with ad accounts, hierarchy, spend tracking, and forms ([e2ac503](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e2ac503630b371a5a304a7ae715af2f05db589b0))
* rename Cases to Surrogates with pipeline updates ([186c6f2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/186c6f24499a033eb557a59b820de6dc53fe073e))

## [0.18.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.18.0...surrogacy-crm-platform-v0.18.1) (2026-01-13)

### Bug Fixes
* **migrations:** Fix baseline FK ordering for fresh installs (tables now created in dependency order)
* **migrations:** Add system user for workflow-created tasks
* **migrations:** Fix encrypted column type imports

---

## [0.18.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.17.0...surrogacy-crm-platform-v0.18.0) (2026-01-13)

### Features

**Security & Multi-tenancy**
* Org-scoped queries for task context (user/queue/case lookups)
* Require encryption keys in production config
* Membership soft-delete (`is_active` flag instead of hard delete)

**UI/UX Audit (Phase 1 & 2)**
* Replace 12 `alert()` calls with toast notifications
* New Match dialog with case/IP selectors
* Standardize form input border radius to `rounded-md`
* Replace `LoaderIcon` with `Loader2Icon` across 31 files
* Cancel flow confirmation dialog (destructive action protection)
* Replace raw `<button>` elements with `<Button>` component
* Replace hardcoded hex colors with Tailwind classes

**Developer Experience**
* FastAPI lifespan handler (replaces deprecated `on_event`)
* Dependency upgrades in `requirements.txt`

### Bug Fixes
* **security:** Bump protobuf to 5.29.5 (CVE fix)
* **migrations:** Baseline FK ordering for fresh database installs

### Performance
* Eliminate N+1 queries in analytics, audit, workflow, and template services
* Batch meta_lead checks with `bulk_update_mappings`
* Preload user display names for case status history

## [0.17.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.16.0...surrogacy-crm-platform-v0.17.0) (2026-01-08)

### Features

**Core Surrogacy Force**
* Cases, intended parents, and matches modules with detailed views, activity history, and inline editing.
* Queue/ownership system with bulk assignment, priority handling, and org-configurable pipelines.
* Unified tasks and calendar with recurrence, reminders, appointments, and booking flows.

**Automation & AI**
* Workflow builder (create/edit/test) with approvals and schedule parsing.
* AI assistant in case and match views with summaries, smart task creation, and chat context.
* Form builder, submissions, and profile sync with PDF exports.

**Integrations & Messaging**
* Gmail, Zoom, and Google Calendar integrations plus booking links and meeting creation.
* Email templates, signatures, notification preferences, and browser push alerts.
* Meta Lead Ads ingestion with conversions API, admin tools, and CSV import.

**Analytics & Reporting**
* Dashboard charts, performance and funnel insights, and PDF exports for reports.

**Security & Governance**
* RBAC permissions, MFA enforcement, audit trails, and compliance tooling.

### Bug Fixes
* Schema hardening for ownership and timestamps, plus appointment buffer and idempotency fixes.
* Auth and API hardening (CSRF/CORS/WebSocket) and workflow stability improvements.

### Developer Experience
* CI/CD updates, test infrastructure, API client hooks, and observability probes.

## [2026-01-05]

### Added
- **Workflow Approval System** — Human-in-the-loop approvals for workflow actions
  - Approval tasks with 48 business hours timeout (respects US federal holidays)
  - Business hours calculator with timezone support (8am-6pm Mon-Fri)
  - Action preview with sanitized display (no PII exposure)
  - Owner change invalidates pending approvals
  - Approval expiry sweep job for timed-out tasks
  - ApprovalStatusBadge and ApprovalTaskActions frontend components
  - Migration: `h1b2c3d4e5f6_add_workflow_approval_columns.py`
  - 23 new tests in `test_workflow_approvals.py`

- **Email Signature Enhancement** — Organization branding and templates
  - 5 email-safe templates (classic, modern, minimal, professional, creative)
  - Organization-level branding (logo, primary color, company info)
  - User-editable social media links (LinkedIn, Twitter, Instagram)
  - Logo upload with processing (max 200x80px, <50KB)
  - Backend-rendered signature preview
  - Copy-to-clipboard functionality
  - Admin settings UI for signature branding
  - Migration: `0afc5c98c589_signature_enhancement_org_branding_and_.py`

- **Team Performance Report** — Per-user conversion funnel analytics
  - `/analytics/performance-by-user` endpoint with assignment/conversion metrics
  - Tracks assigned, applied, matched, and lost cases per owner
  - Conversion rate calculation with date range filtering
  - Activity mode for alternative metrics view
  - New frontend components: PerformanceByUserChart, TeamPerformanceCard
  - 9 new tests in `test_analytics.py`

- **AI Assistant Analytics Tools** — Dynamic function calling for analytics queries
  - AI can query team performance data on demand
  - Natural language questions about conversion rates and team performance
  - Context injection for global mode analytics

- **Workflow Approval Notification Preference** — Dedicated notification settings
  - `workflow_approvals` toggle in user notification settings
  - `WORKFLOW_APPROVAL_REQUESTED` notification type
  - Migration: `c5f4e3d2b1a0_add_workflow_approval_notification_pref.py`

### Changed
- Dashboard, analytics, and calendar components now exclude workflow approval tasks from regular counts
- Removed jspdf dependency from frontend

---

## [2026-01-04]

### Added
- **Interview Tab** — Interview transcription and AI analysis workflow
  - Interview recording and transcription support
  - AI-powered interview summaries
  - Performance optimizations for interview loading

---

## [2026-01-03]

### Added
- **Contact Attempts Tracking** — Log and track contact attempts with automated reminders
  - Contact attempt logging with method, outcome, and notes
  - Automated contact reminder check job
  - Case reminder index for efficient queries

### Security
- **Security Headers Middleware** — Added X-Content-Type-Options, X-Frame-Options, COOP, CORP headers

### Changed
- Replaced `manager` role with `admin` throughout the codebase

---

## [2025-12-31]

### Added
- **Profile Card Enhancement** — Inline editing, sync, hidden fields, and PDF export
  - Editable profile fields with inline save
  - Profile visibility toggle (hidden fields)
  - PDF export functionality

- **Intake Specialist View Access** — Intake specialists can now view post-approval cases (read-only)

### Fixed
- Added `idx_cases_reminder_check` index to Case model
- Added `useCreateContactAttempt` mock to case-detail tests
- Override d3-color to >=3.1.0 to fix ReDoS vulnerability

---

## [2025-12-29]

### Added
- **Form Builder Backend** — Complete backend flow for dynamic form creation
  - New database models: `Form`, `FormSubmission`, `FormSubmissionToken`, `FormFieldMapping`
  - JSON schema-based form structure with pages and fields
  - Supported field types: text, email, phone, date, number, select, multiselect, radio, checkbox, file, address
  - Field mapping to automatically update Case data upon approval
  - Token-based secure public form submissions linked to cases
  - File upload with size/count/MIME validation, EXIF stripping, virus scan integration
  - Review workflow: Pending Review → Approved/Rejected
  - Audit logging for form submission events
  - New files: `routers/forms.py`, `routers/forms_public.py`, `schemas/forms.py`, `services/form_service.py`
  - Migration: `a9f1c2d3e4b5_add_form_builder_tables.py`
  - 170 new tests in `test_forms.py`

- **Global Search Command** (⌘K / Ctrl+K)
  - New `SearchCommand` component with keyboard shortcut
  - Searches across cases, intended parents, notes
  - Real-time results as you type
  - Navigation to search results on selection
  
- **GCP Cloud Monitoring Integration**
  - Health probes for Kubernetes readiness/liveness
  - Monitoring configuration for GCP deployment

- **OAuth Setup Guide** — Comprehensive documentation for OAuth integrations
  - Google Calendar, Zoom, Meta Lead Ads setup instructions
  - Environment variable configuration
  - Troubleshooting steps

### Changed
- **Team Settings Enhancement**
  - Added Developer role visibility in team member list
  - Improved UI layout for role badges
  
- **Dashboard Simplification**
  - Streamlined dashboard layout (126 lines reduced)
  
### Fixed
- **Rich Text Editor Scrolling** — Fixed scroll behavior in editor component
  - Added proper overflow handling
  - 62 lines of improvements
  
- **Recipient Preview Card** — Fixed overflow issues in campaign preview
  - Better text truncation and layout handling

- **Search Vector Columns** — Added missing GIN indexes to models
  - Case, IntendedParent, EntityNote, Attachment now have proper search_vector columns
  - Fixed search page import path

---

## [2025-12-27] (Evening)

### Added
- **Calendar Push (Two-way Sync Complete)** — Push appointments to Google Calendar
  - Appointments are now created in Google Calendar when approved
  - Reschedules update the Google Calendar event
  - Cancellations delete the Google Calendar event
  - Two-phase commit: appointment saved first, then best-effort sync
  - Uses client timezone for event times (falls back to org/UTC)
  - Handles missing/expired tokens gracefully (logs warning, continues)
  - `calendar_service.py`: Added `timezone_name` parameter
  - `appointment_service.py`: Added `_run_async()` helper, `_sync_to_google_calendar()` helper

- **Advanced Search** — Full-text search across cases, notes, attachments, intended parents
  - PostgreSQL tsvector columns with GIN indexes
  - Auto-update triggers for insert/update
  - HTML tag stripping for notes (via `regexp_replace`)
  - Uses `simple` dictionary (no stemming) for names/emails
  - Backfill for existing rows
  - New files:
    - `alembic/versions/5764ba19b573_add_fulltext_search.py`
    - `services/search_service.py` — `global_search()` function
    - `routers/search.py` — `GET /search` endpoint
  - Features:
    - Org-scoped results
    - Permission-gated (notes require `view_case_notes`, IPs require `view_intended_parents`)
    - Ranked by relevance
    - Snippets via `ts_headline()` with highlights
    - `websearch_to_tsquery()` with `plainto_tsquery()` fallback

## [2025-12-27] (Afternoon)

### Added
- **RBAC Standardization** — Complete refactoring of permission system
  - New `policies.py` with centralized `ResourcePolicy` definitions
  - `PermissionKey` enum for type-safe permission references
  - `require_any_permissions()` and `require_all_permissions()` helpers
  - All 20 routers now use policy-driven dependencies
  - RBAC regression matrix tests (`test_rbac_policies.py`)
  
- **MSW Integration Testing Infrastructure**
  - Mock Service Worker (MSW) for intercepting API calls in tests
  - `tests/mocks/handlers.ts` with data factories
  - `tests/utils/integration-wrapper.tsx` with real QueryClientProvider
  - Separate `vitest.integration.config.ts` for integration tests
  - Example integration test for permissions page
  - New npm scripts: `test:integration`, `test:all`

### Refactored
- **SQL Consolidation** — All router-level SQL moved to service layer
  - New services: `ai_service.py`, `match_service.py`, `queue_service.py`, `membership_service.py`, `meta_page_service.py`
  - Updated services: `analytics_service.py`, `audit_service.py`, `note_service.py`, `task_service.py`, `invite_service.py`, `alert_service.py`, `org_service.py`, `user_service.py`
  - **AI router**: Entity lookups, approvals, conversations, notes/tasks, dashboard counts → `ai_service`
  - **Matches router**: Match queries, events, batch loading → `match_service`
  - **Queues router**: CRUD, claim/release, member management → `queue_service`
  - **All other routers**: Thin HTTP handlers delegating to services
  - Pattern: Routers handle HTTP concerns only; services own all SQL/ORM queries

- **Analytics Service Centralization**
  - Unified `analytics_service.py` now provides shared computation for:
    - `parse_date_range()` — consistent date parsing across endpoints
    - `get_analytics_summary()` — high-level KPIs
    - `get_cases_by_status()` / `get_cases_by_assignee()` — breakdown stats
    - `get_cases_trend()` — time-series data
    - `get_meta_performance()` / `get_meta_spend_summary()` — Meta Lead Ads metrics
  - `analytics.py` router now calls service functions instead of inline queries
  - `admin_export_service.py` uses analytics_service for all analytics data
  - `admin_exports.py` uses analytics_service for date parsing and Meta spend
  - PDF export now uses same computation path as API endpoints

### Changed
- Permission checks shifted from role-based to permission-based approach
- Test expectations updated: unauthenticated requests now return 401

### Test Coverage
- **Frontend Unit**: 80 tests passing
- **Frontend Integration**: 3 tests passing (new)
- **Backend**: 267 tests passing
- **Total**: 350 tests

---

## [2025-12-26] (Evening)

### Added
- **Multi-Factor Authentication (MFA)**
  - TOTP-based 2FA with QR code enrollment
  - 8 single-use recovery codes (hashed storage)
  - Duo Web SDK v4 integration
  - MFA enforcement during login flow
  - `/mfa/complete` endpoint upgrades session after verification
  - Security settings page at `/settings/security`
  
- **Calendar Tasks Integration**
  - UnifiedCalendar now displays tasks with due dates
  - Month/Week/Day views show tasks alongside appointments
  - Task filter support (My Tasks toggle)
  - Color-coded legend for appointments vs tasks
  
- **Intended Parents Date Filtering**
  - `created_after`/`created_before` API parameters
  - Frontend date range picker on IP list page

### Fixed
- **Schema Drift Issues**
  - MFA timestamps now use `DateTime(timezone=True)`
  - `tracking_token` unique index properly defined in model
  - Migration `d70f9ed6bfe6` uses `DROP INDEX IF EXISTS`
  
- **Base UI Button Warnings**
  - Standardized dropdown triggers to use native buttons
  - Replaced Button components with buttonVariants + spans
  - No more "not rendered as native button" warnings
  
- **Match Detail Page**
  - No longer fetches unfiltered tasks while loading
  - Rejection now invalidates match queries
  
- **Task Date Bucketing**
  - Uses local date parsing to avoid timezone skew
  
- **Cases Page**
  - Reset button clears date range filters
  - Shows Reset when date filter is active
  
- **Settings Page**
  - Hydrates org settings + user/org names on load
  - Removed unsupported profile phone field

### Security
- **Server-side HTML Sanitization**
  - Notes sanitized via `note_service.sanitize_html()` (uses nh3)
  - Match notes explicitly sanitized in create/accept/reject/update

### Test Coverage
- **Frontend**: 80 tests passing
- **Backend**: 241 tests passing (0 warnings)

---

## [2025-12-27] (Late Night)

### Added
- **Workflow Editor Validation**
  - Validates required fields before wizard step advancement
  - Checks trigger type, action types, email templates, task titles
  - Resets/hydrates state per edit session
  
- **Reports/Analytics Improvements**
  - Local date formatting for filters
  - Error states for funnel chart, map chart, and PDF export
  - Tooltip now renders zero values correctly
  - Campaign filter shows clearer labeling

### Fixed
- **Match Detail Improvements**
  - Notes use `updated_at` for accurate timestamp ordering
  - Files tab has "Upload File" action button
  - Add Note / Reject Match dialogs reset state on close (overlay/ESC)
  - Prevent IP task queries when ipId is missing
  - Local date parsing for DOB/due dates
  
- **Execution History**
  - Button now routes to `/automation/executions` global page
  - Pagination resets on filter changes
  
- **Email Templates**
  - DOMPurify sanitization for template/signature previews
  
- **Legacy Route Cleanup**
  - Removed `/matches/[id]` in favor of `/intended-parents/matches/[id]`
  
- **Intended Parents List**
  - Added `isError` handling with proper error UI
  
- **SQLAlchemy Test Warning**
  - Fixed "transaction already deassociated" warning in conftest.py

## [2025-12-26]

### Fixed
- **AI Bulk Tasks Permission**: Changed `require_permission("manage_tasks")` → `create_tasks`
  - `manage_tasks` didn't exist in PERMISSION_REGISTRY, causing 403 errors
  
- **Match Event Validation**: Added proper validation for all-day vs timed events
  - `all_day=True` now requires `start_date`
  - `end_date` must be >= `start_date`
  - Timed events require `starts_at`
  - `ends_at` must be >= `starts_at`
  
- **Match Event Date Filtering**: Multi-day all-day events now appear in date range queries
  - Uses overlap logic instead of start_date only
  
- **Campaign Wizard**: Restructured from 4 to 5 steps
  - Step 4: Preview Recipients (summary + RecipientPreviewCard)
  - Step 5: Schedule & Send (schedule options + confirm button)
  
- **Page Height Consistency**: Fixed IP list + Matches page scroll issues
  - Changed `min-h-screen` → `h-full overflow-hidden`
  
- **Campaign Recipient Preview**: Fixed `stage.name` → `stage.label` bug
  - PipelineStage uses `label` attribute, not `name`

### Added
- `test_match_events.py` - Event validation and range overlap tests
- `test_ai_bulk_tasks.py` - Case manager permission check tests
- Frontend templates page tests (4 new tests)

### Test Coverage
- **Frontend**: 78 tests passing
- **Backend**: 147 tests passing
- **Total**: 225 tests

---

## [2025-12-24]

### Added
- Template Marketplace with workflow templates
- Frontend template configuration modal for email action setup
- Campaign wizard improvements

### Fixed
- `send_notification` action kwargs mismatch
- Google Calendar integration field name (`provider` → `integration_type`)
- Cancelled campaigns still executing
- Campaign scheduling for "later" option
- Booking links org_id scoping
- Document upload trigger for intended-parent attachments
- `useDashboardSocket` re-render issue
