# Surrogacy Force Platform

**Version:** 0.91.48 <!-- x-release-please-version -->

A modern, multi-tenant platform for surrogacy agencies. Manage surrogates from intake through delivery with configurable workflows, matching, automation, and full auditability.

---

## Current Status

- Auth, org setup, and multi-tenancy
- Surrogates, intended parents, and matches
- Custom fields, intake form builder, and public/embeddable forms
- Surrogate journey timelines, contact attempts, and automated reminders
- Tasks, notes, attachments, and notifications
- Calendar, booking links, and self-service reschedule/cancel flows
- Queue management, bulk operations, mass edit, and filter persistence
- Status-change approval requests
- Automation workflows, email campaigns, and approval flows
- AI assistant, AI Studio (social drafts), AI Focus, and interview transcription/summarization
- Interviews with versioned transcripts, notes, and PDF/JSON export
- Analytics dashboards (funnel, KPIs, per-user, Meta ad spend) with PDF export
- Ticketing inbox with Gmail journal sync, compose, and replies
- Compliance: retention policies, legal holds, PHI-access auditing, and attachment malware scanning
- Ops console for agencies, templates, and integration alerts
- Integrations: Google OAuth SSO, Google Calendar, Gmail, Google Tasks, Zoom, Meta Lead Ads (+ Conversions API & CRM Dataset), Zapier, Resend, Duo + TOTP MFA, Gemini/Vertex AI, ClamAV, S3/GCS storage, Sentry, OpenTelemetry

---

## Release and Deploy Flow

- Merge changes into `main` to let Release Please evaluate the next release.
- Release Please opens and merges a release PR, then creates a version tag like `surrogacy-crm-platform-v0.91.31`.
- Cloud Build deploy triggers listen for those version tags (matching `^surrogacy-crm-platform-v.*$`), not arbitrary GitHub release objects.

---

## Key Features

### Core CRM
- Pipeline-driven surrogate and intended parent lifecycles with stage history
- Match lifecycle tracking with approvals and coordination
- Custom fields that extend surrogate and intended-parent records with configurable typed fields
- Configurable intake forms via a form builder, with versioning, public applicant-facing forms, and embeddable iframe forms
- Surrogate journey timeline aggregating the full record lifecycle
- Contact attempts logging with automated follow-up reminders
- Status-change approval requests reviewed before they take effect
- Tasks, notes, and attachments tied to records with audit trails
- Queue-based assignment with claim and release to balance workload
- Bulk import (reusable templates, AI-assisted column mapping, format detection) and developer-scoped mass edit
- Ticket inbox linked to surrogate records for inbound and outbound conversations

### Automation and Campaigns
- Workflow engine with event triggers, conditions, and approvals
- AI-generated workflows from natural-language descriptions (with validation)
- Campaigns with recipient segmentation and suppression lists
- Email templates with variable rendering and delivery logging
- Email open/click tracking for campaign analytics

### AI
- AI assistant with chat history, suggested actions, and approval gates
- AI Focus: one-shot summarize-a-surrogate, draft typed emails, analyze the dashboard, and generate email templates (SSE streaming)
- AI Studio: org-scoped social-media draft content and images via bring-your-own-key, saved as previews and never auto-posted
- AI Schedule parsing of free-text notes into proposed tasks
- AI usage analytics tracking token consumption and cost (by model, daily, top users)
- Per-org bring-your-own-key (BYOK) AI settings with write-only keys, model selection, and an explicit user consent gate
- PII anonymization applied before any AI provider call, rehydrated in responses
- AI never auto-sends or auto-posts; all drafts require human action

### Interviews
- Record surrogate interviews with versioned TipTap transcripts and threaded notes
- Audio/video attachments with AI-powered transcription (Gemini/Vertex)
- AI summarization per interview and across all of a surrogate's interviews
- PDF and JSON export

### Inbox and Email
- Gmail journal ingestion with ticket threading, surrogate linking, and reply flows
- Resend as a first-class campaign, workflow, and transactional/system email provider (with delivery webhooks)
- Email-safe HTML signature rendering from org branding and user profile data

### Analytics
- Org analytics for surrogate volume, status, source, and state distribution
- Conversion funnel, KPIs, per-user performance, and activity feed
- Meta ad performance and spend reporting
- Server-side PDF export of profiles, journeys, interviews, and analytics

### Scheduling
- Appointment types, availability rules, and public booking links
- Token-based self-service reschedule and cancel flows for booked appointments
- Shared calendar views for cross-team coordination

### Integrations
- Google OAuth SSO and per-user Google integrations (Calendar, Gmail, Google Tasks, Cloud/Vertex)
- Google Calendar two-way sync (with push webhooks) and Gmail journal inbox (send/compose/reply via Cloud Pub/Sub push)
- Google Tasks sync for platform tasks
- Zoom meeting creation/updates with `meeting.started`/`meeting.ended` webhooks
- Meta Lead Ads import with Conversions API (CAPI) feedback and direct Meta CRM Dataset delivery
- Zapier inbound lead webhooks and outbound stage/qualification events
- Resend email provider for campaign, workflow, and platform/system email (with delivery webhooks)
- AI powered by Google Gemini and Vertex AI (Workload Identity Federation / OIDC for keyless Vertex auth)

### Platform and Security
- Strict tenant isolation with org-scoped queries
- Role-based access control and permission checks
- MFA via TOTP (authenticator apps) and Duo Universal Prompt (with Duo Admin API reset)
- Hash-chain audit logging and encryption at rest
- PHI-access audit logging across surrogate, task, note, match, appointment, and attachment reads
- Compliance: retention policies, legal holds, and purge preview/execution
- ClamAV malware scanning for uploads (signatures synced via S3-compatible storage; optional Cloud Run scan job)
- S3-compatible / Google Cloud Storage object storage for attachments
- Admin/developer config version control, org export, and org restore import
- Observability: Sentry error tracking, GCP Cloud Logging + Error Reporting, OpenTelemetry (OTLP) tracing
- Redis for distributed rate limiting

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
| **Backend** | FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| **Database** | PostgreSQL 18 |
| **Cache / Rate limiting** | Redis |
| **Object storage** | S3-compatible / Google Cloud Storage (boto3) |
| **AI** | Google Gemini / Vertex AI |
| **PDF export** | Playwright / Chromium |
| **Search** | PostgreSQL Full-Text Search (tsvector + GIN) |
| **Migrations** | Alembic |
| **Testing** | pytest (backend), Vitest + React Testing Library + MSW (frontend) |
| **Observability** | Sentry, GCP Cloud Logging + Error Reporting, OpenTelemetry |

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
│   │   │   ├── jobs/           # Background job worker + handlers
│   │   │   └── utils/          # Helpers (normalization, pagination)
│   │   ├── alembic/            # Database migrations
│   │   ├── scripts/            # Seed/maintenance scripts
│   │   └── tests/              # pytest suite
│   │
│   └── web/                    # Next.js frontend
│       ├── app/
│       │   ├── (app)/          # Authenticated routes
│       │   ├── (print)/        # Printable record views (journey, case details)
│       │   ├── auth/           # Duo OAuth callback
│       │   ├── mfa/            # MFA challenge
│       │   ├── intake/         # Public intake/application forms (by org slug)
│       │   ├── book/           # Public booking + self-service manage pages
│       │   ├── embed/          # Embeddable forms + forms.v1.js loader
│       │   ├── email/          # Unsubscribe (+ RFC-8058 one-click)
│       │   ├── invite/         # Org invite acceptance
│       │   ├── login/          # Authentication
│       │   ├── ops/            # Ops console
│       │   ├── privacy/        # Privacy policy
│       │   ├── terms/          # Terms of service
│       │   └── health/         # Health endpoint
│       ├── components/         # Shared UI components
│       ├── hooks/              # Shared React hooks
│       └── lib/                # api/, constants/, context/, forms/, hooks/, types/, utils/
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

- **Node.js** 24
- **pnpm** 10.28.2 (pinned via `packageManager`; activate with `corepack`)
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
(for example Gmail sync/ticketing, campaign sends, AI jobs, interview transcription, attachment
scanning, reminders, and scheduled automations). The deployed worker container runs the
HTTP-wrapped variant `python -m app.worker_service`.

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

# 4) High-volume fixture seed (deterministic by default)
SEED_RANDOM_SEED=20260224 \
SEED_SURROGATES=500 \
SEED_INTENDED_PARENTS=10 \
SEED_MATCH_MODE=balanced \
SEED_MATCH_COUNT=30 \
SEED_ACTIVITY_MODE=rich_core \
uv run -m scripts.seed_mock_data
```

`/dev/seed` now returns one user per role:
- `admin@test.com`
- `intake@test.com`
- `specialist@test.com` (case manager)
- `developer@test.com`

`seed_mock_data` prints a machine-readable `SEED_SUMMARY {...}` payload that includes:
- stage/status/match counts
- activity/history totals
- `login_as_user_ids` for browser `POST /dev/login-as/<user_id>`

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
- `VERSION_ENCRYPTION_KEY` (config version snapshots; falls back to `META_ENCRYPTION_KEY` if empty)
- `META_ENCRYPTION_KEY` (Meta Lead Ads integration)

---

## Testing

### Backend
```bash
cd apps/api
uv run -m pytest -v
# or use the helper (frozen install + venv pytest):
./run_tests.sh
```

CI runs pytest with coverage (`--cov=app --cov-branch`) and enforces a separate `alembic check`
migration-drift gate.

### Frontend
```bash
cd apps/web
pnpm test              # Unit tests (Vitest)
pnpm test:integration  # MSW-backed integration tests
pnpm test:all          # Unit + integration
pnpm typecheck
pnpm lint
pnpm check             # typecheck + lint + test
```

> Note: CI runs backend tests against `postgres:16` while local development uses `postgres:18.1`
> (see `docker-compose.yml`); this divergence is intentional.

---

## Deployment

- Terraform: `infra/terraform/README.md`
- GCP Cloud Build + Cloud Run: `docs/gcp-oidc-deploy.md`
- Manual checklist: `deployment.md`
- Post-deploy checklist: `post-deployment.md`

### Health Endpoints
- API liveness: `/health/live`
- API readiness: `/health/ready`
- API (legacy alias to readiness): `/health`
- Web health: `/health`
- Worker service health: `/health`

---

## License

Licensed under the PolyForm Noncommercial 1.0.0 license. See `LICENSE`.
Commercial use requires a separate license/permission from the maintainers.

---

## Contributing

See `agents.md` for contributor rules, dev workflows, and project standards.
