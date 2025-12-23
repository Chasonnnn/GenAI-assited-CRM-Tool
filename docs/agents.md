# agents.md — Surrogacy CRM Platform

> The single source of truth for building this project. Every contributor (human or AI) must follow these rules.

---

## 1) Commands (Quick Reference)

### Backend (apps/api)
```bash
# Start dev server
cd apps/api && PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --reload

# Run all tests
cd apps/api && python -m pytest -v

# Run specific test file
cd apps/api && python -m pytest tests/test_auth.py -v

# Format & lint
ruff check . --fix && ruff format .

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Bootstrap org (CLI)
python -m app.cli create-org
```

### Frontend (apps/web)
```bash
# Start dev server
cd apps/web && pnpm dev

# Type check
pnpm tsc --noEmit

# Run tests
pnpm test --run

# Lint
pnpm lint
```

### Database
```bash
# Start Postgres (Docker)
docker compose up -d postgres

# Connect to DB
psql postgresql://user:pass@localhost:5432/crm_dev
```

---

## 2) Boundaries (Non-Negotiable)

### 🔴 NEVER
| Rule | Reason |
|------|--------|
| **Never commit secrets** | Use `.env` files, keep `.env.example` updated |
| **Never log raw PII** | Mask sensitive data in logs |
| **Never expose API keys in responses** | Keys are write-only |
| **Never auto-send AI messages** | Require human review |
| **Never skip org scoping** | Every query must filter by `organization_id` |

### 🟡 Zero-Tolerance Policy
```markdown
Fix these IMMEDIATELY when they appear:
- Build warnings (TypeScript, lint, deprecations)
- Test failures
- Runtime warnings (React hooks, Next.js)
- Performance issues (N+1 queries, memory leaks)
- Security vulnerabilities
```

### 🟢 Backward Compatibility
```markdown
This is an in-house project. Breaking changes are ACCEPTABLE:
- Prioritize clean design over legacy support
- Make the best architectural choice, not the compatible one
- Users can re-migrate/re-sync as needed
```

### Production-Quality Standard
```markdown
Build FULLY FUNCTIONAL, POLISHED features — not MVPs.

✅ Required:
- Complete error handling & loading states
- Validation & edge cases covered
- Accessibility (keyboard nav, screen readers)
- Visual polish (consistent styling, transitions)

❌ Forbidden:
- "Basic" or "minimal" implementations
- Missing error/loading states
- "TODO: Add feature X later" comments
- Placeholder text instead of functionality
```

---

## 3) Tech Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| Next.js 16 (App Router) | Framework |
| TypeScript (strict) | Type safety |
| Tailwind CSS + shadcn/ui | Styling |
| TanStack Query | Server state |
| Zustand | UI state only |
| React Hook Form + Zod | Forms + validation |

### Backend
| Technology | Purpose |
|------------|---------|
| FastAPI | API framework |
| Pydantic v2 | Validation |
| PostgreSQL | Database |
| SQLAlchemy 2.0 + Alembic | ORM + migrations |
| Cookie JWT + Google OAuth | Authentication |

---

## 4) Project Structure

```
/apps
  /api
    /app
      /routers      # FastAPI endpoints (thin)
      /services     # Business logic
      /models       # SQLAlchemy ORM
      /schemas      # Pydantic DTOs
      /core         # Config, security
      /db           # Session, engine
    /tests
    /alembic        # Migrations
    
  /web
    /app
      /(auth)       # Login pages
      /(app)        # Authenticated pages
    /components     # Shared UI
    /lib
      /api          # API clients
      /hooks        # React Query hooks
      /types        # TypeScript types
    /tests
```

---

## 5) Code Style

### Backend Patterns
```python
# ✅ Thin routers, logic in services
@router.post("/cases")
async def create_case(
    data: CaseCreate,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(require_roles(["intake_specialist", "case_manager"]))
):
    return case_service.create(session, data, user)

# ✅ Explicit transactions
async with session.begin():
    case = Case(**data.dict())
    session.add(case)
    session.add(CaseActivityLog(case_id=case.id, action="created"))

# ✅ Scoped by org
query = select(Case).where(Case.organization_id == user.org_id)

# ✅ Timezone-aware UTC
created_at: datetime = Column(DateTime(timezone=True), default=func.now())
```

### Frontend Patterns
```typescript
// ✅ Typed API client
export async function createCase(data: CaseCreate): Promise<Case> {
    const res = await fetch(`${API_BASE}/cases`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
        credentials: "include",
        body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
}

// ✅ React Query hook
export function useCreateCase() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: createCase,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cases"] }),
    })
}

// ✅ TanStack Query for server data, Zustand for UI only
const { data: cases } = useCases({ status: "active" })
const sidebarOpen = useUIStore(s => s.sidebarOpen)
```

---

## 6) Testing

### Backend Tests
```python
# tests/test_cases.py
def test_create_case_requires_auth(client):
    res = client.post("/cases", json={"name": "Test"})
    assert res.status_code == 401

def test_case_scoped_to_org(client, auth_headers_org1, auth_headers_org2):
    # Create case in org1
    res = client.post("/cases", json={...}, headers=auth_headers_org1)
    case_id = res.json()["id"]
    
    # Org2 cannot see it
    res = client.get(f"/cases/{case_id}", headers=auth_headers_org2)
    assert res.status_code == 404
```

### Frontend Tests
```typescript
// tests/cases.test.tsx
describe("CasesPage", () => {
    it("renders loading state", () => {
        mockUseCases.mockReturnValue({ data: null, isLoading: true })
        render(<CasesPage />)
        expect(screen.getByText("Cases")).toBeInTheDocument()
    })
})
```

### Test Commands
```bash
# Backend: run all
cd apps/api && python -m pytest -v

# Frontend: run all  
cd apps/web && pnpm test --run

# Frontend: run specific
cd apps/web && pnpm test --run tests/cases.test.tsx
```

---

## 7) Git Workflow

### Commit Message Format
```
feat: Add bulk task completion endpoint
fix: Resolve CSRF validation on file upload
docs: Update agents.md with new commands
refactor: Simplify case access checks
test: Add coverage for notification service
```

### Before Committing
```bash
# Backend
cd apps/api && ruff check . --fix && python -m pytest -v

# Frontend
cd apps/web && pnpm tsc --noEmit && pnpm test --run

# Then commit
git add -A && git commit -m "feat: Description"
```

### PR Checklist
- [ ] All tests pass
- [ ] No TypeScript errors
- [ ] No lint warnings
- [ ] `.env.example` updated if new vars
- [ ] Docs updated if behavior changes

---

## 8) Multi-Tenancy Rules

Every domain entity includes `organization_id`:
```python
class Case(Base):
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
```

Every query scopes by org:
```python
query = select(Case).where(
    Case.organization_id == user.org_id,
    Case.is_archived == False
)
```

One user = one organization (via Membership):
```python
membership = session.scalar(
    select(Membership).where(Membership.user_id == user.id)
)
org_id = membership.organization_id
```

---

## 9) Authorization Patterns

### Centralized Dependencies
```python
# ✅ Use these
user = Depends(require_roles(["manager", "case_manager"]))
user = Depends(require_membership())
csrf = Depends(require_csrf_header)

# ❌ Avoid scattered checks
if request.user.role == "manager":  # Don't do this
```

### Cookie Sessions + CSRF
```python
# Frontend: always include credentials
fetch(url, { credentials: "include", headers: { "X-Requested-With": "XMLHttpRequest" } })

# Backend: validate CSRF header on mutations
@router.post("/cases", dependencies=[Depends(require_csrf_header)])
```

---

## 10) Version Numbering

Format: **a.bc.de**

| Part | Range | Meaning |
|------|-------|---------|
| a | 0-9 | Major (0 = pre-release) |
| bc | 00-99 | Feature additions |
| de | 00-99 | Patches/fixes |

Examples:
- `0.06.00` → Pre-release, 6 features
- `1.02.05` → Production v1, 2 features, 5 patches

Current: See `apps/api/app/core/config.py` → `Settings.VERSION`

---

## 11) Environment Variables

### Backend (.env)
```bash
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/crm_dev
JWT_SECRET=your-secret-key
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

**Never put secrets in `NEXT_PUBLIC_*` variables.**

---

## 12) Domain Model (V1)

### Core Entities
- Organization, User, Membership
- Case (with sequential case_number)
- IntendedParent
- Match (case ↔ IP)
- Task, Note, Attachment
- Appointment, Notification

### Case Status Flow
```
new_unread → contacted → qualified → applied → under_review → approved 
→ pending_handoff → pending_match → meds_started → exam_passed 
→ embryo_transferred → delivered
```

---

## 13) Current Status

- **Version:** 0.09.00+
- **Completed:** Auth, cases, IPs, matches, tasks, notes, attachments, notifications, calendar, bulk operations, filter persistence
- **Stack:** Next.js 16, React 19, FastAPI, PostgreSQL, SQLAlchemy 2.0
