# Changelog

All notable changes to this project will be documented in this file.

## [0.42.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.41.0...surrogacy-crm-platform-v0.42.0) (2026-01-29)


### Features

* add email domain and phone last4 helpers for ops filtering ([aee5387](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/aee538729c5072b31402997ec827194841f7dc08))
* add email unsubscribe and suppression handling ([b83f4c6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b83f4c6e861e21f403867f3480cd2af07e911d6d))
* add Meta form mapping and lead conversion UI ([c098794](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c09879468b46038b8a49ea6d15644a74e09c6b9a))
* add Meta integration audit logging and sync enhancements ([7415853](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/74158536e00972dc5ae625348808c9afe00ccf9a))
* add Meta OAuth infrastructure for Facebook Login for Business ([9e88bad](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9e88bade81728b25810937fbb2c117203b053330))
* add normalized identity fields for search ([78ec227](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/78ec2272f82f2869267f614394a57835baac54f7))
* add retry-failed endpoint for campaign runs ([d6118d1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d6118d1d6c28c8b96153c71d9b942caf8125597e))
* add Vertex AI WIF support and AI service improvements ([7bb9c33](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7bb9c3342a46fc9da45520db86c47aa89cbccf5d))
* centralize AI prompts and validate outputs ([8477b33](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8477b3393f5f7b04cd09cb81b1c306e96bb21f4d))
* CSV import backdating support for submission timestamps ([8ad5011](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8ad5011bdd7f97af5f85b4ff026d0f553a4b8cc7))
* enhance Meta performance analytics and automated reporting ([7591940](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7591940d7401dbe05ade7e56ba0e2d2b194dd59d))
* improve CSV import with auto-match and mapping correction system ([66f6861](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/66f6861d88ab509f2e6dcc1ef5cfe223093af2d5))
* **web:** add Failed recipients tab to campaign detail view ([d6c5701](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d6c570120c2dac122e3208160e61e27c03b9753d))
* **web:** show backdated badge in tasks awaiting approval ([f547792](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f547792ac47320c4783a6cbda976c9a4781640d4))


### Bug Fixes

* add local org logo serving route (review finding [#4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/issues/4)) ([0cfeb96](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0cfeb96fb6aa5ef5a5d1b44d6f952151e8f064e5))
* **api:** fix column analysis in meta form mapping service and standardize ai_focus imports ([b44b58a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b44b58a3b1b38b9a560f5bda0def317d189b1f9a))
* **api:** fix workflow pause FK and enhance AI interview service ([7f895a4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7f895a4fa5befefa108f60c2484b389355e51813))
* **api:** track original suggestions during Meta form mapping updates ([e9314c9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e9314c913338e0c08db3862dbd16e8841605d603))
* campaign filter_criteria UUID serialization and test mocks ([5e2ad1d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5e2ad1dc17412114164742234bccbd45a30a4570))
* Meta reauth button, reports type errors, and terraform formatting ([4f19b54](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4f19b540abb2bc77892e110b1ce46afb6f25a866))
* org-scoped status change lookup and storage rollback cleanup ([9ac90ff](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9ac90ffdd3a6ea95bbb33027bbea305a4ddea3bb))
* rate limiter fail-open and websocket redis fallback ([e56211f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e56211ff7048426fae2451f253c4823d6485e658))
* **test:** make terraform monitoring config regex whitespace-tolerant ([dd052b1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dd052b1f6fc9431267c3ca167cf5a6b5cdb6ec02))
* **web:** add error states and parallel fetch for review findings [#5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/issues/5),7,8,12,13 ([2e54925](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2e549256b9c50b4afcf2860b175bc98d114ebf8f))


### Maintenance

* add ruff and uv cache directories to gitignore ([bbd7a22](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bbd7a2294272e1122976d1a36c7709e83b755b2e))
* miscellaneous updates and cleanups ([89bfa86](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/89bfa864392e3b2e74fd6bbab89ceb9a48a62330))
* update config, imports, and tests ([273679f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/273679fe41fb2805f2ce7365d451be1bfcc7cf30))
* update refactor logs and fix UI bugs ([a15499d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a15499dc02874d9af446f9a7bc9186e00ec389a1))

## [0.41.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.40.1...surrogacy-crm-platform-v0.41.0) (2026-01-28)


### ⚠ BREAKING CHANGES

* Full rename of Cases entity to Surrogates across the stack.

### Features

**Multi-Tenant Infrastructure**
* Multi-tenant subdomain routing with org resolution and slug management APIs
* Session host validation and wildcard tenant routing
* Ops subdomain support with dedicated routing and session management

**Authentication & Security**
* Duo MFA integration with TOTP fallback and platform admin reset
* Double-submit CSRF token pattern
* Server-side auth gating and org-scoped lookups
* Organization soft delete with scheduled purge via worker job

**Email & Notifications**
* Resend platform email service with webhook handling
* Email engagement tracking for invites
* Email provider resolution based on workflow scope
* Enhanced notification system with browser push support

**Import & Data Management**
* Import templates with custom field mapping
* CSV content storage in DB with backdate flag support
* Personal workflow scope with permission-based access control
* Cursor-based pagination for high-volume lists

**Observability & Infrastructure**
* Health probes and monitoring webhook infrastructure
* GCP Cloud Run deployment with Cloud Build 2nd gen triggers
* Monitoring alerts, billing budgets, and weekly cost reports
* Redis pub/sub backplane for WebSocket

**Core Feature Enhancements**
* Surrogate journey timeline with featured images and PDF export
* Backdated status changes with admin approval workflow
* Zoom and Google Meet integration for appointments
* Activity logging for notes and attachment previews


### Bug Fixes

* Stabilize import routing and harden preview/approval responses
* Org-scoped status change lookup and storage rollback cleanup
* Sidebar navigation and org context issues
* TypeScript compatibility updates for Next.js 15+ params/searchParams
* Various MFA flow refinements and session persistence fixes


### Maintenance

* Archive historical migrations and consolidate into single baseline
* API cleanup and refactors across all components
* Terraform fmt checks and infrastructure hardening
* Docker setup improvements and test coverage expansion

---

## [0.40.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.40.0...surrogacy-crm-platform-v0.40.1) (2026-01-28)

### Bug Fixes

* add missing timezone import to match_service
* rename timezone parameter to tz_name to avoid shadowing datetime.timezone

### Maintenance

* update Docker files to match test requirements

## [0.40.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.39.3...surrogacy-crm-platform-v0.40.0) (2026-01-28)

### Features

* add health probes and monitoring webhook infrastructure
* add health route and observability infrastructure

### Maintenance

* add API dockerignore and docker setup tests
* add URL utils and form field attribute tests

## [0.39.3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.39.2...surrogacy-crm-platform-v0.39.3) (2026-01-28)

### Bug Fixes

* add local proxy settings to env and update sidebar/shell

## [0.39.2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.39.1...surrogacy-crm-platform-v0.39.2) (2026-01-28)

### Bug Fixes

* debug testing improvements

## [0.39.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.39.0...surrogacy-crm-platform-v0.39.1) (2026-01-27)

### Bug Fixes

* add more debug tests

## [0.39.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.38.3...surrogacy-crm-platform-v0.39.0) (2026-01-27)

### Features

* add debug navigation test page

## [0.38.3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.38.2...surrogacy-crm-platform-v0.38.3) (2026-01-27)

### Bug Fixes

* allow .localhost subdomain lookups when PLATFORM_BASE_DOMAIN=localhost
* AppLink fallbackMode adjustments for navigation reliability
* resolve sidebar navigation and org context issues

## [0.38.2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.38.1...surrogacy-crm-platform-v0.38.2) (2026-01-27)

### Bug Fixes

* **web:** move ops subdomain rewrites to next.config.js

## [0.38.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.38.0...surrogacy-crm-platform-v0.38.1) (2026-01-27)

### Bug Fixes

* **web:** regenerate pnpm-lock.yaml to remove duplicate entries

## [0.38.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.37.0...surrogacy-crm-platform-v0.38.0) (2026-01-27)

### Features

* webhook registry appointment integrations

### Bug Fixes

* **deps:** update dependencies and fix TypeScript compatibility
* **web:** improve AppLink navigation and proxy org caching
* **web:** migrate params/searchParams to Promise types for Next.js 15+

## [0.37.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.36.0...surrogacy-crm-platform-v0.37.0) (2026-01-26)

### Features

* **api:** add personal workflow scope with permission-based access control
* **api:** add workflow email provider resolution based on scope

### Bug Fixes

* **web:** refactor tab navigation to use Next.js router instead of history API

## [0.36.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.35.1...surrogacy-crm-platform-v0.36.0) (2026-01-26)

### Features

* **api:** add import templates and custom fields

### Bug Fixes

* **api:** stabilize import routing and harden preview/approval responses

## [0.35.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.35.0...surrogacy-crm-platform-v0.35.1) (2026-01-26)

### Bug Fixes

* **web:** handle optional taskFilter and notes prop types

## [0.35.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.34.6...surrogacy-crm-platform-v0.35.0) (2026-01-26)

### Features

* wildcard tenant routing, UI component extraction, architecture docs

## [0.34.0 - 0.34.6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.33.2...surrogacy-crm-platform-v0.35.0) (2026-01-26)

### Features

* **api:** add multi-tenant subdomain infrastructure
* **api:** add public org resolution and slug management APIs
* **api:** add session host validation for multi-tenancy
* **web:** add multi-tenant subdomain routing

### Bug Fixes

* Multiple ops subdomain authentication and routing fixes
* **web:** replace next/link with AppLink wrapper for navigation reliability

### Maintenance

* **api:** cleanup portal_domain references

## [0.33.0 - 0.33.2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.32.0...surrogacy-crm-platform-v0.33.2) (2026-01-25)

### Features

* **api,web:** add organization context to invite acceptance flow
* **api:** add database migration checks to readiness probes
* **api:** enforce Duo priority over TOTP when enrolled

### Bug Fixes

* **web:** fix SidebarMenuButton Link+Tooltip composition
* **web:** resolve nested interactive element violations

## [0.32.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.31.6...surrogacy-crm-platform-v0.32.0) (2026-01-25)

### Features

* **api:** add email engagement tracking for invites
* **api:** add organization soft delete with restore endpoints
* **api:** add ORG_DELETE worker job handler
* **api:** expand HTML sanitization for email templates
* **api:** refactor Resend webhooks and add platform endpoint
* **web:** add org deletion UI to ops dashboard

## [0.31.0 - 0.31.6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.30.3...surrogacy-crm-platform-v0.31.6) (2026-01-24 - 2026-01-25)

### Features

* **mfa:** refine Duo MFA authentication and UI flow

### Bug Fixes

* **api:** persist upgraded session on MFA completion
* **web:** pass return_to for ops login
* **infra:** update Cloud Run job config and variable documentation
* **web:** refine global styles, layout, and MFA UI improvements
* improve ops invite template UX
* **api:** include resend_count in invite email idempotency key

### Maintenance

* apply API cleanup and refactors across all components

## [0.30.0 - 0.30.3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.29.0...surrogacy-crm-platform-v0.30.3) (2026-01-24)

### Features

* **api:** add Duo MFA initiation and platform MFA management
* **api:** add platform admin MFA reset endpoint
* **web:** update MFA and platform admin UI

### Bug Fixes

* **mfa:** refine Duo authentication flow and UI handling
* **web:** improve Duo callback handling
* **api:** sanitize Duo credentials and add validation tests

## [0.29.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.28.1...surrogacy-crm-platform-v0.29.0) (2026-01-24)

### Features

* **api:** enhance Duo MFA service and router
* **infra:** add Cloud Run job configuration and variable updates
* **web:** update MFA pages and ops layout

### Bug Fixes

* **infra:** update Cloud Run and terraform locals

## [0.28.0 - 0.28.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.27.0...surrogacy-crm-platform-v0.28.1) (2026-01-24)

### Bug Fixes

* restore release-please manifest
* update terraform variables and release-please config

### Maintenance

* test cloud build trigger

## [0.27.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.26.0...surrogacy-crm-platform-v0.27.0) (2026-01-24)

### Maintenance

* **ci:** improve pip-audit guard and test configuration
* update release-please configuration

## [0.26.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.25.2...surrogacy-crm-platform-v0.26.0) (2026-01-23)

### ⚠ BREAKING CHANGES

* Full rename of Cases entity to Surrogates across the stack.

### Features

* **activity:** log note and attachment previews
* rename Cases to Surrogates with pipeline updates
* **analytics:** add Meta analytics enhancement with ad accounts, hierarchy, spend tracking, and forms

## [0.25.0 - 0.25.2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.24.0...surrogacy-crm-platform-v0.25.2) (2026-01-23)

### Features

* **api:** add support session constraints and operational indexes
* **load-tests:** expand k6 coverage with realistic UI flows
* **web:** update appointments, dashboard, calendar, and rich text editor components

### Bug Fixes

* **api:** improve ClamAV scanner detection and error handling
* **api:** improve invite service role handling and display name
* **web:** improve TypeScript types and Link component usage

### Performance Improvements

* **api:** add index on organization_subscriptions status column

## [0.24.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.23.0...surrogacy-crm-platform-v0.24.0) (2026-01-23)

### Features

* **infra:** add monitoring alerts, billing budgets, and weekly cost reports

### Bug Fixes

* **infra:** improve startup probe and Cloud Build trigger configuration
* use Cloud Logging for Cloud Build BYOSA

## [0.23.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.22.1...surrogacy-crm-platform-v0.23.0) (2026-01-22)

### Features

* **api:** add configurable DB connection pooling and Redis client

### Bug Fixes

* CI updated for UV migration

## [0.22.0 - 0.22.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.21.0...surrogacy-crm-platform-v0.22.1) (2026-01-19 - 2026-01-20)

### Features

* **api:** add cursor-based pagination for high-volume lists
* **db:** add indexes for analytics and activity log queries
* **email:** add email service enhancements
* **import:** store CSV content in DB and improve import handling
* **org:** add portal domain support and bootstrap tests
* **realtime:** add Redis pub/sub backplane for WebSocket
* **tasks:** add task service improvements
* **worker:** add job type segregation for priority handling

### Bug Fixes

* **terraform:** use ssl_mode instead of deprecated require_ssl
* **api:** minor router and security fixes

### Performance Improvements

* **analytics:** optimize date queries with expression indexes
* **campaigns:** batch recipient processing and reduce commits
* **worker:** optimize task sweep with SQL date filtering

## [0.21.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.20.0...surrogacy-crm-platform-v0.21.0) (2026-01-19)

### Features

* auto-load app version from release-please manifest

### Bug Fixes

* guard bundle analyzer in prod

## [0.20.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.7...surrogacy-crm-platform-v0.20.0) (2026-01-19)

### Features

* **infra:** add public invoker toggle and improve Docker build
* **infra:** migrate Cloud Build triggers to 2nd gen repository connections

### Bug Fixes

* set cloud build logging to cloud logging only
* use js next config to avoid runtime typescript install

## [0.19.4 - 0.19.7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.3...surrogacy-crm-platform-v0.19.7) (2026-01-18 - 2026-01-19)

### Features

* **analytics:** add monitoring endpoints and improve analytics
* **auth:** improve auth router and MFA service
* **admin:** enhance import/export services
* **infra:** add GCP Cloud Run deployment infrastructure
* **ai:** enhance AI assistant with privacy and access controls
* **attachments:** add attachment scanning service
* **compliance:** enhance compliance service with activity tracking
* **integrations:** enhance OAuth and integrations management
* **jobs:** enhance job service with retry and monitoring
* **journey:** add surrogate journey timeline with featured images and PDF export
* **surrogates:** add actual delivery date tracking
* **surrogates:** add import page and improve surrogate list

### Bug Fixes

* **surrogates:** add agency source and improve list fields
* fix f-string syntax for Python 3.11 compatibility

## [0.19.3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.2...surrogacy-crm-platform-v0.19.3) (2026-01-17)

### Features

* add Zoom and Google Meet integration for appointments
* **matches:** add cancel match request workflow and UI
* **notifications:** enhance notification system
* **surrogate-detail:** add tab navigation and activity timeline

### Bug Fixes

* add missing partial indexes to StatusChangeRequest model
* **chart:** fix ChartContainer rendering in JSDOM tests
* create session record on dev login
* enable dev login from browser

## [0.19.2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.1...surrogacy-crm-platform-v0.19.2) (2026-01-17)

### Features

* add backdated status changes with admin approval workflow
* Add default sorting to entity tables, center align table content
* enforce org-scoped lookups and cross-org isolation for AI/workflow actions
* expand surrogate overview and medical data
* proxy headers, DB-backed idempotency, and server-side auth gating
* security hardening and ops readiness for launch
* **security:** implement double-submit CSRF token pattern

## [0.19.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.0...surrogacy-crm-platform-v0.19.1) (2026-01-15)

### Features

* add IP/match numbering, update docs, fix inline editing

## [0.19.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.18.1...surrogacy-crm-platform-v0.19.0) (2026-01-15)

### ⚠ BREAKING CHANGES

* Full rename of Cases entity to Surrogates across the stack.

### Features

* **analytics:** add Meta analytics enhancement with ad accounts, hierarchy, spend tracking, and forms
* rename Cases to Surrogates with pipeline updates

## [0.18.0 - 0.18.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.17.0...surrogacy-crm-platform-v0.18.1) (2026-01-13)

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

**Developer Experience**
* FastAPI lifespan handler (replaces deprecated `on_event`)
* Dependency upgrades in `requirements.txt`

### Bug Fixes
* **security:** Bump protobuf to 5.29.5 (CVE fix)
* **migrations:** Baseline FK ordering for fresh database installs

### Performance
* Eliminate N+1 queries in analytics, audit, workflow, and template services
* Batch meta_lead checks with `bulk_update_mappings`

## [0.17.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.16.0...surrogacy-crm-platform-v0.17.0) (2026-01-08)

### Features

**Core Surrogacy Force**
* Cases, intended parents, and matches modules with detailed views, activity history, and inline editing
* Queue/ownership system with bulk assignment, priority handling, and org-configurable pipelines
* Unified tasks and calendar with recurrence, reminders, appointments, and booking flows

**Automation & AI**
* Workflow builder (create/edit/test) with approvals and schedule parsing
* AI assistant in case and match views with summaries, smart task creation, and chat context
* Form builder, submissions, and profile sync with PDF exports

**Integrations & Messaging**
* Gmail, Zoom, and Google Calendar integrations plus booking links and meeting creation
* Email templates, signatures, notification preferences, and browser push alerts
* Meta Lead Ads ingestion with conversions API, admin tools, and CSV import

**Analytics & Reporting**
* Dashboard charts, performance and funnel insights, and PDF exports for reports

**Security & Governance**
* RBAC permissions, MFA enforcement, audit trails, and compliance tooling

### Bug Fixes
* Schema hardening for ownership and timestamps, plus appointment buffer and idempotency fixes
* Auth and API hardening (CSRF/CORS/WebSocket) and workflow stability improvements

### Developer Experience
* CI/CD updates, test infrastructure, API client hooks, and observability probes

---

## Pre-Release History (2025-12 - 2026-01)

### [2026-01-05] Workflow Approval System
* Human-in-the-loop approvals with 48 business hours timeout
* Business hours calculator with timezone support (8am-6pm Mon-Fri, respects US federal holidays)
* Email signature enhancement with 5 templates and organization branding
* Team performance report with per-user conversion funnel analytics
* AI assistant analytics tools with dynamic function calling

### [2026-01-04] Interview Tab
* Interview recording and transcription support
* AI-powered interview summaries

### [2026-01-03] Contact Attempts & Security
* Contact attempts tracking with automated reminders
* Security headers middleware (X-Content-Type-Options, X-Frame-Options, COOP, CORP)
* Replaced `manager` role with `admin` throughout codebase

### [2025-12-31] Profile & Access
* Profile card enhancement with inline editing, sync, hidden fields, and PDF export
* Intake specialist view access for post-approval cases (read-only)

### [2025-12-29] Form Builder & Search
* Complete form builder backend with JSON schema structure
* Token-based secure public form submissions
* Global search command (⌘K / Ctrl+K) across cases, IPs, notes
* GCP Cloud Monitoring integration with health probes
* OAuth setup guide documentation

### [2025-12-27] RBAC & Calendar
* Calendar push (two-way sync with Google Calendar)
* Advanced full-text search with PostgreSQL tsvector
* RBAC standardization with centralized ResourcePolicy definitions
* MSW integration testing infrastructure
* SQL consolidation - all router-level SQL moved to service layer

### [2025-12-26] MFA & Calendar Tasks
* Multi-factor authentication with TOTP and Duo Web SDK
* Calendar tasks integration showing tasks with due dates
* Intended parents date filtering
* Schema drift fixes for MFA timestamps
