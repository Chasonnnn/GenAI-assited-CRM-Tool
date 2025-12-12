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
│   │   │   ├── core/        # Config, settings
│   │   │   ├── db/          # Database models, session, migrations
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

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with database connectivity test |

## Current Status

**In Development** — Setting up core infrastructure:

- [x] Project scaffolding (monorepo structure)
- [x] PostgreSQL with Docker Compose
- [x] FastAPI with health endpoint
- [x] SQLAlchemy + Alembic migrations configured
- [x] Next.js with App Router and (app) route group
- [x] Basic layout with sidebar/topbar
- [x] Placeholder pages: Dashboard, Leads, Settings
- [ ] Authentication & multi-tenancy
- [ ] Lead management CRUD
- [ ] Case workflow
- [ ] Meta Lead Ads integration

## Documentation

See [agents.md](./agents.md) for detailed project specifications, architecture decisions, and contribution guidelines.

## Open-source & Customization Strategy

The long-term goal is to keep a **general, open-source-ready core** while supporting organization-level customization via configuration (not forks):

- Shared core entities and APIs (org-scoped, role-scoped)
- Per-organization settings for pipelines/statuses, templates, rubrics, and (optional) AI policies/keys

## License

Private — All rights reserved.
