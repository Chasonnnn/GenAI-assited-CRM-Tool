# Surrogacy Force Platform

**Version:** 0.22.0 | **Last Updated:** January 19, 2026

A modern, multi-tenant Surrogacy Force platform purpose-built for surrogacy agencies. Manage surrogates from lead intake through delivery with customizable pipelines, intended parent matching, AI-powered assistance, and comprehensive automation.

---

## ✨ Key Features

### Surrogate Management
- **Customizable Pipelines** — Define stages, colors, and workflows per organization
- **Surrogate Claim Workflow** — Intake-to-case-manager claim flow via queues
- **Activity Logging** — Complete audit trail of all surrogate actions
- **Queue System** — Salesforce-style claim/release for workload distribution

### Form Builder
- **Dynamic Forms** — Create multi-page application forms with drag-and-drop
- **Secure Public Links** — Token-based form access for applicants
- **Auto-Mapping** — Form submissions auto-populate surrogate fields on approval
- **File Uploads** — Secure document collection with virus scanning

### Matching & Coordination
- **IP-Surrogate Matching** — Propose, review, accept/reject workflow
- **Shared Calendar** — Coordinated scheduling across match parties
- **Notes & Files** — Centralized documentation per match

### Automation
- **Workflow Engine** — Event-driven automation with approvals and scheduling hooks
- **Workflow Approvals** — Human-in-the-loop gating for sensitive actions
- **Email Campaigns** — Bulk sends with recipient filtering and tracking
- **Email Templates** — Customizable templates with variable substitution

### AI Assistant (Optional)
- **BYOK Model** — Bring your own API key (OpenAI, etc.)
- **Surrogate Summarization** — AI-generated surrogate and interview summaries
- **Schedule Parsing** — Extract meeting intent into tasks or appointments
- **Smart Task Creation** — Suggest tasks from surrogate and match context
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
- **Notifications** — Browser push alerts with per-user preferences
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
│       └── lib/                # API client, hooks, schemas, utilities
│
├── docs/                       # Documentation
│   ├── DESIGN.md               # Architecture documentation
│   ├── automation.md           # Automation system guide
│   ├── oauth-setup-guide.md    # Integration setup
│   ├── agents.md               # Agent rules and workflows
│   ├── email-template-variables.md # Email template variables reference
│   ├── gcp-oidc-deploy.md      # GCP deployment notes
│   ├── FEATURE_GAPS.md         # Known gaps and roadmap
│   └── ROADMAP.txt             # Planning notes
│
├── load-tests/                 # k6 and performance scripts
├── CHANGELOG.md                # Version history
├── CLAUDE.md                   # Project conventions and rules
├── release-please-config.json  # Release automation config
├── zap-baseline.conf           # ZAP baseline scan config
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

# Bootstrap first organization (portal domain optional)
python -m app.cli create-org --name "Your Agency" --slug "agency" --admin-email "admin@agency.com"
# Optional: derive portal domain as ap.<domain>
python -m app.cli create-org --name "Your Agency" --slug "agency" --admin-email "admin@agency.com" --base-domain "agency.com"
# Optional: set explicit portal domain
python -m app.cli create-org --name "Your Agency" --slug "agency" --admin-email "admin@agency.com" --portal-domain "ap.agency.com"

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
# Environment
ENV=dev

# Database
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/crm

# Authentication (JWT in HTTP-only cookie)
JWT_SECRET=your-secret-key-minimum-32-characters
JWT_SECRET_PREVIOUS=
JWT_EXPIRES_HOURS=4
# Cookie SameSite policy (lax, strict, none). None requires HTTPS.
COOKIE_SAMESITE=lax

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Encryption (required)
FERNET_KEY=generate-with-Fernet.generate_key()
DATA_ENCRYPTION_KEY=generate-with-Fernet.generate_key()
PII_HASH_KEY=generate-with-secrets.token_urlsafe(32)
VERSION_ENCRYPTION_KEY=generate-with-Fernet.generate_key()

# Frontend
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000

# Integrations (optional)
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
ZOOM_REDIRECT_URI=http://localhost:8000/integrations/zoom/callback
GMAIL_REDIRECT_URI=http://localhost:8000/integrations/gmail/callback

# Meta Lead Ads (optional)
META_APP_ID=
META_APP_SECRET=
META_VERIFY_TOKEN=
META_ENCRYPTION_KEY=
META_AD_ACCOUNT_ID=
META_SYSTEM_TOKEN=
META_PIXEL_ID=
META_CAPI_ENABLED=false

# Development
DEV_SECRET=local-dev-secret
```

### Frontend (`apps/web/.env.local`)

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## 🔧 Local Development Setup

### Dev Login-As (Skip Google OAuth)

For local development without configuring Google OAuth:

1. **Backend** (`apps/api/.env`):
   ```env
   DEV_SECRET=local-dev-secret
   ENV=dev
   ```

2. Start the API and web apps.

3. Export the dev secret for curl (or replace `$DEV_SECRET` below with the literal value):
   ```bash
   export DEV_SECRET=local-dev-secret
   ```

4. Seed a test org and users (returns user IDs):
   ```bash
   curl -s -X POST http://localhost:8000/dev/seed \
     -H "X-Dev-Secret: $DEV_SECRET"
   ```

5. Pick a `user_id` from the response.

6. Log in from the browser (recommended; this stores cookies in the browser):
   ```js
   await fetch("/api/dev/login-as/<user_id>", {
     method: "POST",
     headers: { "X-Dev-Secret": "<your dev secret>" },
     credentials: "include",
   }).then((r) => r.json())
   ```

7. Refresh the browser — you should now be authenticated.

Note: `curl -i` against `/dev/login-as` is useful for inspecting `Set-Cookie`, but it does not log your browser in.

### Database Reset & Seed

When you need a fresh database:

```bash
# 1. Reset database (removes all data)
docker-compose down -v && docker-compose up -d

# 2. Run migrations
cd apps/api
.venv/bin/python -m alembic upgrade head

# 3. Seed a test org and users (dev endpoints)
curl -s -X POST http://localhost:8000/dev/seed \
  -H "X-Dev-Secret: $DEV_SECRET"

# 4. Log in from the browser (see Dev Login-As steps above)
#    This ensures cookies are stored in the browser.
```

### Required Encryption Keys

Generate and add these to `apps/api/.env`:

```bash
# Generate keys
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Required in .env:
DATA_ENCRYPTION_KEY=<generated-key>
META_ENCRYPTION_KEY=<generated-key>
```

Without these, you'll get "DATA_ENCRYPTION_KEY not configured" errors.

---

## 📊 Data Models

### Core Entities (55+ tables)

| Category | Models |
|----------|--------|
| **Auth** | Organization, User, Membership, AuthIdentity, OrgInvite, RolePermission |
| **Surrogates** | Surrogate, SurrogateStatusHistory, SurrogateActivityLog, MetaLead, SurrogateImport |
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
- **Encryption**: Fernet encryption for OAuth tokens, PII fields, and versioned configs
- **Audit**: Hash-chain logging with tamper detection
- **Data Isolation**: All queries scoped by organization_id

### Roles

| Role | Description |
|------|-------------|
| `intake_specialist` | Lead intake and initial processing |
| `case_manager` | Full surrogate management access |
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
pnpm test            # Unit tests
pnpm test:integration  # Integration tests
pnpm test:all        # Full frontend suite
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
- **Proxy headers**: Set `TRUST_PROXY_HEADERS=true` behind Cloud Run/LB

### Custom Domains (Branded Redirect Portals)
Use per-client subdomains as branded entry points that redirect to your primary app domain.

1) Create subdomains
- Portal: `ap.clientdomain.com`

2) Domain mapping (Cloud Run)
- Map `ap.clientdomain.com` to a single redirect service that 308-redirects to your primary app.

3) DNS (CNAME)
- Point `ap` to the redirect service target hostname provided by Cloud Run.
  - For Wix-managed domains, use subdomain CNAMEs (avoid apex CNAMEs)

4) Env vars (stay on the primary domains)
- Backend:
  - `FRONTEND_URL=https://app.yourdomain.com`
  - `CORS_ORIGINS=https://app.yourdomain.com`
  - `API_BASE_URL=https://api.yourdomain.com`
- Frontend:
  - `NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com`

5) Set the org portal domain (drives public links for forms, booking, invites)
- Settings → Organization → Portal Domain: `ap.clientdomain.com`
- Or set on org creation:
  - `--base-domain "clientdomain.com"` (builds `ap.clientdomain.com`)
  - `--portal-domain "ap.clientdomain.com"`

Note: A fully hosted per-client portal (no redirect) requires HTTPS and either
same-site hosting for UI + API or `COOKIE_SAMESITE=none` plus updated `CORS_ORIGINS`
to include the portal domain.

---

## 📝 License

Private — All rights reserved.

---

## 🤝 Contributing

This is a private project. For questions or access, contact the maintainers.
