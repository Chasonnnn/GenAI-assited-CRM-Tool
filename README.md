# Surrogacy CRM Platform

**Version:** 0.16.0 | **Last Updated:** December 29, 2025

A modern, multi-tenant CRM platform purpose-built for surrogacy agencies. Manage cases from lead intake through delivery with customizable pipelines, intended parent matching, AI-powered assistance, and comprehensive automation.

---

## ✨ Key Features

### Case Management
- **Customizable Pipelines** — Define stages, colors, and workflows per organization
- **Case Handoff Workflow** — Seamless intake-to-case-manager transitions
- **Activity Logging** — Complete audit trail of all case actions
- **Queue System** — Salesforce-style claim/release for workload distribution

### Form Builder
- **Dynamic Forms** — Create multi-page application forms with drag-and-drop
- **Secure Public Links** — Token-based form access for applicants
- **Auto-Mapping** — Form submissions auto-populate case fields on approval
- **File Uploads** — Secure document collection with virus scanning

### Matching & Coordination
- **IP-Surrogate Matching** — Propose, review, accept/reject workflow
- **Shared Calendar** — Coordinated scheduling across match parties
- **Notes & Files** — Centralized documentation per match

### Automation
- **Workflow Engine** — Event-driven automation (8 triggers, 6 action types)
- **Email Campaigns** — Bulk sends with recipient filtering and tracking
- **Email Templates** — Customizable templates with variable substitution

### AI Assistant (Optional)
- **BYOK Model** — Bring your own API key (OpenAI, etc.)
- **Case Summarization** — AI-generated case summaries
- **Email Drafting** — Context-aware email composition
- **Dashboard Insights** — Smart analytics recommendations

### Integrations
- **Google OAuth SSO** — Secure authentication
- **Google Calendar** — Two-way appointment sync
- **Zoom** — Meeting creation and invites
- **Meta Lead Ads** — Auto-import leads with CAPI feedback
- **Gmail** — Send emails through connected accounts

### Enterprise Features
- **Multi-Tenancy** — Complete organization isolation
- **RBAC** — Role-based permissions (intake, case manager, admin, developer)
- **MFA** — TOTP and Duo Security support
- **Audit Trail** — Tamper-evident hash-chain logging
- **Version Control** — Rollback support for configurations

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui components |
| **Backend** | FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| **Database** | PostgreSQL 16 |
| **Search** | PostgreSQL Full-Text Search (tsvector + GIN) |
| **Migrations** | Alembic |
| **Testing** | pytest (backend), Vitest + React Testing Library (frontend) |

---

## 📁 Project Structure

```
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── app/
│   │   │   ├── core/           # Config, security, permissions
│   │   │   ├── db/             # SQLAlchemy models, enums
│   │   │   ├── routers/        # API endpoints (25+ modules)
│   │   │   ├── schemas/        # Pydantic request/response DTOs
│   │   │   ├── services/       # Business logic (40+ services)
│   │   │   └── utils/          # Helpers (normalization, pagination)
│   │   ├── alembic/            # Database migrations
│   │   └── tests/              # pytest test suite
│   │
│   └── web/                    # Next.js frontend
│       ├── app/
│       │   ├── (app)/          # Authenticated routes
│       │   ├── apply/          # Public application forms
│       │   ├── book/           # Public booking pages
│       │   └── login/          # Authentication
│       ├── components/         # Shared UI components
│       └── lib/                # API client, hooks, utilities
│
├── docs/                       # Documentation
│   ├── DESIGN.md               # Architecture documentation
│   ├── automation.md           # Automation system guide
│   └── oauth-setup-guide.md    # Integration setup
│
├── CHANGELOG.md                # Version history
└── docker-compose.yml          # PostgreSQL for development
```

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** ≥ 20 (LTS)
- **pnpm** (package manager)
- **Python** ≥ 3.11
- **Docker** & Docker Compose

### 1. Start Database

```bash
docker compose up -d
```

PostgreSQL runs on `localhost:5432` (database: `crm`, user: `postgres`, password: `postgres`)

### 2. Setup Backend

```bash
cd apps/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
alembic upgrade head

# Bootstrap first organization
python -m app.cli create-org --name "Your Agency" --slug "agency" --admin-email "admin@agency.com"

# Start server
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000` | Docs: `http://localhost:8000/docs`

### 3. Setup Frontend

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

## ⚙️ Environment Variables

### Backend (`apps/api/.env`)

```env
# Database
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/crm

# Authentication
JWT_SECRET=your-secret-key-minimum-32-characters
JWT_EXPIRES_HOURS=4

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Encryption (required for OAuth tokens, versioned configs)
FERNET_KEY=generate-with-Fernet.generate_key()
VERSION_ENCRYPTION_KEY=generate-with-Fernet.generate_key()

# Frontend
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000

# Email (Resend)
RESEND_API_KEY=re_your_api_key

# Integrations (optional)
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
GMAIL_REDIRECT_URI=http://localhost:8000/integrations/gmail/callback

# Meta Lead Ads (optional)
META_VERIFY_TOKEN=
META_AD_ACCOUNT_ID=
META_SYSTEM_TOKEN=

# Development
DEV_SECRET=local-dev-secret
```

### Frontend (`apps/web/.env.local`)

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## 📊 Data Models

### Core Entities (55+ tables)

| Category | Models |
|----------|--------|
| **Auth** | Organization, User, Membership, AuthIdentity, OrgInvite, RolePermission |
| **Cases** | Case, CaseStatusHistory, CaseActivityLog, MetaLead, CaseImport |
| **Relationships** | IntendedParent, Match, MatchEvent |
| **Tasks** | Task, EntityNote, Attachment |
| **Forms** | Form, FormSubmission, FormSubmissionToken, FormFieldMapping |
| **Automation** | AutomationWorkflow, WorkflowExecution, EmailTemplate, EmailLog |
| **Campaigns** | Campaign, CampaignRun, CampaignRecipient, EmailSuppression |
| **Scheduling** | Appointment, AppointmentType, AvailabilityRule, BookingLink |
| **AI** | AISettings, AIConversation, AIMessage, AIEntitySummary |
| **Operations** | Job, Notification, IntegrationHealth, SystemAlert, AuditLog |
| **Config** | Pipeline, PipelineStage, EntityVersion, UserIntegration |

---

## 🔐 Security

- **Authentication**: Cookie-based JWT sessions with Google OAuth
- **Authorization**: Role-based access control (RBAC) with granular permissions
- **CSRF Protection**: Required header on all mutations
- **Multi-Factor**: TOTP and Duo Security integration
- **Encryption**: Fernet encryption for OAuth tokens and sensitive configs
- **Audit**: Hash-chain logging with tamper detection
- **Data Isolation**: All queries scoped by organization_id

### Roles

| Role | Description |
|------|-------------|
| `intake_specialist` | Lead intake and initial processing |
| `case_manager` | Full case management access |
| `admin` | Administrative access, analytics, team management |
| `developer` | Platform administration, all permissions |

---

## 📚 Documentation

- **[DESIGN.md](./docs/DESIGN.md)** — Architecture decisions and patterns
- **[CHANGELOG.md](./CHANGELOG.md)** — Version history and release notes
- **[automation.md](./docs/automation.md)** — Workflow automation guide
- **[oauth-setup-guide.md](./docs/oauth-setup-guide.md)** — Integration configuration

---

## 🧪 Testing

### Backend
```bash
cd apps/api
pytest
```

### Frontend
```bash
cd apps/web
pnpm test        # Unit tests
pnpm test:integration  # Integration tests
```

---

## 🚢 Deployment

### Health Endpoints
- `/health/live` — Liveness probe
- `/health/ready` — Readiness probe (checks DB)

### Recommended Stack
- **Frontend**: Vercel
- **Backend**: Cloud Run, Railway, or Render
- **Database**: Cloud SQL or Supabase
- **Storage**: S3-compatible for file uploads

---

## 📝 License

Private — All rights reserved.

---

## 🤝 Contributing

This is a private project. For questions or access, contact the maintainers.
