# agents.md — Surrogacy CRM Platform (Multi-tenant, Open-source Ready)

This document is the single source of truth for how we build this project: architecture, conventions, workflows, and rules that every contributor (human or AI agent) must follow.

## 0) Project Summary

We are building an **in-house CRM + case management platform** for a surrogacy agency, with the ability to **scale to multiple companies (multi-tenant)** and be **open-source ready** (a general version that can be customized per organization).

Primary user roles (per organization):
- **Manager** (full access, dashboards, assignments)
- **PR / Intake** (lead pipeline management, initial screening, assignments)
- **Specialist** (case workflow tracking, notes, important dates)

Core modules:
- Leads (surrogate applicants, including Meta Lead Ads ingestion)
- Intended Parents CRM (profiles used for matching)
- Cases (specialist workflow: waiting → matched → transfer → pregnant → delivered)
- Notes + Important Dates
- Notifications
- Analytics/Reports
- Optional AI assistant for summaries/drafts/analysis

## 1) High-level Goals

### V1 (MVP) Goals
- Secure login with org-based roles
- Multi-tenant data isolation (organization_id on all domain entities)
- Leads pipeline (create, update, status changes, assign)
- Intended parents store & basic filtering
- Case workflow for specialists + notes + important dates
- Manager dashboards (counts by period/status)
- Meta Lead Ads ingestion (webhook + fetch details + store)
- In-app notifications
- Mobile-friendly UI

### V1 Non-Goals (Do NOT over-engineer)
- Custom field builder (dynamic schema per tenant)
- Arbitrary workflow builder for any industry
- Plugin architecture / event bus / webhooks-as-a-product
- Full white-label theming engine
- Auto-sending AI emails without human review

## 1.1) Open-source & Generalizability Goals

We aim to keep the codebase **generalizable** so an open-source “core CRM” can exist without being tightly coupled to one agency’s process.

- Prefer **configuration** (org settings, templates, rubrics, stages) over forks.
- Avoid hard-coding surrogacy-only assumptions into shared core logic; isolate domain specifics behind configuration or clearly named modules.
- Keep multi-tenancy and authorization rules identical across all verticals.

## 1.2) Development Rules

### **No Backward Compatibility** - Break Old Formats Freely
- This is an in-house, rapidly evolving project.
- **Breaking changes are acceptable** - prioritize better design over maintaining old formats.
- When improving data structures, API contracts, or database schemas, make the cleanest change without worrying about backward compatibility.
- Users can re-migrate, re-sync, or update their integrations as needed.
- Focus on **current best practices**, not legacy support.

### **Version Numbering Scheme** - a.bc.de Format
The application uses a 3-part version format: **a.bc.de**

| Part | Range | Meaning |
|------|-------|---------|
| **a** | 0-9 | Major version (0 = pre-release/development) |
| **bc** | 00-99 | Feature version (major feature additions) |
| **de** | 00-99 | Patch version (bug fixes, minor changes) |

Examples:
- `0.06.00` → Pre-release, 6 major features, no patches
- `1.00.00` → First production release
- `1.02.05` → Production v1, 2 features since 1.0, 5 patches

**When to increment:**
- **a (major):** Breaking API changes or production-ready milestone
- **bc (feature):** New feature completion (e.g., audit trail, versioning)
- **de (patch):** Bug fixes, documentation, minor improvements

Current version is defined in `apps/api/app/core/config.py` as `Settings.VERSION`.


## 2) Tech Stack (Target)

### Frontend
- Next.js (App Router), React Server Components when useful
- TypeScript (strict)
- Tailwind CSS + shadcn/ui
- TanStack Query (server state/cache)
- Zustand (UI state only)
- React Hook Form + Zod (client validation)

### Backend
- FastAPI
- Pydantic v2
- PostgreSQL (Supabase for managed hosting)
- ORM + migrations (SQLAlchemy + Alembic OR SQLModel + Alembic)
- Cookie-based session auth (JWT in HTTP-only cookie) + Google OAuth (Workspace SSO)

### Optional (Later)
- Redis + background jobs (Celery/RQ/Arq) if we need queues/reminders at scale
- Docker compose for consistent dev env
- Playwright for E2E smoke tests

## 3) Repo Layout

Single repository with two apps:
/backend
/app
/api        # FastAPI routers grouped by domain
/core       # config, security, logging
/db         # engine/session, migrations setup
/models     # ORM models (DB)
/schemas    # Pydantic models (DTO)
/services   # domain logic; keep routers thin
/utils
/tests
pyproject.toml (or requirements.txt)
alembic.ini
/alembic

/frontend
/app
/(auth)     # login, etc.
/(app)      # authenticated area
/components   # shared UI
/lib          # api client, auth helpers, query keys
/styles
package.json
tsconfig.json

## 3.1) Navigation & Modules (V1 contract)

We implement features as **modules** (enabled per org) and present them as **tabs** (shown per role).

V1 “real” tabs (build first):
- Home (calendar + quick actions + my work)
- Cases (unified pipeline: new → delivered, role-filtered)
- Reports
- Settings

V1-lite tabs (simple versions early; expand later):
- Inbox/Notifications
- Tasks
- Activity (org-scoped timeline/audit)

Later/optional modules:
- Templates (email/snippets/checklists)
- Automation (follow-ups, SLAs, assignment rules)
- Integrations (Meta Lead Ads, email providers, calendar, SMS/telephony)
- Import/Export and Dedupe tools
- Contacts/Directory

Role defaults (can be adjusted by org policy):
- Manager: Home, Cases, Reports, Inbox, Tasks, Activity, Settings
- PR/Intake: Home, Cases (Stage A only), Inbox, Tasks, Activity
- Specialist/Case Manager: Home, Cases (full pipeline), Inbox, Tasks, Activity

## 4) Local Development Setup (Suggested)

### Prereqs
- Node.js LTS (>= 20 recommended)
- pnpm (recommended) or npm
- Python >= 3.11 (3.12 ok)
- Postgres (local) OR Supabase project for dev
- Optional: ngrok / Cloudflare Tunnel for webhook dev

### Environment Variables
- Never commit real secrets.
- Keep `.env.example` up to date for both apps.

Backend `.env` example:
- `DATABASE_URL=postgresql+psycopg://...`
- `JWT_SECRET=...`
- `JWT_SECRET_PREVIOUS=` (optional for rotation)
- `JWT_EXPIRES_HOURS=4`
- `GOOGLE_CLIENT_ID=...`
- `GOOGLE_CLIENT_SECRET=...`
- `GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback`
- `ALLOWED_EMAIL_DOMAINS=example.com` (optional)
- `CORS_ORIGINS=http://localhost:3000`
- `FRONTEND_URL=http://localhost:3000`
- `DEV_SECRET=...` (dev-only)
- `META_APP_SECRET=...`
- `META_VERIFY_TOKEN=...`
- `META_PAGE_ACCESS_TOKEN=...` (or a secure token store later)

Frontend `.env.local` example:
- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- (Avoid putting secrets into NEXT_PUBLIC_*.)

## 5) Engineering Rules (Non-negotiable)

### 5.1 Multi-tenancy rules
- Every domain entity MUST include `organization_id`:
  - leads, intended_parents, cases, notes, events/dates, notifications, analytics snapshots, etc.
- Every query MUST scope by organization:
  - `WHERE organization_id = current_org_id`
- This project uses **one organization per user account**:
  - `User` is identity
  - `Membership` is authorization context and enforces `UNIQUE(user_id)`
  - `org_id` is derived from the authenticated session (not from client-supplied org headers)

### 5.2 Authorization rules
- Do not scatter `if role == "x"` across routers.
- Use centralized dependencies/helpers, e.g.:
  - `require_roles(["manager", "intake"])`
  - `require_membership()`
- Enforce both:
  - user authentication
  - membership in org
  - role permission for action

### 5.2.1 Cookie sessions + CSRF
- Auth is cookie-based; API requests from the frontend must use `credentials: "include"` (or equivalent).
- For state-changing requests, require a simple CSRF header (e.g. `X-Requested-With: XMLHttpRequest`) and validate it in a centralized dependency.

### 5.3 Data safety / privacy
This domain may include sensitive PII and potentially health-related info.
- Avoid logging raw PII in server logs.
- Webhook payloads may include sensitive data: store carefully and consider redaction.
- AI features must:
  - minimize transmitted data
  - require human review before sending outbound messages
  - log requests/responses for auditing (without leaking secrets)

### 5.4 API design
- Prefer RESTful endpoints with predictable resources:
  - `/auth/google/login`, `/auth/me`, `/auth/logout`
  - `/orgs`, `/orgs/:id` (admin-only if needed)
  - `/leads`, `/leads/:id`, `/leads/:id/status`, `/leads/:id/assign`
  - `/parents`, `/cases`, `/notes`, `/events`, `/notifications`
- Pagination required for list endpoints.
- Filterable fields should be query params: `status=`, `assigned_to=`, `q=`, `from=`, `to=`.
- API responses should be stable and typed (Pydantic schemas).

### 5.5 Frontend state rules
- TanStack Query is the source of truth for server data (leads/cases/parents/notifications).
- Zustand is for UI-only state:
  - sidebar open/close, theme, layout prefs
- Avoid duplicating server state into Zustand.
- Prefer Server Components for data-heavy pages when it simplifies things, but:
  - Use Client Components for forms, tables with heavy interactions, modals.

## 6) Domain Model (V1)

### Core entities
- Organization
- User
- Membership (user/org/role)
- Lead (surrogate applicants initially; we may later generalize)
- IntendedParent
- Case
- Note (generic: entity_type + entity_id)
- Event / ImportantDate (generic: entity_type + entity_id)
- Notification

### Status enums (V1)
LeadStatus:
- `new`
- `contacted`
- `followup_needed`
- `application_review`
- `approved`
- `not_qualified`

CaseStatus (Intake Pipeline + Post-Approval):
- `new_unread` (initial status)
- `contacted` (intake reached out)
- `qualified` (intake confirmed applicant is a good lead) ← triggers Meta CAPI
- `applied` (applicant submitted full application form)
- `followup_scheduled`
- `application_submitted`
- `under_review`
- `approved` (case approved, intake reviews before handoff)
- `pending_handoff` (intake submits to case manager)
- `disqualified`
- Post-Approval (case_manager+ only):
  - `pending_match`, `meds_started`, `exam_passed`, `embryo_transferred`, `delivered`
  - `archived` (soft-delete pseudo-status)

## 7) Meta Lead Ads Integration (Rules)

We ingest leads from Meta via webhook.
- Webhook endpoints must:
  - support Meta verification challenge (GET verification)
  - validate signature/verify token where applicable
- Process pattern:
  1) Receive webhook event (leadgen id/form id/page id)
  2) Fetch lead details from Meta API using server-side token
  3) Map fields → Lead schema
  4) Upsert by `meta_lead_id` (dedupe)
  5) Log outcome (success/failure); retry failures later

Do NOT block webhook response on long processing; keep it fast if possible.

## 8) AI Assistant (V1 rules)

AI features are assistive and must be safe.
Allowed initial capabilities:
- Summarize a lead/case history
- Suggest next actions
- Draft emails/messages (user must review/edit)
- Explain analytics trends in plain language

Forbidden in V1:
- Auto-sending messages without human approval
- Making final eligibility decisions automatically

Implementation guideline:
- Backend endpoints like `/ai/summarize-lead`, `/ai/draft-email`
- Enforce org + role scoping
- Redact/minimize sensitive fields sent to the model
- Store an audit record of prompts/outputs (safe subset)

Additional rules (provider + keys + governance):
- AI must be **optional** and **off by default**.
- Support a provider abstraction (e.g., OpenAI first) so we can switch/extend providers later without rewriting features.
- Prefer BYOK: **organization-managed keys**, stored in the DB **server-side** (encrypted at rest) and never exposed to the browser.
- Key handling rules:
  - Keys are **write-only**: the UI can set/rotate/test a key, but never displays the full value again (show masked last-4 + created_at).
  - Only `manager` (or org admin) can create/update/disable keys.
  - Backend must never return keys in API responses and must never log them.
  - Support rotation (keep “active key id” per org) and an immediate “disable AI” kill switch.
- Treat classification/qualification as **AI recommendation** (reasons + confidence + rubric signals) until a user confirms a final status/decision.

## 9) Code Style & Quality

### Backend
- Keep routers thin; business logic in services.
- Prefer explicit transactions for multi-step writes.
- Use timezone-aware UTC datetimes.
- Errors: return meaningful HTTP codes; Pydantic handles validation errors.

Recommended tooling:
- ruff (lint/format)
- mypy (optional)
- pytest (tests)

### Frontend
- Strict TypeScript.
- Use shared `apiClient` wrapper that attaches auth token and handles 401.
- Use typed query keys.
- Prefer composable components.

Recommended tooling:
- ESLint + Prettier
- typecheck in CI

## 10) Testing Strategy (Pragmatic)

V1 minimum:
- Backend: unit tests for key services + auth + multi-tenant scoping
- Frontend: smoke test the most important pages and forms (optional early)
- E2E later: Playwright minimal flows:
  - login → leads list → lead detail → status change

## 11) How Agents Should Work (Human or AI)

Before coding:
1) Read existing code in affected areas.
2) Propose a short plan: files to touch, migrations needed, edge cases.
3) Keep PRs small and incremental.

While coding:
- Do not introduce new libraries unless necessary.
- Do not refactor unrelated code in feature PRs.
- Preserve multi-tenant and permission rules.

Before finishing:
- Run formatting + lint + tests.
- Update `.env.example` if new vars are introduced.
- Update docs if behavior changes.

Deliverable format for agent responses:
- Summary of changes
- Files changed
- Commands run (and results)
- Next steps / TODOs

## 12) Deployment Notes (Target)

- Frontend: Vercel (or equivalent)
- Backend: Render/Railway/Fly.io
- DB: Supabase Postgres

Constraints:
- Webhooks require a stable public HTTPS URL.
- CORS must be restricted to the frontend origin in production.

## 13) Current Status (Update regularly)

- **Date:** 2025-12-16
- **Completed:**
  - Project scaffolding (monorepo with apps/api + apps/web)
  - PostgreSQL 16 via Docker Compose
  - FastAPI with health endpoint + DB connectivity check
  - SQLAlchemy 2.0 + Alembic migrations configured
  - Next.js 16 with App Router and (app) route group
  - Basic app layout (sidebar + topbar)
  - **Week 2 complete:** Authentication & tenant isolation
    - Google OAuth SSO with state/nonce/user-agent binding
    - Invite-only access (one pending invite per email globally)
    - JWT sessions in HTTP-only cookies with key rotation
    - Role-based authorization
    - Strict tenant isolation via Membership (one org per user)
    - CLI bootstrap (`python -m app.cli create-org`)
    - Dev endpoints (`/dev/seed`, `/dev/login-as`)
  - **Week 3 complete:** Cases module (backend)
    - 4 roles: intake_specialist, case_manager, manager, developer
    - Cases table with sequential numbering, soft-delete, status history
    - Phone normalization (E.164), state validation (2-letter codes)
    - Notes (2-4000 chars), tasks (with due dates/completion)
    - Meta leads ingestion skeleton
    - All CRUD endpoints with pagination (max 100), search, filters
  - **Week 4 complete:** Frontend UI (v0 design implementation)
    - Login page (Duo SSO + username option, glassmorphism, watercolor gradient)
    - Dashboard (stats cards, charts with recharts, recent activity)
    - Cases List (filters, search, table, pagination)
    - Case Detail (tabs, status updates, notes)
    - Tasks page (grid layout, filters, priority badges)
    - Intended Parents (list, filters, actions, pagination)
    - Reports (4 chart types, quick stats, export)
    - Settings (5 tabs: Profile, Org, Notifications, Integrations, Security)
    - Automation (Workflows + Templates tabs)
    - App Sidebar with navigation and user menu
    - Loading skeletons for all pages
    - All pages use shadcn/ui components with responsive Tailwind classes
  - **Week 5 complete:** Frontend-Backend Integration
  - **Week 5b complete:** Workflow automation + email foundation
  - **Week 6 complete:** Intended Parents module + handoff workflow + case enhancements
  - **Week 8 complete:** In-App Notifications + Theme System
  - **Week 9 complete:** Meta Lead Ads Integration + CAPI
  - **Week 10 complete:** Ops Console + Manager Analytics
  - **Week 10+ complete:** AI Assistant Tab + Meta Ads Spend Integration + UI Refinements
  - **Enterprise Features (v0.06.00):**
    - Global Audit Trail (hash chain, tamper-evident)
    - CSV Import with Email Dedupe
    - Org-Configurable Pipelines (stage labels, colors, order)
    - In-App Version Control (encrypted snapshots, rollback)
- **Current Version:** 0.06.00
- **In progress:** None
- **Blockers:** None
- **Next milestones:** Deployment + hardening

### Enterprise Features (2025-12-17, v0.06.00)
- **Completed:**
  - Global Audit Trail with hash chain (tamper-evident logging)
  - CSV Import with email-based duplicate detection
  - Org-Configurable Pipelines (relabel, recolor, reorder statuses)
  - In-App Version Control for configurations:
    - Pipelines, Email Templates, AI Settings
    - Encrypted snapshots (Fernet), SHA256 checksums
    - Rollback = new version from old payload (never rewrite history)
    - API keys stored as [REDACTED] (never versioned)
    - Developer-only access for /versions and /rollback
  - Admin Versions API (`/admin/versions/{type}/{id}`)

### Week 10+ (2025-12-16): AI Assistant Tab + Meta Ads Spend + UI Refinements
- **Completed:**
  - AI Assistant page (`/ai-assistant`) with ChatGPT-style layout
  - `ai_enabled` feature toggle on Organization model
  - AI sidebar link conditional on org's `ai_enabled` setting
  - Meta Ads Spend endpoint (`GET /analytics/meta/spend`)
  - `fetch_ad_account_insights()` in meta_api.py
  - Ad Spend summary card in Reports dashboard (total spend, CPL)
  - Circle blur theme toggle animation (View Transitions API)
  - Global font changed to Noto Sans
  - DateRangePicker UX improvements (stays open during selection)

### Week 6 (2025-12-14): Intended Parents Module + Dependencies
- **Completed:**
  - Intended Parents CRUD (full name, email, phone, state, budget)
  - Status workflow with history tracking
  - Archive/restore with status preservation and duplicate email check
  - State/phone normalization validators in Pydantic schemas
  - Polymorphic EntityNotes supporting both Cases and IPs
  - CSRF protection on all IP mutation endpoints
  - Frontend: IP list page with filters, detail page with tabs
- **Dependencies upgraded:**
  - Next.js 16.0.10, React 19.2.3, Zod 4.1.13, recharts 3.5.1
  - All Radix UI components to latest versions
  - Base UI combobox/pagination fixed for render prop compatibility
  - ChartTooltipContent/ChartLegendContent rewritten for recharts 3 API

### Week 6c (2025-12-15): Case Management Enhancements
- **Completed:**
  - Priority cases with `is_priority` field and gold highlighting
  - Comprehensive CaseActivityLog model (12 activity types)
  - Activity service with helper functions for each type
  - Assignment tracking captures from→to on reassignment
  - GET /cases/{id}/activity endpoint (paginated)
  - GET /cases/assignees endpoint for user picker
  - POST /cases/bulk-assign endpoint (case_manager+ role)
  - Multi-select UI with checkboxes and floating action bar
  - Activity Log tab (renamed from Status History)
  - Case inline editing dialog
  - Permission alignment: case_manager can now assign cases
  - All roles can archive cases (ROLES_CAN_ARCHIVE updated)

### Week 8 (2025-12-15): In-App Notifications + Theme System
- **Completed:**
  - Notification model with dedupe_key, read_at, org-scoping, proper indexes
  - UserNotificationSettings model (per-user toggles for 4 notification types)
  - NotificationType enum (6 types: case/task events)
  - Notification service with create, list, count, mark_read, settings
  - Triggers integrated into case_service.py and task_service.py
  - Notifications router with 6 endpoints under /me/
  - ThemeProvider using next-themes (system/light/dark)
  - ThemeToggle dropdown in header
  - Stone base + Teal theme colors for both light and dark modes
  - NotificationBell component with unread badge and dropdown
  - Notifications page (/notifications)
  - Settings page wired to real notification settings API
  - 30-second polling for unread count
- **Bug fixes:**
  - DropdownMenuLabel Menu.Group error
  - Cases table scroll (header/filters fixed)
  - mark_read() org_id for tenant isolation
  - Dedupe query org_id + user_id for multi-tenancy

### Week 9 (2025-12-16): Meta Lead Ads Integration ✓ COMPLETE
- **Completed:**
  - Webhook endpoint with HMAC signature verification
  - Meta API client (fetch lead details, appsecret_proof)
  - Auto-conversion: Meta leads → Cases (source=META)
  - Campaign tracking: meta_ad_id, meta_form_id on Case
  - Meta Conversions API (CAPI): sends signals on qualified/approved
  - Fernet encryption for page access tokens
  - CLI commands: update-meta-page-token, deactivate-meta-page
  - Dev endpoints: /dev/meta-leads/alerts, /dev/meta-leads/all
- **Workflow changes:**
  - New statuses: qualified (intake confirms), applied (full app submitted)
  - Removed auto-transition approved → pending_handoff
  - New flow: new → contacted → qualified → applied → under_review → approved → pending_handoff

### Week 10 (2025-12-16): Ops Console + Manager Analytics ✓ COMPLETE
- **Completed:**
  - Database: integration_health, integration_error_rollup, system_alerts, request_metrics_rollup
  - Services: ops_service.py, alert_service.py, metrics_service.py
  - Worker integration: job success/failure tracking, alert creation on max retry failures
  - Scheduled endpoint: POST /internal/scheduled/token-check (meta token expiry checks)
  - Analytics endpoints: /analytics/summary, /cases/by-status, /cases/by-assignee, /cases/trend, /meta/performance
  - Ops endpoints: /ops/health, /ops/alerts/summary, /ops/alerts, resolve/acknowledge/snooze
  - Frontend: /reports with real data, /settings/alerts, /settings/integrations
  - API clients + React Query hooks for analytics and ops
- **Security fixes:**
  - CSRF on all ops mutation endpoints
  - Literal types for enum query params (prevents 500)
  - Consistent pagination with severity filter
  - Naive datetime comparison fixed in token-check
  - 'default' instead of NULL for upsert keys

## 14) Decision Log (Update when choices change)

- **ORM choice:** SQLAlchemy 2.0 with DeclarativeBase
- **Auth token strategy:** Stateless JWT in HTTP-only cookie, signed with HS256, key rotation via `JWT_SECRET` + `JWT_SECRET_PREVIOUS`
- **Session revocation:** `token_version` on users table; bump to invalidate all sessions
- **OIDC verification:** `google-auth` library (handles JWKS fetching, signature verification)
- **CSRF protection:** `SameSite=Lax` + `X-Requested-With: XMLHttpRequest` header on mutations
- **Hosting choice:** TBD (target: Vercel for frontend, Render/Railway for backend)
- **Meta integration approach (2025-12-16):** Webhook → Job Queue → Worker → Auto-convert to Case; CAPI on qualified/approved
- **Status workflow change (2025-12-16):** No auto-transition from approved → pending_handoff; intake manually submits
- **AI provider choice:** TBD
- **Frontend deps (2025-12-14):** Next.js 16.0.10, React 19.2.3, Zod 4.1.13, recharts 3.5.1, Tailwind 4.1
- **Polymorphic notes:** EntityNote table with `entity_type` + `entity_id` supports Cases and IPs
- **Archive/restore pattern:** Set status to "archived", restore to previous status from history
- **Activity logging (2025-12-15):** CaseActivityLog with JSONB details, stores new values only, actor names resolved at read-time
- **Bulk operations (2025-12-15):** case_manager+ can bulk assign, all roles can archive
- **Assignment permissions (2025-12-15):** case_manager added to ROLES_CAN_ASSIGN for consistency
- **Notification dedupe (2025-12-15):** App-level dedupe with 1-hour window, DB constraint deferred until noisy
- **Theme system (2025-12-15):** Stone base + Teal theme using next-themes, warm oklch colors
- **Ops/alerts design (2025-12-16):** Fingerprint-based alert deduplication, hourly error rollups, 'default' for null integration keys

