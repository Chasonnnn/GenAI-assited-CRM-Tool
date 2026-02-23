# Surrogacy Force Platform

**Version:** 0.90.2 | **Last Updated:** February 23, 2026

A modern, multi-tenant platform for surrogacy agencies. Manage surrogates from intake through delivery with configurable workflows, matching, automation, and full auditability.

---

## Current Status

- Auth, org setup, and multi-tenancy
- Surrogates, intended parents, and matches
- Tasks, notes, attachments, and notifications
- Calendar, booking links, and appointment workflows
- Queue management, bulk operations, and filter persistence
- Automation workflows, email campaigns, and approval flows
- AI assistant with action proposals and execution approvals
- Ticketing inbox with Gmail journal sync, compose, and replies
- Ops console for agencies, templates, and integration alerts
- Integrations: Google OAuth, Google Calendar, Gmail, Zoom, Meta Lead Ads

---

## Key Features

### Core CRM
- Pipeline-driven surrogate and intended parent lifecycles with stage history
- Match lifecycle tracking with approvals and coordination
- Tasks, notes, and attachments tied to records with audit trails
- Queue-based assignment with claim and release to balance workload
- Ticket inbox linked to surrogate records for inbound and outbound conversations

### Automation and Campaigns
- Workflow engine with event triggers, conditions, and approvals
- Campaigns with recipient segmentation and suppression lists
- Email templates with variable rendering and delivery logging

### AI and Inbox
- AI assistant with chat history, suggested actions, and approval gates
- Gmail journal ingestion with ticket threading, surrogate linking, and reply flows

### Scheduling
- Appointment types, availability rules, and public booking links
- Shared calendar views for cross-team coordination

### Integrations
- Google OAuth SSO and per-user integrations
- Google Calendar sync and Gmail journal inbox (send/compose/reply)
- Zoom meeting creation and updates
- Meta Lead Ads import with optional CAPI feedback

### Platform and Security
- Strict tenant isolation with org-scoped queries
- Role-based access control and permission checks
- MFA via TOTP and Duo
- Hash-chain audit logging and encryption at rest

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| **Backend** | FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| **Database** | PostgreSQL 18 |
| **Search** | PostgreSQL Full-Text Search (tsvector + GIN) |
| **Migrations** | Alembic |
| **Testing** | pytest (backend), Vitest + React Testing Library (frontend) |

---

## Project Structure

```
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── app/
│   │   │   ├── core/           # Config, security, permissions
│   │   │   ├── db/             # ORM models, enums
│   │   │   ├── routers/        # API endpoints (thin)
│   │   │   ├── schemas/        # Pydantic DTOs
│   │   │   ├── services/       # Business logic
│   │   │   ├── jobs/           # Scheduled tasks / background jobs
│   │   │   └── utils/          # Helpers (normalization, pagination)
│   │   ├── alembic/            # Database migrations
│   │   └── tests/              # pytest suite
│   │
│   └── web/                    # Next.js frontend
│       ├── app/
│       │   ├── (app)/          # Authenticated routes
│       │   ├── apply/          # Public application forms
│       │   ├── book/           # Public booking pages
│       │   ├── login/          # Authentication
│       │   ├── ops/            # Ops console
│       │   └── health/         # Health endpoint
│       ├── components/         # Shared UI components
│       └── lib/                # API clients, hooks, types, utilities
│
├── infra/terraform/            # Terraform for GCP infra
├── cloudbuild/                 # Cloud Build configs
├── docs/                       # Documentation
├── scripts/                    # Utilities (stage map generator, etc.)
├── deployment.md               # Manual deploy notes
├── post-deployment.md          # Post-deploy checklist
└── docker-compose.yml          # PostgreSQL for development
```

---

## Getting Started

### Prerequisites

- **Node.js** 20+
- **pnpm**
- **Python** 3.11+
- **uv** (Python package manager)
- **Docker** + Docker Compose

### 1) Start Database

```bash
docker compose up -d db
```

PostgreSQL runs on `localhost:5432` (database: `crm`, user: `postgres`, password: `postgres`).

### 2) Setup Backend

```bash
cd apps/api

# Install dependencies
uv sync --extra test

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
uv run -m alembic upgrade head

# Bootstrap first organization
uv run -m app.cli create-org --name "Your Agency" --slug "agency" --admin-email "admin@agency.com"

# Start server
uv run -- uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000` | Docs: `http://localhost:8000/docs`

### 3) Run Background Worker

```bash
cd apps/api
uv run -- python -m app.worker
```

Run this in a second terminal while developing features that use queued/background jobs
(for example Gmail sync/ticketing, campaign sends, AI jobs, and scheduled automations).

### 4) Setup Frontend

```bash
cd apps/web

# Install dependencies
pnpm install

# Configure environment
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local

# Start dev server
pnpm dev
```

Frontend: `http://localhost:3000`

---

## Environment Variables

- **Backend**: see `apps/api/.env.example` for the full list.
- **Frontend**: `apps/web/.env.local`

Minimum backend vars for local dev:

```env
ENV=dev
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/crm
JWT_SECRET=change-this-in-production-minimum-32-characters
DEV_SECRET=local-dev-secret-change-me
FERNET_KEY=<generated>
DATA_ENCRYPTION_KEY=<generated>
PII_HASH_KEY=<generated>
```

Frontend:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## Local Development Setup

### Dev Login-As (Skip Google OAuth)

1) Set `DEV_SECRET` in `apps/api/.env` and start the API.

2) Seed a test org and users:
```bash
curl -s -X POST http://localhost:8000/dev/seed \
  -H "X-Dev-Secret: $DEV_SECRET"
```

3) Use a returned `user_id` to log in from the browser:
```js
await fetch("http://localhost:8000/dev/login-as/<user_id>", {
  method: "POST",
  headers: { "X-Dev-Secret": "<your dev secret>" },
  credentials: "include",
}).then((r) => r.json())
```

Note: `curl -i` against `/dev/login-as/<user_id>` is useful for inspecting `Set-Cookie`, but it does not log your browser in.

### Database Reset & Seed

```bash
# 1) Reset database (removes all data)
docker compose down -v && docker compose up -d db

# 2) Run migrations
cd apps/api
uv run -m alembic upgrade head

# 3) Seed test org and users
curl -s -X POST http://localhost:8000/dev/seed \
  -H "X-Dev-Secret: $DEV_SECRET"
```

### Required Encryption Keys

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Required:
- `FERNET_KEY`
- `DATA_ENCRYPTION_KEY`
- `PII_HASH_KEY`

Optional/conditional:
- `VERSION_ENCRYPTION_KEY` (config version snapshots)
- `META_ENCRYPTION_KEY` (Meta Lead Ads integration)

---

## Testing

### Backend
```bash
cd apps/api
uv run -m pytest -v
```

### Frontend
```bash
cd apps/web
pnpm test            # Unit tests (Vitest)
pnpm test:integration
pnpm typecheck
pnpm lint
```

---

## Deployment

- Terraform: `infra/terraform/README.md`
- GCP Cloud Build + Cloud Run: `docs/gcp-oidc-deploy.md`
- Manual checklist: `deployment.md`
- Post-deploy checklist: `post-deployment.md`

### Health Endpoints
- API liveness: `/health/live`
- API readiness: `/health/ready`
- Web health: `/health`

---

## License

Licensed under the PolyForm Noncommercial 1.0.0 license. See `LICENSE`.
Commercial use requires a separate license/permission from the maintainers.

---

## Contributing

See `agents.md` for contributor rules, dev workflows, and project standards.
