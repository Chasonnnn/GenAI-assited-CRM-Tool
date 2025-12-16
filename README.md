# Surrogacy CRM Platform

A modern, multi-tenant CRM and case management platform built for surrogacy agencies. Features lead pipeline management, intended parent profiles, case workflow tracking, and AI-assisted insights.

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
│   ├── api/                 # FastAPI backend
│   │   ├── app/
│   │   │   ├── core/        # Config, security, dependencies
│   │   │   ├── db/          # Database models, session, enums
│   │   │   ├── routers/     # API endpoints (auth, dev)
│   │   │   ├── schemas/     # Pydantic DTOs (auth, user, org, invite)
│   │   │   ├── services/    # Business logic (auth, user, org, google_oauth)
│   │   │   ├── cli.py       # CLI commands (create-org, revoke-sessions)
│   │   │   └── main.py      # FastAPI app entry
│   │   ├── alembic/         # Database migrations
│   │   └── requirements.txt
│   │
│   └── web/                 # Next.js frontend
│       ├── app/
│       │   ├── (app)/       # Authenticated app routes
│       │   │   ├── dashboard/
│       │   │   ├── leads/
│       │   │   └── settings/
│       │   └── layout.tsx
│       └── components/
│
├── docker-compose.yml       # PostgreSQL database
└── agents.md               # Project specification & guidelines
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
ALLOWED_EMAIL_DOMAINS=
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
DEV_SECRET=local-dev-secret-change-me
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

**Week 6+ Complete** — Case Handoff Workflow:

- [x] Project scaffolding (monorepo structure)
- [x] PostgreSQL with Docker Compose
- [x] FastAPI with health endpoint
- [x] SQLAlchemy + Alembic migrations configured
- [x] Next.js with App Router and (app) route group
- [x] Basic layout with sidebar/topbar
- [x] Google OAuth SSO with state/nonce/user-agent binding
- [x] Invite-only access (one pending invite per email globally)
- [x] JWT sessions in HTTP-only cookies with key rotation
- [x] Role-based authorization (4 roles: intake_specialist, case_manager, manager, developer)
- [x] Tenant isolation via Membership (one org per user)
- [x] CLI bootstrap + dev endpoints
- [x] **Cases module complete (backend):**
  - [x] Cases CRUD with sequential numbering
  - [x] Phone normalization (E.164) and state validation
  - [x] Soft-delete (archive/restore) with status sync
  - [x] Status history tracking
  - [x] Notes (2-4000 chars) with XSS sanitization (nh3)
  - [x] Tasks (with due dates and completion)
  - [x] Meta webhook skeleton
  - [x] **Case handoff workflow (intake → case manager)**
    - [x] `pending_handoff` status (manual, intake submits when ready)
    - [x] Handoff queue endpoint (case_manager+ only)
    - [x] Accept/Deny endpoints with reason tracking
    - [x] Role-based access control (intake can't see post-handoff cases)
    - [x] Transition guards (intake can't skip handoff)
- [x] **Intended Parents module complete (Week 6):**
  - [x] IP CRUD with full name, email, phone, state, budget
  - [x] Status workflow (new → contacted → in_review → qualified → matched → declined → on_hold)
  - [x] Archive/restore with status preservation and duplicate email check
  - [x] State/phone normalization validators
  - [x] Polymorphic EntityNotes supporting both Cases and IPs
  - [x] CSRF protection on all mutations
  - [x] Frontend pages (list with filters, detail with tabs)
- [x] **Frontend UI complete (v0 design):**
  - [x] Login page (Duo SSO + username option, glassmorphism)
  - [x] Dashboard (stats cards, charts, recent activity)
  - [x] Cases List (filters, search, table, pagination)
    - [x] Pending Handoff tab (case_manager+ only, with badge)
  - [x] Case Detail (tabs, status updates, notes)
  - [x] Tasks page (Kanban-style, filters)
  - [x] Intended Parents (list, filters, actions)
  - [x] Reports (4 chart types with recharts 3.5.1)
  - [x] Settings (5 tabs: Profile, Org, Notifications, Integrations, Security)
  - [x] Automation (Workflows + Templates tabs)
  - [x] App Sidebar with navigation
- [x] **Dependencies upgraded (2025-12-14):**
  - [x] Next.js 16.0.10, React 19.2.3, Zod 4.1.13, recharts 3.5.1
  - [x] All Radix UI components to latest versions
  - [x] Base UI combobox/pagination fixed for render prop compatibility
- [x] **Case Management Enhancements (2025-12-15):**
  - [x] Priority cases with `is_priority` field and gold highlighting
  - [x] Comprehensive activity logging (12 activity types)
  - [x] Activity Log tab replacing Status History
  - [x] Multi-select with checkboxes and floating action bar
  - [x] Bulk assign (case_manager+) and bulk archive (all roles)
  - [x] Case inline editing dialog
  - [x] Permission alignment (case_manager can now assign)
- [x] **In-App Notifications + Theme System (Week 8):**
  - [x] Notification model with dedupe, read status, org-scoping
  - [x] 6 notification types (case/task events)
  - [x] User notification settings (toggleable per type)
  - [x] NotificationBell component with unread badge
  - [x] Notifications page (/notifications)
  - [x] Settings page wired to real notifications API
  - [x] Theme system (light/dark/system) with Stone + Teal colors
  - [x] ThemeToggle dropdown in header
  - [x] 30-second polling for real-time updates
- [x] **Meta Lead Ads Integration (Week 9):**
  - [x] Webhook endpoint with HMAC signature verification
  - [x] Auto-conversion: Meta leads → Cases (source=META)
  - [x] Campaign tracking (meta_ad_id, meta_form_id)
  - [x] Meta Conversions API (CAPI) on qualified/approved
  - [x] CLI: update-meta-page-token, deactivate-meta-page
  - [x] New statuses: qualified, applied
  - [x] New workflow: contacted → qualified → applied → under_review → approved → pending_handoff
- [ ] Ops Console + Manager Analytics

## Documentation

See [agents.md](./agents.md) for detailed project specifications, architecture decisions, and contribution guidelines.

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
