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
- Work Queue (monitor leads/cases with filters + assignments)
- Leads
- Cases
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
- Manager: Home, Work Queue, Leads, Cases, Reports, Inbox, Tasks, Activity, Settings
- PR/Intake: Home, Work Queue, Leads, Inbox, Tasks, Activity
- Specialist: Home, Work Queue, Cases, Inbox, Tasks, Activity

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

CaseStatus:
- `waiting_for_match`
- `matched`
- `embryo_transfer`
- `pregnant`
- `delivered`
- `closed`

Rule: keep enum values centralized in one place (backend constants + frontend types).

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

- **Date:** 2025-12-13
- **Completed:**
  - Project scaffolding (monorepo with apps/api + apps/web)
  - PostgreSQL 16 via Docker Compose
  - FastAPI with health endpoint + DB connectivity check
  - SQLAlchemy 2.0 + Alembic migrations configured
  - Next.js 16 with App Router and (app) route group
  - Basic app layout (sidebar + topbar)
  - Placeholder pages: Dashboard, Leads, Settings
  - **Week 2 complete:** Authentication & tenant isolation
    - Google OAuth SSO with state/nonce/user-agent binding
    - Invite-only access (one pending invite per email globally)
    - JWT sessions in HTTP-only cookies with key rotation
    - Role-based authorization (manager, intake, specialist)
    - Strict tenant isolation via Membership (one org per user)
    - CLI bootstrap (`python -m app.cli create-org`)
    - Dev endpoints (`/dev/seed`, `/dev/login-as`)
- **In progress:** Frontend auth integration
- **Blockers:** None
- **Next milestones:** Frontend login flow, Leads CRUD API

## 14) Decision Log (Update when choices change)

- **ORM choice:** SQLAlchemy 2.0 with DeclarativeBase
- **Auth token strategy:** Stateless JWT in HTTP-only cookie, signed with HS256, key rotation via `JWT_SECRET` + `JWT_SECRET_PREVIOUS`
- **Session revocation:** `token_version` on users table; bump to invalidate all sessions
- **OIDC verification:** `google-auth` library (handles JWKS fetching, signature verification)
- **CSRF protection:** `SameSite=Lax` + `X-Requested-With: XMLHttpRequest` header on mutations
- **Hosting choice:** TBD (target: Vercel for frontend, Render/Railway for backend)
- **Meta integration approach:** TBD
- **AI provider choice:** TBD
