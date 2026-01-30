# Changelog

All notable changes to this project will be documented in this file.

## [0.44.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.43.0...surrogacy-crm-platform-v0.44.0) (2026-01-30)

### Features

- Baby gender and weight tracking for surrogate delivery outcome
- Client-safe redacted journey export
- Delivery tracking and future-only scheduling for campaigns
- Enhanced Duo MFA security with state cookies and UA hashing
- Enhanced surrogate import workflow and error reporting
- Workflow engine multi-entity testing support
- Zapier lead ingestion with batch support and auto-mapping
- Modernized Meta integration and OAuth handlers
- Overhauled tasks page with modular components
- Organization AI status sync and improved integration settings UI

### Bug Fixes

- Accessibility and consistency improvements across settings and automation pages
- Preserved handler signature in FailOpenLimiter decorator
- Refined automation page error handling and UI helpers

---

## [0.43.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.42.0...surrogacy-crm-platform-v0.43.0) (2026-01-29)

Consolidated release including changes from 0.19.2 through 0.42.0.

### Major Features

**Multi-Tenant Platform**
- Multi-tenant subdomain routing with org resolution and slug management
- Ops console for platform administration with dedicated subdomain
- Session host validation and wildcard tenant routing
- Organization soft delete with scheduled purge via worker job

**Authentication & Security**
- Duo MFA integration with TOTP fallback
- Double-submit CSRF token pattern
- Platform admin MFA reset capability
- Rate limiter with fail-open behavior and Redis fallback

**Email & Campaigns**
- Resend platform email service with webhook handling
- Email unsubscribe and suppression management
- Email engagement tracking for invites
- Failed recipients tab with retry-failed endpoint

**Meta Integration**
- Meta OAuth infrastructure for Facebook Login for Business
- Meta form mapping and lead conversion UI
- Meta performance analytics with automated reporting
- Ad-level platform breakdown for attribution

**Import & Data Management**
- Import templates with custom field mapping
- AI-assisted CSV import with auto-match and mapping correction
- CSV content storage in DB with backdate flag support
- Cursor-based pagination for high-volume lists

**Workflow & Automation**
- Personal workflow scope with permission-based access control
- Workflow email provider resolution based on scope
- Zapier integration for inbound leads and outbound events
- Cancel match request workflow

**Appointments & Calendar**
- Zoom and Google Meet integration
- Webhook registry for appointment integrations

**AI & Analytics**
- Vertex AI WIF support
- Centralized AI prompts with output validation
- Normalized identity fields for search
- Monitoring endpoints and analytics improvements

**Observability & Infrastructure**
- Health probes and monitoring webhook infrastructure
- GCP Cloud Run deployment with Cloud Build 2nd gen triggers
- Redis pub/sub backplane for WebSocket
- Monitoring alerts, billing budgets, and weekly cost reports

### Bug Fixes

- Stabilized import routing and hardened preview/approval responses
- Fixed org-scoped status change lookup and storage rollback
- Resolved sidebar navigation and org context issues
- TypeScript compatibility for Next.js 15+ params/searchParams
- MFA flow refinements and session persistence fixes

---

## [0.41.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.40.0...surrogacy-crm-platform-v0.41.0) (2026-01-28)

### Breaking Changes

- Full rename of Cases entity to Surrogates across the stack

### Features

- Multi-tenant subdomain routing with org resolution
- Duo MFA integration with TOTP fallback and platform admin reset
- Resend platform email service with webhook handling
- Import templates with custom field mapping
- Health probes and GCP Cloud Run deployment
- Surrogate journey timeline with featured images and PDF export
- Zoom and Google Meet integration for appointments

---

## [0.40.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.39.0...surrogacy-crm-platform-v0.40.0) (2026-01-28)

- Health probes and monitoring webhook infrastructure

---

## [0.38.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.37.0...surrogacy-crm-platform-v0.38.0) (2026-01-27)

- Webhook registry appointment integrations
- Next.js 15+ compatibility updates

---

## [0.37.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.36.0...surrogacy-crm-platform-v0.37.0) (2026-01-26)

- Personal workflow scope with permission-based access control
- Workflow email provider resolution based on scope

---

## [0.36.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.35.0...surrogacy-crm-platform-v0.36.0) (2026-01-26)

- Import templates and custom fields support
- Attachment scanning service (ClamAV)

---

## [0.35.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.34.0...surrogacy-crm-platform-v0.35.0) (2026-01-26)

- Resend configuration API and webhooks
- System email template management UI

---

## [0.34.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.33.0...surrogacy-crm-platform-v0.34.0) (2026-01-25)

- Organization deletion with restore capability
- Platform admin email service

---

## [0.33.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.32.0...surrogacy-crm-platform-v0.33.0) (2026-01-24)

- Duo MFA initiation and platform MFA management
- Org context in invite acceptance flow

---

## [0.32.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.31.0...surrogacy-crm-platform-v0.32.0) (2026-01-24)

- Multi-tenant subdomain infrastructure
- Public org resolution and slug management APIs

---

## [0.31.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.30.0...surrogacy-crm-platform-v0.31.0) (2026-01-22)

- Ops subdomain support with dedicated routing
- Database migration checks in readiness probes

---

## [0.30.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.29.0...surrogacy-crm-platform-v0.30.0) (2026-01-21)

- GCP Cloud Run deployment infrastructure
- Configurable DB connection pooling and Redis client

---

## [0.29.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.28.0...surrogacy-crm-platform-v0.29.0) (2026-01-20)

- Security hardening and ops readiness for launch
- Double-submit CSRF token pattern

---

## [0.28.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.27.0...surrogacy-crm-platform-v0.28.0) (2026-01-18)

- Redis pub/sub backplane for WebSocket
- Monitoring alerts, billing budgets, and weekly cost reports

---

## [0.27.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.26.0...surrogacy-crm-platform-v0.27.0) (2026-01-17)

- Enhanced surrogate import with AI mapping and file hashing
- CSV import backdating support

---

## [0.26.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.25.0...surrogacy-crm-platform-v0.26.0) (2026-01-16)

- Zapier integration for inbound leads and outbound events
- Cancel match request workflow

---

## [0.25.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.24.0...surrogacy-crm-platform-v0.25.0) (2026-01-15)

- Zoom and Google Meet integration for appointments
- Journey timeline with featured images and PDF export

---

## [0.24.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.23.0...surrogacy-crm-platform-v0.24.0) (2026-01-14)

- AI assistant privacy and access controls
- Compliance service with activity tracking

---

## [0.23.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.22.0...surrogacy-crm-platform-v0.23.0) (2026-01-12)

- Surrogate journey timeline
- Tab navigation and activity timeline

---

## [0.22.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.21.0...surrogacy-crm-platform-v0.22.0) (2026-01-11)

- 'Run Now' support for surrogate imports
- Welcome page for new users

---

## [0.21.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.20.0...surrogacy-crm-platform-v0.21.0) (2026-01-10)

- Portal domain support
- Session management page

---

## [0.20.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.2...surrogacy-crm-platform-v0.20.0) (2026-01-09)

- Error boundaries and not-found pages
- Rate limit handling in API client

---

## Pre-Release History (2025-12 - 2026-01)

### [2026-01-05] Workflow Approval System
- Human-in-the-loop approvals with 48 business hours timeout
- Business hours calculator with timezone support
- Email signature enhancement with 5 templates
- Team performance report with per-user conversion funnel analytics
- AI assistant analytics tools with dynamic function calling

### [2026-01-04] Interview Tab
- Interview recording and transcription support
- AI-powered interview summaries

### [2026-01-03] Contact Attempts & Security
- Contact attempts tracking with automated reminders
- Security headers middleware

### [2025-12-31] Profile & Access
- Profile card enhancement with inline editing, sync, hidden fields, and PDF export
- Intake specialist view access for post-approval cases (read-only)

### [2025-12-29] Form Builder & Search
- Complete form builder backend with JSON schema structure
- Token-based secure public form submissions
- Global search command (Cmd+K / Ctrl+K)
- GCP Cloud Monitoring integration

### [2025-12-27] RBAC & Calendar
- Calendar push (two-way sync with Google Calendar)
- Advanced full-text search with PostgreSQL tsvector
- RBAC standardization with centralized ResourcePolicy definitions

### [2025-12-26] MFA & Calendar Tasks
- Multi-factor authentication with TOTP and Duo Web SDK
- Calendar tasks integration
