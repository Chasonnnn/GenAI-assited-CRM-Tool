# agents.md — Surrogacy Force Platform

> The single source of truth for building this project. Every contributor (human or AI) must follow these rules.

---

## 1) Commands (Quick Reference)

### Backend (apps/api)
```bash
# Start dev server
cd apps/api && uv sync --extra test
cd apps/api && uv run -- uvicorn app.main:app --reload

# Run all tests
cd apps/api && uv run -m pytest -v

# Run specific test file
cd apps/api && uv run -m pytest tests/test_auth.py -v

# Format & lint
ruff check . --fix && ruff format .

# Run migrations
cd apps/api && uv run -m alembic upgrade head

# Create new migration
cd apps/api && uv run -m alembic revision --autogenerate -m "description"

# Migration naming convention: YYYYMMDD_HHMM_<slug>.py
# Use a time-based rev-id + slug to match filename pattern
cd apps/api && uv run -m alembic revision --autogenerate --rev-id 20260111_1420 -m "add_surrogate_flags"

# Baseline reset (rare)
# 1) Archive old versions/ to versions_archive/
# 2) Generate a consolidated baseline in versions/
# 3) Stamp all existing DBs to the new revision
#    uv run -m alembic stamp --purge <new_revision_id>
# 4) Verify alembic upgrade head is a no-op

# Bootstrap org (CLI)
cd apps/api && uv run -m app.cli create-org
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

### Utilities
```bash
# Ripgrep (fast search)
rg -n "pattern" path
rg --files

# Python (system)
python3 - <<'PY'
print("inline script")
PY

# Regenerate frontend stage constants (build-time sync)
cd apps/api && uv run -- python scripts/gen_stage_map.py
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

Accessibility compatibility is not required unless explicitly requested.

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
@router.post("/surrogates")
async def create_surrogate(
    data: SurrogateCreate,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(require_roles(["intake_specialist", "case_manager"]))
):
    return surrogate_service.create(session, data, user)

# ✅ Explicit transactions
async with session.begin():
    surrogate = Surrogate(**data.dict())
    session.add(surrogate)
    session.add(SurrogateActivityLog(surrogate_id=surrogate.id, action="created"))

# ✅ Scoped by org
query = select(Surrogate).where(Surrogate.organization_id == user.org_id)

# ✅ Timezone-aware UTC
created_at: datetime = Column(DateTime(timezone=True), default=func.now())
```

### Frontend Patterns
```typescript
// ✅ Typed API client
export async function createSurrogate(data: SurrogateCreate): Promise<Surrogate> {
    const res = await fetch(`${API_BASE}/surrogates`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
        credentials: "include",
        body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
}

// ✅ React Query hook
export function useCreateSurrogate() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: createSurrogate,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["surrogates"] }),
    })
}

// ✅ TanStack Query for server data, Zustand for UI only
const { data: surrogates } = useSurrogates({ status: "active" })
const sidebarOpen = useUIStore(s => s.sidebarOpen)
```

---

## 6) Testing

### TDD Rule
Write or update tests FIRST. Start with a failing test that captures the change, then implement code until it passes. If behavior changes, update tests in the same PR.

When I report a bug, don't start by trying to fix it. Instead, start by writing a test that reproduces the bug. Then, have subagents try to fix the bug and prove it with a passing test.

### Backend Tests
```python
# tests/test_surrogates.py
def test_create_surrogate_requires_auth(client):
    res = client.post("/surrogates", json={"name": "Test"})
    assert res.status_code == 401

def test_surrogate_scoped_to_org(client, auth_headers_org1, auth_headers_org2):
    # Create surrogate in org1
    res = client.post("/surrogates", json={...}, headers=auth_headers_org1)
    surrogate_id = res.json()["id"]
    
    # Org2 cannot see it
    res = client.get(f"/surrogates/{surrogate_id}", headers=auth_headers_org2)
    assert res.status_code == 404
```

### Frontend Tests
```typescript
// tests/surrogates.test.tsx
describe("SurrogatesPage", () => {
    it("renders loading state", () => {
        mockUseSurrogates.mockReturnValue({ data: null, isLoading: true })
        render(<SurrogatesPage />)
        expect(screen.getByText("Surrogates")).toBeInTheDocument()
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
cd apps/web && pnpm test --run tests/surrogates.test.tsx
```

---

## 7) Git Workflow

### Commit Prefix Rule
- All commits must start with a conventional prefix: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, or `chore:`.

### Commit Message Format
```
feat: Add bulk task completion endpoint
fix: Resolve CSRF validation on file upload
docs: Update agents.md with new commands
refactor: Simplify surrogate access checks
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
class Surrogate(Base):
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
```

Every query scopes by org:
```python
query = select(Surrogate).where(
    Surrogate.organization_id == user.org_id,
    Surrogate.is_archived == False
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
user = Depends(require_roles(["admin", "case_manager"]))
user = Depends(require_membership())
csrf = Depends(require_csrf_header)

# ❌ Avoid scattered checks
if request.user.role == "admin":  # Don't do this
```

### Cookie Sessions + CSRF
```python
# Frontend: always include credentials
fetch(url, { credentials: "include", headers: { "X-Requested-With": "XMLHttpRequest" } })

# Backend: validate CSRF header on mutations
@router.post("/surrogates", dependencies=[Depends(require_csrf_header)])
```

---

## 10) Version Numbering

Format: **MAJOR.MINOR.PATCH** (SemVer)

| Part | Meaning |
|------|---------|
| MAJOR | Breaking changes |
| MINOR | New features |
| PATCH | Fixes and maintenance |

Pre-1.0 policy: stay in `0.x` even for breaking changes (Release Please uses `bump-minor-pre-major`).

Examples:
- `0.16.0` → Pre-release, feature update
- `1.2.5` → Stable release with patch fixes

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
API_BASE_URL=http://localhost:8000
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
- Surrogate (with sequential surrogate_number: S10001+)
- IntendedParent (with sequential intended_parent_number: I10001+)
- Match (surrogate ↔ IP)
- Task, Note, Attachment
- Appointment, Notification

### Surrogate Status Flow
```
new_unread → contacted → qualified → interview_scheduled → application_submitted
→ under_review → approved → ready_to_match → matched → medical_clearance_passed
→ legal_clearance_passed → transfer_cycle → second_hcg_confirmed → heartbeat_confirmed
→ ob_care_established → anatomy_scanned → delivered

Terminal (intake-only): lost, disqualified
```

---

## 13) Current Status

- **Version:** 0.16.0
- **Completed:** Auth, surrogates, IPs, matches, tasks, notes, attachments, notifications, calendar, bulk operations, filter persistence, automation workflows, campaigns, queue management
- **Stack:** Next.js 16, React 19, FastAPI, PostgreSQL, SQLAlchemy 2.0

<!-- NEXT-AGENTS-MD-START -->[Next.js Docs Index]|root: ./.next-docs|STOP. What you remember about Next.js is WRONG for this project. Always search docs and read before any task.|If docs missing, run this command first: npx @next/codemod agents-md --output AGENTS.md|01-app:{glossary.mdx}|01-app/01-getting-started:{01-installation.mdx,02-project-structure.mdx,03-layouts-and-pages.mdx,04-linking-and-navigating.mdx,05-server-and-client-components.mdx,06-cache-components.mdx,07-fetching-data.mdx,08-updating-data.mdx,09-caching-and-revalidating.mdx,10-error-handling.mdx,11-css.mdx,12-images.mdx,13-fonts.mdx,14-metadata-and-og-images.mdx,15-route-handlers.mdx,16-proxy.mdx,17-deploying.mdx,18-upgrading.mdx}|01-app/02-guides:{analytics.mdx,authentication.mdx,backend-for-frontend.mdx,caching.mdx,ci-build-caching.mdx,content-security-policy.mdx,css-in-js.mdx,custom-server.mdx,data-security.mdx,debugging.mdx,draft-mode.mdx,environment-variables.mdx,forms.mdx,incremental-static-regeneration.mdx,instrumentation.mdx,internationalization.mdx,json-ld.mdx,lazy-loading.mdx,local-development.mdx,mcp.mdx,mdx.mdx,memory-usage.mdx,multi-tenant.mdx,multi-zones.mdx,open-telemetry.mdx,package-bundling.mdx,prefetching.mdx,production-checklist.mdx,progressive-web-apps.mdx,redirecting.mdx,sass.mdx,scripts.mdx,self-hosting.mdx,single-page-applications.mdx,static-exports.mdx,tailwind-v3-css.mdx,third-party-libraries.mdx,videos.mdx}|01-app/02-guides/migrating:{app-router-migration.mdx,from-create-react-app.mdx,from-vite.mdx}|01-app/02-guides/testing:{cypress.mdx,jest.mdx,playwright.mdx,vitest.mdx}|01-app/02-guides/upgrading:{codemods.mdx,version-14.mdx,version-15.mdx,version-16.mdx}|01-app/03-api-reference:{07-edge.mdx,08-turbopack.mdx}|01-app/03-api-reference/01-directives:{use-cache-private.mdx,use-cache-remote.mdx,use-cache.mdx,use-client.mdx,use-server.mdx}|01-app/03-api-reference/02-components:{font.mdx,form.mdx,image.mdx,link.mdx,script.mdx}|01-app/03-api-reference/03-file-conventions/01-metadata:{app-icons.mdx,manifest.mdx,opengraph-image.mdx,robots.mdx,sitemap.mdx}|01-app/03-api-reference/03-file-conventions:{default.mdx,dynamic-routes.mdx,error.mdx,forbidden.mdx,instrumentation-client.mdx,instrumentation.mdx,intercepting-routes.mdx,layout.mdx,loading.mdx,mdx-components.mdx,not-found.mdx,page.mdx,parallel-routes.mdx,proxy.mdx,public-folder.mdx,route-groups.mdx,route-segment-config.mdx,route.mdx,src-folder.mdx,template.mdx,unauthorized.mdx}|01-app/03-api-reference/04-functions:{after.mdx,cacheLife.mdx,cacheTag.mdx,connection.mdx,cookies.mdx,draft-mode.mdx,fetch.mdx,forbidden.mdx,generate-image-metadata.mdx,generate-metadata.mdx,generate-sitemaps.mdx,generate-static-params.mdx,generate-viewport.mdx,headers.mdx,image-response.mdx,next-request.mdx,next-response.mdx,not-found.mdx,permanentRedirect.mdx,redirect.mdx,refresh.mdx,revalidatePath.mdx,revalidateTag.mdx,unauthorized.mdx,unstable_cache.mdx,unstable_noStore.mdx,unstable_rethrow.mdx,updateTag.mdx,use-link-status.mdx,use-params.mdx,use-pathname.mdx,use-report-web-vitals.mdx,use-router.mdx,use-search-params.mdx,use-selected-layout-segment.mdx,use-selected-layout-segments.mdx,userAgent.mdx}|01-app/03-api-reference/05-config/01-next-config-js:{adapterPath.mdx,allowedDevOrigins.mdx,appDir.mdx,assetPrefix.mdx,authInterrupts.mdx,basePath.mdx,browserDebugInfoInTerminal.mdx,cacheComponents.mdx,cacheHandlers.mdx,cacheLife.mdx,compress.mdx,crossOrigin.mdx,cssChunking.mdx,devIndicators.mdx,distDir.mdx,env.mdx,expireTime.mdx,exportPathMap.mdx,generateBuildId.mdx,generateEtags.mdx,headers.mdx,htmlLimitedBots.mdx,httpAgentOptions.mdx,images.mdx,incrementalCacheHandlerPath.mdx,inlineCss.mdx,isolatedDevBuild.mdx,logging.mdx,mdxRs.mdx,onDemandEntries.mdx,optimizePackageImports.mdx,output.mdx,pageExtensions.mdx,poweredByHeader.mdx,productionBrowserSourceMaps.mdx,proxyClientMaxBodySize.mdx,reactCompiler.mdx,reactMaxHeadersLength.mdx,reactStrictMode.mdx,redirects.mdx,rewrites.mdx,sassOptions.mdx,serverActions.mdx,serverComponentsHmrCache.mdx,serverExternalPackages.mdx,staleTimes.mdx,staticGeneration.mdx,taint.mdx,trailingSlash.mdx,transpilePackages.mdx,turbopack.mdx,turbopackFileSystemCache.mdx,typedRoutes.mdx,typescript.mdx,urlImports.mdx,useLightningcss.mdx,viewTransition.mdx,webVitalsAttribution.mdx,webpack.mdx}|01-app/03-api-reference/05-config:{02-typescript.mdx,03-eslint.mdx}|01-app/03-api-reference/06-cli:{create-next-app.mdx,next.mdx}|02-pages/01-getting-started:{01-installation.mdx,02-project-structure.mdx,04-images.mdx,05-fonts.mdx,06-css.mdx,11-deploying.mdx}|02-pages/02-guides:{analytics.mdx,authentication.mdx,babel.mdx,ci-build-caching.mdx,content-security-policy.mdx,css-in-js.mdx,custom-server.mdx,debugging.mdx,draft-mode.mdx,environment-variables.mdx,forms.mdx,incremental-static-regeneration.mdx,instrumentation.mdx,internationalization.mdx,lazy-loading.mdx,mdx.mdx,multi-zones.mdx,open-telemetry.mdx,package-bundling.mdx,post-css.mdx,preview-mode.mdx,production-checklist.mdx,redirecting.mdx,sass.mdx,scripts.mdx,self-hosting.mdx,static-exports.mdx,tailwind-v3-css.mdx,third-party-libraries.mdx}|02-pages/02-guides/migrating:{app-router-migration.mdx,from-create-react-app.mdx,from-vite.mdx}|02-pages/02-guides/testing:{cypress.mdx,jest.mdx,playwright.mdx,vitest.mdx}|02-pages/02-guides/upgrading:{codemods.mdx,version-10.mdx,version-11.mdx,version-12.mdx,version-13.mdx,version-14.mdx,version-9.mdx}|02-pages/03-building-your-application/01-routing:{01-pages-and-layouts.mdx,02-dynamic-routes.mdx,03-linking-and-navigating.mdx,05-custom-app.mdx,06-custom-document.mdx,07-api-routes.mdx,08-custom-error.mdx}|02-pages/03-building-your-application/02-rendering:{01-server-side-rendering.mdx,02-static-site-generation.mdx,04-automatic-static-optimization.mdx,05-client-side-rendering.mdx}|02-pages/03-building-your-application/03-data-fetching:{01-get-static-props.mdx,02-get-static-paths.mdx,03-forms-and-mutations.mdx,03-get-server-side-props.mdx,05-client-side.mdx}|02-pages/03-building-your-application/06-configuring:{12-error-handling.mdx}|02-pages/04-api-reference:{06-edge.mdx,08-turbopack.mdx}|02-pages/04-api-reference/01-components:{font.mdx,form.mdx,head.mdx,image-legacy.mdx,image.mdx,link.mdx,script.mdx}|02-pages/04-api-reference/02-file-conventions:{instrumentation.mdx,proxy.mdx,public-folder.mdx,src-folder.mdx}|02-pages/04-api-reference/03-functions:{get-initial-props.mdx,get-server-side-props.mdx,get-static-paths.mdx,get-static-props.mdx,next-request.mdx,next-response.mdx,use-params.mdx,use-report-web-vitals.mdx,use-router.mdx,use-search-params.mdx,userAgent.mdx}|02-pages/04-api-reference/04-config/01-next-config-js:{adapterPath.mdx,allowedDevOrigins.mdx,assetPrefix.mdx,basePath.mdx,bundlePagesRouterDependencies.mdx,compress.mdx,crossOrigin.mdx,devIndicators.mdx,distDir.mdx,env.mdx,exportPathMap.mdx,generateBuildId.mdx,generateEtags.mdx,headers.mdx,httpAgentOptions.mdx,images.mdx,isolatedDevBuild.mdx,onDemandEntries.mdx,optimizePackageImports.mdx,output.mdx,pageExtensions.mdx,poweredByHeader.mdx,productionBrowserSourceMaps.mdx,proxyClientMaxBodySize.mdx,reactStrictMode.mdx,redirects.mdx,rewrites.mdx,serverExternalPackages.mdx,trailingSlash.mdx,transpilePackages.mdx,turbopack.mdx,typescript.mdx,urlImports.mdx,useLightningcss.mdx,webVitalsAttribution.mdx,webpack.mdx}|02-pages/04-api-reference/04-config:{01-typescript.mdx,02-eslint.mdx}|02-pages/04-api-reference/05-cli:{create-next-app.mdx,next.mdx}|03-architecture:{accessibility.mdx,fast-refresh.mdx,nextjs-compiler.mdx,supported-browsers.mdx}|04-community:{01-contribution-guide.mdx,02-rspack.mdx}<!-- NEXT-AGENTS-MD-END -->
