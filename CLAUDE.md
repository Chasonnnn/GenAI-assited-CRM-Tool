# Surrogacy CRM Platform

> **Version:** 0.16.0 | Multi-tenant CRM for surrogacy agencies

## Project Guidelines

See agents.md for complete coding guidelines.
See @docs/layouts.md for UI design system.

## Quick Reference

### Tech Stack
- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2.0, PostgreSQL 16, Alembic
- **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui
- **State:** TanStack Query (server), Zustand (UI only)
- **Forms:** React Hook Form + Zod

## Boundaries (Non-Negotiable)

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

### 🟢 No-Backward Compatibility
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
- Visual polish (consistent styling, transitions)

❌ Forbidden:
- "Basic" or "minimal" implementations
- Missing error/loading states
- "TODO: Add feature X later" comments
- Placeholder text instead of functionality
```


### Commands

```bash
# Backend
cd apps/api && PYTHONPATH=. .venv/bin/python -m uvicorn app.main:app --reload
cd apps/api && .venv/bin/python -m pytest -v
ruff check . --fix && ruff format .
alembic upgrade head

# Frontend
cd apps/web && pnpm dev
pnpm tsc --noEmit
pnpm test --run

# Build-time stage map (frontend constants)
apps/api/.venv/bin/python scripts/gen_stage_map.py
```

### Core Rules

1. **Multi-tenancy** — Every query must filter by `organization_id`
2. **Thin routers** — Business logic lives in services, not routers
3. **No backward compatibility** — Clean design over legacy support
4. **Production quality** — Complete error handling, loading states, validation
5. **Cookie JWT + CSRF** — Always include `credentials: "include"` and `X-Requested-With` header
6. **Accessibility** — Not required unless explicitly requested

### Roles
- `intake_specialist` — Lead intake
- `case_manager` — Full surrogate management
- `admin` — Administrative access
- `developer` — Platform administration
