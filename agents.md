# agent.md — Surrogacy CRM Platform (Multi-tenant, Open-source Ready)

This document is the single source of truth for how we build this project: architecture, conventions, workflows, and rules that every contributor (human or AI agent) must follow.

## 0) Project Summary

We are building an **in-house CRM + case management platform** for a surrogacy agency, with the ability to **scale to multiple companies (multi-tenant)** and potentially be **open-sourced** in the future.

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
- JWT auth (access tokens)

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
- `DATABASE_URL=postgresql+asyncpg://...`
- `JWT_SECRET=...`
- `JWT_EXPIRES_MIN=...`
- `CORS_ORIGINS=http://localhost:3000`
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
- Roles are per-organization membership:
  - `User` is identity
  - `Membership(user_id, organization_id, role)` is authorization context

### 5.2 Authorization rules
- Do not scatter `if role == "x"` across routers.
- Use centralized dependencies/helpers, e.g.:
  - `require_roles(["manager", "intake"])`
  - `require_membership()`
- Enforce both:
  - user authentication
  - membership in org
  - role permission for action

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
  - `/auth/login`, `/auth/me`
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

- Date:
- Completed:
- In progress:
- Blockers:
- Next milestones:

## 14) Decision Log (Update when choices change)

- ORM choice: (SQLAlchemy / SQLModel)
- Auth token strategy: (JWT in httpOnly cookie vs localStorage)
- Hosting choice:
- Meta integration approach:
- AI provider choice:
