# Surrogacy CRM Platform

**Version:** 0.12.00 | **Format:** a.bc.de (major.feature.patch)

A modern, multi-tenant CRM and case management platform built for surrogacy agencies. Features lead pipeline management with **customizable stages**, intended parent profiles, case workflow tracking, AI-assisted insights, and enterprise audit/versioning.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16.0.10, React 19.2.3, TypeScript 5.9, Tailwind CSS 4.1, shadcn/ui, Zod 4 |
| **Backend** | FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| **Database** | PostgreSQL 16 (via Docker) |
| **Migrations** | Alembic |

## AI (Optional / BYOK)

AI is an **optional** capability designed to be safe, auditable, and tenant-configurable.

- Default: **off** (the app works without AI).
- If enabled: organizations can use **their own AI provider keys** (BYOK) so costs and provider choices stay under their control.
- Recommended: store the org’s AI key **server-side in the database (encrypted at rest)** so a manager enables AI once and authorized employees can use AI features without handling keys.
- Early AI surfaces (recommended): analytics/insights, summarization, and drafting (with human review).
- Early AI safety stance (recommended): AI can **recommend** qualification/flags with reasons + confidence, but a human confirms any final status changes.

## Project Structure

```
├── apps/
│   ├── api/                    # FastAPI backend (v0.12.00)
│   │   ├── app/
│   │   │   ├── core/           # Config, security, dependencies, case_access
│   │   │   ├── db/             # Models (36: +PipelineStage), enums, session
│   │   │   ├── routers/        # API endpoints (21 modules + stage CRUD)
│   │   │   │   ├── auth, cases, tasks, notes, notifications
│   │   │   │   ├── intended_parents, email_templates, pipelines, queues
│   │   │   │   ├── ai, analytics, audit, admin_versions, metadata
│   │   │   │   ├── integrations, webhooks, ops, jobs
│   │   │   │   └── dev, internal, websocket
│   │   │   ├── schemas/        # Pydantic DTOs
│   │   │   ├── services/       # Business logic (33 services: +queue_service)
│   │   │   │   ├── auth, user, org, case, task, note, queue
│   │   │   │   ├── ai_*, email, pipeline, version
│   │   │   │   ├── meta_*, import, audit, analytics
│   │   │   │   └── notification, oauth, gmail, pii_anonymizer
│   │   │   ├── utils/          # Helpers (normalization, pagination)
│   │   │   ├── cli.py          # CLI commands
│   │   │   └── main.py         # FastAPI app entry
│   │   ├── alembic/            # Database migrations (37: +pipeline_stages, +cutover)
│   │   ├── tests/              # pytest test suite (65 tests)
│   │   └── requirements.txt
│   │
│   └── web/                    # Next.js frontend
│       ├── app/
│       │   ├── (app)/          # Authenticated routes
│       │   │   ├── dashboard, cases, tasks, leads
│       │   │   ├── intended-parents, reports, settings
│       │   │   │   ├── audit/   # Audit log viewer (managers)
│       │   │   │   └── queues/  # Queue management (managers)
│       │   │   ├── ai-assistant, notifications, automation
│       │   │   └── analytics, ops-console
│       │   ├── login/          # Public login page
│       │   └── layout.tsx
│       ├── components/         # Shared UI (inline-edit-field, etc.)
│       ├── lib/                # API client, hooks, utils
│       │   └── hooks/          # React Query hooks (+use-queues.ts)
│       └── tests/              # Vitest test suite (30 tests)
│
├── docs/                       # Documentation
│   ├── agents.md               # Project spec & guidelines
│   └── DESIGN.md               # Architecture decisions
├── docker-compose.yml          # PostgreSQL database
└── README.md
```


## Getting Started

### Prerequisites

- Node.js >= 20 (LTS)
- pnpm
- Python >= 3.11
- Docker & Docker Compose

### 1. Start the Database

```bash
docker compose up -d
```

This starts PostgreSQL on `localhost:5432` with:
- Database: `crm`
- User: `postgres`
- Password: `postgres`

### 2. Setup Backend (API)

```bash
cd apps/api

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env  # Then edit with your settings

# Bootstrap (create first org + manager invite)
python -m app.cli create-org --name "Acme Surrogacy" --slug "acme" --admin-email "admin@acme.com"

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

API runs at `http://localhost:8000`

### 3. Setup Frontend (Web)

```bash
cd apps/web

# Install dependencies
pnpm install

# Start dev server
pnpm dev
```

Frontend runs at `http://localhost:3000`

## Environment Variables

### Backend (`apps/api/.env`)

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/crm
# Auth (cookie-based session)
JWT_SECRET=change-this-in-production-minimum-32-characters
JWT_SECRET_PREVIOUS=
JWT_EXPIRES_HOURS=4
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
# Encryption (required for OAuth tokens + versioned config snapshots)
FERNET_KEY=generate-with-python-cryptography-fernet
VERSION_ENCRYPTION_KEY=generate-with-python-cryptography-fernet
META_ENCRYPTION_KEY=optional-fallback-if-VERSION_ENCRYPTION_KEY-empty
ALLOWED_EMAIL_DOMAINS=
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
DEV_SECRET=local-dev-secret-change-me
# Integrations (per-user OAuth)
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
ZOOM_REDIRECT_URI=http://localhost:8000/integrations/zoom/callback
GMAIL_REDIRECT_URI=http://localhost:8000/integrations/gmail/callback
# Email Provider (Resend)
RESEND_API_KEY=re_your_api_key_here  # Get from https://resend.com/api-keys
# Redis (optional, for distributed rate limiting across workers)
REDIS_URL=redis://localhost:6379/0
# Optional AI (example; exact wiring may evolve):
# AI_ENABLED=false
# AI_PROVIDER=openai
# OPENAI_API_KEY=...
```

### Frontend (`apps/web/.env.local`)

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## API Endpoints

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with database connectivity test |
| `/auth/google/login` | GET | Initiate Google OAuth flow |
| `/auth/google/callback` | GET | Handle OAuth callback, create session |
| `/auth/me` | GET | Get current user profile + org + role |
| `/auth/logout` | POST | Clear session cookie (requires CSRF header) |

### Cases
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/cases` | GET | List cases (paginated, filters: status, source, assigned_to, q) |
| `/cases` | POST | Create case (auto-generates case_number) |
| `/cases/handoff-queue` | GET | List pending handoff cases (case_manager+ only) |
| `/cases/{id}` | GET | Get case by ID |
| `/cases/{id}` | PATCH | Update case fields |
| `/cases/{id}` | DELETE | Hard delete (requires archived first, manager+) |
| `/cases/{id}/status` | PATCH | Change status (records history) |
| `/cases/{id}/assign` | PATCH | Assign to user (manager+ only) |
| `/cases/{id}/archive` | POST | Soft delete (manager+ only) |
| `/cases/{id}/restore` | POST | Restore archived case (manager+ only) |
| `/cases/{id}/history` | GET | Get status change history (legacy) |
| `/cases/{id}/activity` | GET | Get comprehensive activity log (paginated) |
| `/cases/{id}/notes` | GET, POST | List/create notes |
| `/cases/{id}/accept` | POST | Accept handoff (case_manager+ only) |
| `/cases/{id}/deny` | POST | Deny handoff with reason (case_manager+ only) |
| `/cases/assignees` | GET | Get org members for assignment dropdown |
| `/cases/bulk-assign` | POST | Bulk assign cases (case_manager+ only) |

### Email Templates
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/email-templates` | GET | List templates |
| `/email-templates` | POST | Create template (manager+ only) |
| `/email-templates/{id}` | GET, PATCH, DELETE | Template CRUD |
| `/email-templates/{id}/versions` | GET | List version history |
| `/cases/{id}/send-email` | POST | Send email to case using template |

### CSV Import
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/cases/import/preview` | POST | Upload CSV and preview data with validation |
| `/cases/import/execute` | POST | Execute CSV import |
| `/cases/import` | GET | List import history |
| `/cases/import/{id}` | GET | Get import details with errors |

### Meta Leads Admin
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/meta-pages` | GET | List configured Meta pages |
| `/admin/meta-pages` | POST | Add page token (encrypted) |
| `/admin/meta-pages/{page_id}` | PUT | Update page configuration |
| `/admin/meta-pages/{page_id}` | DELETE | Remove page |

### Tasks
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tasks` | GET | List tasks (filters: assigned_to, case_id, is_completed) |
| `/tasks` | POST | Create task |
| `/tasks/{id}` | GET, PATCH, DELETE | Task CRUD |
| `/tasks/{id}/complete` | POST | Mark complete |
| `/tasks/{id}/uncomplete` | POST | Mark incomplete |

### Notes
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/notes/{id}` | DELETE | Delete note (author or manager+) |

### Development (dev only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dev/seed` | POST | Create test org + users (requires X-Dev-Secret) |
| `/dev/login-as/{user_id}` | POST | Bypass OAuth for testing |

### Intended Parents
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/intended-parents` | GET | List IPs (paginated, filters: status, state, budget, q) |
| `/intended-parents` | POST | Create intended parent |
| `/intended-parents/stats` | GET | Get IP counts by status |
| `/intended-parents/{id}` | GET | Get IP by ID |
| `/intended-parents/{id}` | PATCH | Update IP fields |
| `/intended-parents/{id}/status` | PATCH | Change status (records history) |
| `/intended-parents/{id}/archive` | POST | Archive IP |
| `/intended-parents/{id}/restore` | POST | Restore archived IP (manager+ only) |
| `/intended-parents/{id}` | DELETE | Hard delete (requires archived first, manager+) |
| `/intended-parents/{id}/history` | GET | Get status change history |
| `/intended-parents/{id}/notes` | GET, POST, DELETE | List/create/delete notes |

### Notifications
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/me/notifications` | GET | List notifications (filters: unread_only, limit, offset) |
| `/me/notifications/count` | GET | Get unread count (for polling) |
| `/me/notifications/{id}/read` | PATCH | Mark notification as read |
| `/me/notifications/read-all` | POST | Mark all notifications as read |
| `/me/settings/notifications` | GET | Get notification preferences |
| `/me/settings/notifications` | PATCH | Update notification preferences |

## Current Status

**Version 0.10.00** — AI Assistant v1 Complete

### Core Platform
- [x] Project scaffolding + PostgreSQL + migrations
- [x] Google OAuth SSO + JWT sessions + role-based auth
- [x] Cases module (CRUD, notes, tasks, status history, handoff workflow)
- [x] Intended Parents module (CRUD, status workflow, archive/restore)
- [x] Frontend UI (shadcn/ui, responsive design, dark mode)
- [x] Workflow automation + email foundation
- [x] In-App Notifications + Theme System
- [x] Meta Lead Ads Integration + CAPI

### Enterprise Features (v0.10.00)
- [x] **Global Audit Trail** — Hash chain, tamper-evident logging
- [x] **CSV Import** — Email-based duplicate detection
- [x] **Org-Configurable Pipelines** — Custom stage labels, colors, order
- [x] **In-App Version Control** — Encrypted snapshots, rollback support
- [x] **Queue/Ownership System** — Salesforce-style claim/release workflow
- [x] **Zoom Integration** — OAuth, meeting creation, email invites
- [x] **AI Assistant v1** — BYOK, summarize-case, draft-email, analyze-dashboard

### Data Models (35 tables)
`Organization`, `User`, `Membership`, `AuthIdentity`, `OrgInvite`, `Case`, `CaseStatusHistory`, `CaseActivityLog`, `Task`, `MetaLead`, `MetaPageMapping`, `Job`, `EmailTemplate`, `EmailLog`, `IntendedParent`, `IntendedParentStatusHistory`, `EntityNote`, `Notification`, `UserNotificationSettings`, `IntegrationHealth`, `IntegrationErrorRollup`, `SystemAlert`, `RequestMetricsRollup`, `AISettings`, `AIConversation`, `AIMessage`, `AIActionApproval`, `AIEntitySummary`, `AIUsageLog`, `UserIntegration`, `AuditLog`, `CaseImport`, `Pipeline`, `EntityVersion`


## Documentation

See [agents.md](./docs/agents.md) for detailed project specifications, architecture decisions, and contribution guidelines.

## Open-source & Customization Strategy

The long-term goal is to keep a **general, open-source-ready core** while supporting organization-level customization via configuration (not forks):

- Shared core entities and APIs (org-scoped, role-scoped)
- Per-organization settings for pipelines/statuses, templates, rubrics, and (optional) AI policies/keys

## Tabs & Modules (V1 vs Later)

We will likely expose features as **modules** (enabled per org) and **tabs** (shown per role).

Recommended V1 tabs:
- Home (calendar + quick actions + my work)
- Work Queue (monitor leads/cases with filters + assignments)
- Leads
- Cases
- Reports
- Settings

Useful V1-lite tabs (simple early versions):
- Inbox/Notifications
- Tasks
- Activity

Later/optional modules:
- Templates (email/snippets/checklists)
- Automation (follow-up rules, SLAs, assignment rules)
- Integrations (Meta Lead Ads, email providers, calendar, SMS/telephony)
- Import/Export and Dedupe
- Contacts/Directory

## License

Private — All rights reserved.
