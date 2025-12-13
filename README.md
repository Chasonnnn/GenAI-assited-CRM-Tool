# Surrogacy CRM Platform

A modern, multi-tenant CRM and case management platform built for surrogacy agencies. Features lead pipeline management, intended parent profiles, case workflow tracking, and AI-assisted insights.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
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

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with database connectivity test |
| `/auth/google/login` | GET | Initiate Google OAuth flow |
| `/auth/google/callback` | GET | Handle OAuth callback, create session |
| `/auth/me` | GET | Get current user profile + org + role |
| `/auth/logout` | POST | Clear session cookie (requires CSRF header) |
| `/dev/seed` | POST | Create test org + users (dev only, requires X-Dev-Secret) |
| `/dev/login-as/{user_id}` | POST | Bypass OAuth for testing (dev only) |

## Current Status

**Week 2 Complete** — Authentication & tenant isolation:

- [x] Project scaffolding (monorepo structure)
- [x] PostgreSQL with Docker Compose
- [x] FastAPI with health endpoint
- [x] SQLAlchemy + Alembic migrations configured
- [x] Next.js with App Router and (app) route group
- [x] Basic layout with sidebar/topbar
- [x] Placeholder pages: Dashboard, Leads, Settings
- [x] Google OAuth SSO with state/nonce/user-agent binding
- [x] Invite-only access (one pending invite per email globally)
- [x] JWT sessions in HTTP-only cookies with key rotation
- [x] Role-based authorization (manager, intake, specialist)
- [x] Tenant isolation via Membership (one org per user)
- [x] CLI bootstrap + dev endpoints
- [ ] Frontend auth integration (login button, route protection)
- [ ] Lead management CRUD
- [ ] Case workflow
- [ ] Meta Lead Ads integration

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
