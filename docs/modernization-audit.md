# Platform Modernization Audit

> Generated 2026-06-14 by a multi-agent audit (23 agents, 11 stack areas). The stack is already on current versions; this audit assesses whether the code **uses the modern features those versions unlock**.

## Executive Summary

This stack is in an unusual and specific state: every dependency is current (Next 16, React 19.2, Tailwind 4, TanStack Query 5.90, FastAPI 0.136, SQLAlchemy 2.0, Pydantic 2.12), the structural foundations are genuinely good (typed ORM, thin routers, lifespan, Pydantic v2 with no v1 leftovers, CSS-first Tailwind, full Base UI migration, strict TS), but the code consistently uses the PRIOR-generation feature subset of those versions. This is not a "you're behind on versions" audit; it's a "you paid for capabilities you never switched on" audit. The verified evidence is stark: 0 uses of HydrationBoundary/useSuspenseQuery/server-prefetch, 0 useOptimistic and 0 onMutate across ~261 mutations, reactCompiler/typedRoutes/optimizePackageImports all unset, every credential typed as plain str (0 SecretStr), 0 with_loader_criteria org-scoping backstop, and 1511 half-migrated Annotated dependency markers.

Two structural themes dominate everything else and should anchor the roadmap. First, the frontend is a SPA wearing App Router clothing: 278 of 528 files are client components, every page.tsx renders a skeleton then defers all fetching to a client component on mount, and detail pages literally fetch the resource server-side (in getServerRouteResourceStatus) only to throw the body away and refetch it on the client — a guaranteed double round-trip plus a post-mount waterfall. The team is on Next 16 + React 19 + TanStack v5 specifically the versions where server prefetch + HydrationBoundary + useSuspenseQuery is the blessed path, and uses none of it. Second, the backend is a fully-sync SQLAlchemy layer under async FastAPI, with 16 async def handlers calling sync db.commit() directly on the event loop, ~1593 hand-written organization_id filters with zero framework-level enforcement (one miss = cross-tenant leak), 294/296 relationships on default lazy loading with no raiseload guard, and a per-request synchronous Postgres metrics write on the hot path.

The honest priority call: the highest-value work is not the headline architectural rewrites (server components, COPY bulk paths, OTel-everything) — those are high-effort and partly risky. The highest ROI is a cluster of low-effort, high-or-medium-impact items that harden the project's own non-negotiables (org-scoping, no-secret-leakage, no-N+1, no perf regressions) and flip on capabilities that are nearly free: React Compiler, typedRoutes, SecretStr, the SQLAlchemy org-scoping backstop, a global TanStack error handler, type-aware ESLint, and the get_db_for_stream deletion. I'd ship those first, then take on the two big structural shifts (frontend server-data flow; backend async/observability) as deliberate, sequenced initiatives rather than a big bang.

Cross-cutting note on duplicates: React Compiler, optimistic updates, and the Annotated/dependency cleanup each appear in 2-3 separate reports — they're deduped below into single ranked items. Treat the per-area reports as evidence, not as independent backlogs.

## Cross-Cutting Themes

- Frontend is a SPA-on-App-Router: ~278 client files, every page defers all fetching to client-on-mount, 0 Server-Component data prefetch / HydrationBoundary / useSuspenseQuery despite being on the exact Next 16 + React 19 + TanStack v5 versions that make it the blessed path. Detail pages even fetch server-side then discard the body and refetch on the client.
- Manual memoization everywhere instead of the compiler: 389 useMemo + 403 useCallback + brittle dependency arrays in deeply-nested context providers. React Compiler (stable in React 19, one flag in Next 16) is unenabled across THREE reports — it is the single most-repeated recommendation in the whole audit.
- Zero optimistic UI: 0 useOptimistic, 0 onMutate across ~261 mutations; every interaction (notification read, task complete, status change) waits a full round-trip. Flagged independently by the React, TanStack, and Next reports.
- Fully-sync DB under async FastAPI: 16 async def handlers block the event loop on sync db.commit(); a per-request synchronous Postgres metrics write sits on the hot path; sync redis storage used on async rate-limited routes.
- Org-scoping (the #1 non-negotiable) has zero defense-in-depth: ~1593 hand-written organization_id filters and not one framework-level backstop (no with_loader_criteria/do_orm_execute). One forgotten filter is a silent cross-tenant leak.
- Secrets and PII handling lean on convention, not types: every credential is plain str (0 SecretStr) so keys can surface in repr/tracebacks/Sentry; no before_send PII scrubber; single-Fernet data keys with no rotation path — all in direct tension with the 'never log raw PII / keys are write-only' rule.
- Validation logic is hand-rolled and triplicated: the field contract lives as a Pydantic model, a hand-kept TS interface, AND a 130-line imperative intake validator — RHF+Zod is installed but used in exactly one file. Same pattern of 'modern tool installed, legacy code path' as everything else.
- Tooling is configured but switched off: eslint-plugin-react-hooks@7 ships 12+ React-Compiler/Rules-of-React rules with only 2 wired; typescript-eslint runs no type-aware rules; eslint-config-next isn't installed at all; typedRoutes type artifact is generated but enforcement is off.
- Three overlapping observability/error stacks run in parallel (Sentry + GCP Error Reporting + a hand-rolled Postgres metrics writer), with the modern OTel path half-configured-but-disabled in prod — the worst possible state.
- Several genuinely free cleanups recur: half-finished codemods (1511 Annotated 'fastapi_param' markers), dead Radix-era data-[state=*] selectors, orphaned deps (vaul/autoprefixer/tailwindcss-animate), an hsl()-on-oklch color bug, and residual legacy typing — all low-risk consistency wins.

## Top Priorities (ranked, deduped across areas)

| # | Area | Recommendation | Impact | Effort | Breaking |
|---|------|----------------|--------|--------|----------|
| 1 | SQLAlchemy / backend | Add a defense-in-depth org-scoping backstop (with_loader_criteria + do_orm_execute event) | high | high | no |
| 2 | Pydantic / backend security | Type all credentials as SecretStr in Settings | high | medium | yes |
| 3 | React / Next / tooling | Enable the React Compiler (Next 16 reactCompiler flag) + turn on the react-hooks@7 compiler lint rules | high | medium | no |
| 4 | FastAPI / backend perf | Make async handlers that touch the sync Session non-blocking (def, run_in_threadpool, or worker offload) | high | medium | no |
| 5 | TanStack Query / Next / React | Adopt the App Router server-prefetch + HydrationBoundary + useSuspenseQuery SSR flow, reusing the server fetch detail pages already do | high | high | no |
| 6 | TanStack Query / React | Add a global QueryCache/MutationCache onError + optimistic updates for high-frequency mutations | high | medium | no |
| 7 | React Hook Form + Zod / frontend | Replace the imperative intake validator with a Zod 4 schema built from the field model (+ useFieldArray, + shared lib/forms/schema.ts) | high | high | no |
| 8 | SQLAlchemy / backend perf | Make accidental N+1 lazy loads fail loudly (lazy=raise_on_sql / raiseload) | high | medium | yes |
| 9 | FastAPI / backend DX | Finish the Annotated dependency migration with shared type aliases (DbSession / CurrentSession / OrgScope) | high | high | no |
| 10 | Frontend tooling | Add type-aware ESLint (projectService + strict-type-checked) and install eslint-config-next | high | medium | no |
| 11 | Next / frontend | Turn on typedRoutes + optimizePackageImports in next.config.js | medium | low | no |
| 12 | FastAPI / backend cleanup | Delete get_db_for_stream() and stream with the normal get_db dependency | medium | medium | no |
| 13 | Observability / security | Add Sentry release tagging + before_send PII scrubber, and decide Sentry-vs-GCP (kill one) | high | low | no |
| 14 | Backend security | Use MultiFernet for zero-downtime rotation of data/meta encryption keys | high | medium | no |
| 15 | TanStack Query / frontend | Co-locate queries as queryOptions() factories + add react-query-devtools + explicit gcTime/mutation defaults | medium | medium | no |

**1. Add a defense-in-depth org-scoping backstop (with_loader_criteria + do_orm_execute event)** — _SQLAlchemy / backend_  
Org-scoping is the project's #1 non-negotiable and has ZERO framework-level enforcement — ~1593 manual filters, one miss = silent cross-tenant PHI leak. A session-level do_orm_execute listener injecting with_loader_criteria(org_id) is a backstop behind the existing manual filters, not a replacement. Highest-stakes correctness item in the audit.

**2. Type all credentials as SecretStr in Settings** — _Pydantic / backend security_  
Every secret (JWT_SECRET, FERNET_KEY, DATA_ENCRYPTION_KEY, META_APP_SECRET, etc.) is plain str, so any repr(settings) / traceback / Sentry context prints them in cleartext — directly violating 'never log raw PII / keys are write-only'. SecretStr enforces masking at the type level; call-site fan-out is bounded and mechanical (.get_secret_value()).

**3. Enable the React Compiler (Next 16 reactCompiler flag) + turn on the react-hooks@7 compiler lint rules** — _React / Next / tooling_  
The most-repeated recommendation in the entire audit (3 reports). Auto-memoizes 287 client components, lets the team retire 389 useMemo + 403 useCallback and their brittle dependency arrays, and structurally closes the zero-tolerance performance rule. Project meets every prerequisite. Pair with reactHooks.configs.flat.recommended so violations surface before the compiler silently bails. Roll out with rules at 'warn' first.

**4. Make async handlers that touch the sync Session non-blocking (def, run_in_threadpool, or worker offload)** — _FastAPI / backend perf_  
16 verified async def handlers call sync db.commit() directly on the single event loop (meta_callback, upload_attachment, integrations, webhooks, invites, settings...), blocking it for all requests. Convert no-reason-to-be-async handlers to plain def (FastAPI threadpools them safely with the sync Session) and wrap genuine I/O+DB mixes in run_in_threadpool. Concrete, scoped, high-impact.

**5. Adopt the App Router server-prefetch + HydrationBoundary + useSuspenseQuery SSR flow, reusing the server fetch detail pages already do** — _TanStack Query / Next / React_  
The flagship structural fix. Today every page renders a skeleton then fetches client-side on mount; detail pages fetch the resource server-side just to discard it and refetch — a guaranteed double round-trip. Fold the existence check INTO a prefetch, dehydrate, and switch the client hook to useSuspenseQuery so the page.tsx Suspense boundary becomes the single loading UI. Forward cookies + x-org-* exactly as today to preserve scoping. Start with detail/match pages where the server fetch already exists.

**6. Add a global QueryCache/MutationCache onError + optimistic updates for high-frequency mutations** — _TanStack Query / React_  
Two deduped items that pair naturally. ~299 ad-hoc toast.error sites collapse into one global onError (with 401/403 handling and per-call meta opt-out). Separately, 0 optimistic updates across ~261 mutations means notification-read, task-complete, and status-change all wait a round-trip — add onMutate snapshot/rollback (or useOptimistic for client-state UI) to the top few interactions. Both are pure UX/maintainability wins that fit the 'polished, not MVP' standard.

**7. Replace the imperative intake validator with a Zod 4 schema built from the field model (+ useFieldArray, + shared lib/forms/schema.ts)** — _React Hook Form + Zod / frontend_  
RHF+Zod is installed but used in exactly ONE file; the 1684-line public intake form hand-rolls a 130-line validator that re-implements min/max/pattern/coerce that Zod ships natively, and surfaces errors as a single toast instead of inline. A buildFieldSchema() helper validated by one compiled schema replaces three hand-maintained copies of the contract (Pydantic model / TS interface / imperative validator) and moves errors inline. Highest-leverage frontend correctness item outside the data layer.

**8. Make accidental N+1 lazy loads fail loudly (lazy=raise_on_sql / raiseload)** — _SQLAlchemy / backend perf_  
294/296 relationships use default lazy=select with only per-query eager-loading as protection — any code path touching a relationship without explicit loading silently emits an N+1, directly violating the zero-tolerance performance rule. Set lazy=raise_on_sql on hot/large relationships and add raiseload('*') after explicit eager-loads on list endpoints. Roll out per-relationship so eager-loaded paths keep working.

**9. Finish the Annotated dependency migration with shared type aliases (DbSession / CurrentSession / OrgScope)** — _FastAPI / backend DX_  
A half-finished codemod left 1511 meaningless Annotated[X, 'fastapi_param'] = Depends(...) markers across all 74 routers. Adopting Annotated[T, Depends(dep)] + reusable aliases in deps.py removes ~1500 lines of noise, gives one source of truth for auth/db wiring, and is a prerequisite for leaning on FastAPI 0.118's per-request dependency caching. Big DX win, low risk, fully covered by tests.

**10. Add type-aware ESLint (projectService + strict-type-checked) and install eslint-config-next** — _Frontend tooling_  
typescript-eslint runs only 'recommended' with no type info, so no-floating-promises / no-misused-promises can't run despite verified candidates (5 unawaited mutateAsync, 40 async onClick) that silently swallow errors in a human-review product. And eslint-config-next isn't installed at all, so ZERO Next-specific rules run on a Next app (next lint was removed in v16). High correctness value, mostly config.

**11. Turn on typedRoutes + optimizePackageImports in next.config.js** — _Next / frontend_  
Near-free wins. The typedRoutes type artifact is already generated and wired into tsconfig — flipping the flag gives compile-time validation of 56+ <Link href> and router.push across the multi-tenant route trees. optimizePackageImports for fullcalendar/tiptap/react-simple-maps/base-ui trims bundle on heavy client libs. Both low-effort, low-risk.

**12. Delete get_db_for_stream() and stream with the normal get_db dependency** — _FastAPI / backend cleanup_  
A whole bespoke streaming-session contextmanager exists purely to work around pre-0.118 teardown timing that FastAPI 0.118 already fixed — yield-dependency exit now runs AFTER the StreamingResponse finishes. Drop the workaround in ai_chat and audit the other SSE sites. Removes a real source of divergent session lifecycle.

**13. Add Sentry release tagging + before_send PII scrubber, and decide Sentry-vs-GCP (kill one)** — _Observability / security_  
For a PHI-handling app, send_default_pii=False alone doesn't scrub application-level PII in exception values/breadcrumbs/request bodies — a meaningful HIPAA-posture gap fixable with a small before_send hook + release=VERSION. Separately, Sentry AND GCP Error Reporting both fire for the same exception today (duplicate/inconsistent reports); pick one source of truth. Low effort for the scrubber, medium for consolidation.

**14. Use MultiFernet for zero-downtime rotation of data/meta encryption keys** — _Backend security_  
PII-at-rest uses a single Fernet per key with no rotation — changing DATA_ENCRYPTION_KEY makes all existing encrypted PII undecryptable. The JWT path already supports rotation via a previous-secret list; bring data keys to the same maturity with MultiFernet([current, previous]). Important for a HIPAA-style key-rotation policy.

**15. Co-locate queries as queryOptions() factories + add react-query-devtools + explicit gcTime/mutation defaults** — _TanStack Query / frontend_  
Foundational enablers for the SSR and optimistic work above, bundled because they're cheap and synergistic. ~40 hand-rolled key objects drift from their queryFn/options and the 26 setQueryData sites; queryOptions() makes one typed source of truth that useQuery/useSuspenseQuery/prefetchQuery/setQueryData all share. Devtools (dev-only, zero prod cost) makes the heavy invalidation web debuggable. Explicit gcTime/mutations.retry makes prod cache behavior intentional.

## Phased Roadmap

- Phase 0 — Safety & quick wins (days, mostly low-risk): typedRoutes + optimizePackageImports; FastAPI global exception handlers; tiptap.css color fix; remove orphaned deps + dead Base UI selectors; Sentry release+before_send PII scrubber; .python-version + uv lock --locked + tsconfig target bump; ruff pyupgrade cleanup; Alembic post-write hook; rename the colliding useForm hook; Redis retry policy + pool_recycle. Ship these in small PRs to build momentum and harden the security/PHI posture immediately.
- Phase 1 — Enforce the non-negotiables (highest stakes): org-scoping backstop (with_loader_criteria + do_orm_execute); SecretStr credential migration; type-aware ESLint + eslint-config-next + react-hooks@7 flat preset at 'warn'. These directly convert org-scoping, secret-handling, and the zero-tolerance rules from convention into enforced invariants, and the lint preset is the gate that makes Phase 2's compiler rollout safe.
- Phase 2 — Performance & DX foundations: enable React Compiler (now that lint rules surface bailouts); make the 16 sync-db async handlers non-blocking; delete get_db_for_stream; roll out lazy=raise_on_sql/raiseload incrementally; finish the Annotated/type-alias dependency cleanup across routers; add TanStack global onError + queryOptions() factories + devtools + explicit gcTime. This is where re-render cost, event-loop blocking, and N+1s get structurally addressed.
- Phase 3 — The two big structural shifts (parallelizable across frontend/backend owners): Frontend — server prefetch + HydrationBoundary + useSuspenseQuery starting with detail pages, then optimistic updates on top mutations. Backend — TaskGroup supervision + parallel job batch + LISTEN/NOTIFY worker wake. These are high-effort but high-impact; sequence them after Phases 1-2 so they build on enforced invariants and shared query factories.
- Phase 4 — Unification & consolidation: RHF+Zod validation unification (buildFieldSchema, intake + surrogate editor, z.toJSONSchema CI diff); observability consolidation (commit to OTel-in-prod OR Sentry+GCP, retire the third stack and the per-request Postgres metrics write); MultiFernet key rotation. Larger architectural cleanups that benefit from a stable, hardened base.
- Phase 5 — Forward-looking polish (optional, lower urgency): Python 3.13 runtime bump (then PEP 695 generics/Self); Pydantic nested settings + discriminated-union form fields; SQLAlchemy COPY bulk paths and select() migration of remaining heavy services; finishing the Base UI consolidation (sonner->Base UI Toast, cmdk->Base UI Combobox to drop @radix-ui entirely); Tailwind v4.1 niceties (wrap-anywhere, user-valid/invalid, gradient tokens). Do these as capacity allows; none block the core hardening.

## Quick Wins

- [Next] Set typedRoutes: true and experimental.optimizePackageImports in next.config.js — type artifact already generated; near-zero risk.
- [FastAPI] Register global exception handlers for RequestValidationError + StarletteHTTPException to normalize 422/4xx bodies to the canonical {detail, error_code, request_id} envelope the frontend already keys off.
- [Tailwind] Fix the hsl()-on-oklch placeholder bug in styles/tiptap.css (one-line: hsl(var(--muted-foreground)) -> var(--muted-foreground)).
- [Tailwind] Remove three orphaned deps (tailwindcss-animate, autoprefixer, vaul) — zero imports each; vaul removal also prunes the residual @radix-ui transitive subtree.
- [Tailwind] Fix dead Radix-era data-[state=*] selectors in tooltip/toggle-group/table (Base UI emits data-open/data-pressed/data-selected) — restores the silently-broken selected-row highlight and toggle 'on' state.
- [Sentry] Add release=settings.VERSION + a before_send PII scrubber (reuse existing PHI-safe key allowlist).
- [Observability] Add logging.dictConfig JSON formatter so structured logs work off-GCP (local/CI), and read trace IDs from the active OTel span instead of re-parsing headers.
- [Pydantic] Replace hand-rolled JsonValue=object with pydantic.JsonValue; standardize the 39 plain-dict model_config literals on ConfigDict; type cross-field validators as ValidationInfo.
- [Pydantic] Use cached module-level TypeAdapter(list[Model]) for the repeated [Model(**i).model_dump() for i in data] loops in analytics.py (9 endpoints) and similar.
- [Python] Add apps/api/.python-version; add a uv lock --locked CI check; bump tsconfig target ES2017 -> ES2022.
- [Python] Route the three asyncio.run() calls in platform_service.py through the existing run_async() bridge; run ruff pyupgrade (UP006/UP007/UP045) to clear 118 typing.Optional + uppercase Dict/List uses.
- [Alembic] Enable the ruff 'module' post-write hook and modernize script.py.mako typing (collections.abc.Sequence, str | ... | None) so new migrations stop reintroducing legacy typing.
- [TanStack] Add @tanstack/react-query-devtools (dev-only) and set explicit gcTime + mutations.retry:false in the prod QueryClient.
- [RHF/Zod] Rename the TanStack useForm hook (use-forms.ts) to useFormQuery to remove the react-hook-form name collision before RHF adoption broadens.
- [Redis] Pass an explicit Retry(ExponentialBackoff(), retries=N) + retry_on_error to all three pools instead of the coarse retry_on_timeout=True.
- [SQLAlchemy] Set DB_POOL_RECYCLE to ~1800s and pool_use_lifo=True for connections behind cloud LBs/PgBouncer.

## Major Initiatives

- Frontend server-data architecture (Next 16 + TanStack v5 + React 19): move from SPA-on-App-Router to genuine server prefetch + HydrationBoundary + useSuspenseQuery, starting with detail/match pages that already fetch server-side (eliminating the double round-trip), then list pages and the dashboard's 6-query fan-out (useQueries combine). Add route error.tsx with QueryErrorResetBoundary. This is the single largest architectural shift and unlocks faster first paint and removal of per-component isLoading branches. Sequence AFTER queryOptions() factories land.
- Backend async correctness pass: stop blocking the event loop. Convert/threadpool the 16 sync-db async handlers, delete get_db_for_stream (0.118 fix), supervise the worker's fire-and-forget create_task + per-batch fan-out with asyncio.TaskGroup, parallelize the sequential job batch with bounded concurrency + per-job sessions, and replace fixed 10s worker polling with Postgres LISTEN/NOTIFY for sub-second job latency.
- Org-scoping + N+1 hardening: ship the with_loader_criteria backstop, then roll out lazy=raise_on_sql / raiseload per-relationship and WriteOnlyMapped for unbounded collections (Organization.surrogates, status_history). Together these convert the project's two zero-tolerance rules (scoping, perf) from convention into enforced invariants.
- Validation unification (RHF + Zod 4): build lib/forms/schema.ts (buildFieldSchema/buildPageSchema), migrate the public intake form and the surrogate application editor onto it with useFieldArray and inline errors, model the field-type union as a Zod discriminatedUnion, and use z.toJSONSchema() diffed in CI against the Pydantic model to kill frontend/backend validation drift. Collapses three hand-maintained copies of the contract into one.
- Observability consolidation: choose ONE error/telemetry strategy. Either make OTel actually run in prod (wire OTEL_* into Cloud Run, add MeterProvider + LoggingHandler, retire the per-request Postgres metrics write and the parallel GCP path) or commit to Sentry+GCP and delete the half-disabled OTel code. End the three-overlapping-stacks state.
- Backend ergonomics modernization: complete the Annotated/type-alias dependency cleanup across 74 routers, adopt Pydantic query-param models on heavy list endpoints, lean on FastAPI 0.118 per-request dependency caching to retire the request.state.user_session memo, and migrate the heaviest services from legacy db.query() to the 2.0 select()/scalars() idiom (which is also what with_loader_criteria attaches to cleanly).
- Python runtime bump to 3.13 across pyproject/ruff/mypy/Docker/CI: unlocks faster cold-starts (relevant for Cloud Run scale-to-zero), far better tracebacks in Cloud Logging, optional JIT/free-threading, and gates PEP 695 generics. The code already ships 3.14 forward-compat shims, so intent exists — execute the floor bump deliberately as one change.

---

## Full Per-Area Findings

Each recommendation: **C**=current, **P**=proposed, **Doc**=official source, **Where**=files, with impact/effort/risk/breaking.

### Next 16

#### 1. Enable the React Compiler for automatic memoization across the client-heavy UI  
`[performance]` · impact=high · effort=low · risk=medium · breaking=no

- **Current:** reactCompiler is not set in apps/web/next.config.js. The app is overwhelmingly client-rendered (278 of 528 files carry use client; 188 of 205 components are client), so re-render cost is paid manually via useMemo/useCallback if at all.
- **Proposed:** Install babel-plugin-react-compiler and add reactCompiler true to next.config.js. React Compiler 1.0 is stable in Next 16 and auto-memoizes components/hooks with zero code changes.
- **Doc:** .next-docs/01-app/02-guides/upgrading/version-16.mdx (React Compiler Support)
- **Where:** apps/web/next.config.js, apps/web/package.json

#### 2. Configure optimizePackageImports for heavy client libs  
`[performance]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** next.config.js has no optimizePackageImports. Ships large barrel-export libs: fullcalendar, tiptap, react-simple-maps.
- **Proposed:** Add experimental.optimizePackageImports for the fullcalendar packages, tiptap react and starter-kit, react-simple-maps, base-ui react.
- **Doc:** .next-docs/01-app/03-api-reference/05-config/01-next-config-js/optimizePackageImports.mdx
- **Where:** apps/web/next.config.js

#### 3. Cache Components PPR on public book/intake routes  
`[architecture]` · impact=high · effort=high · risk=medium · breaking=yes

- **Current:** app/book/[slug] and app/intake/[slug] render a thin server shell then a full client component fetching via TanStack Query; nothing prerenders so first paint is blank. (app)/layout.tsx is force-dynamic.
- **Proposed:** Enable cacheComponents true and prerender the static public-route chrome into a shell with slug content under Suspense or use cache; then remove the now-redundant force-dynamic. Pilot on public routes first.
- **Doc:** .next-docs/01-app/01-getting-started/06-cache-components.mdx; cacheComponents.mdx
- **Where:** apps/web/next.config.js, apps/web/app/book/[slug]/page.tsx, apps/web/app/intake/[slug]/page.tsx, apps/web/app/(app)/layout.tsx

### React 19 (Actions / hooks / compiler) adoption in apps/web

This codebase is already on React 19.2.4 + Next.js 16.2.6 and has adopted the low-risk, no-brainer React 19 idioms well: forwardRef is fully removed (ref-as-prop everywhere), use() is used to read Context inside custom hooks and to unwrap Next 16 async params, and useTransition drives the surrogates filter UI. The unrealized value is concentrated in three buckets. (1) React Compiler is not enabled despite the project being a near-ideal candidate (all function components, eslint-plugin-react-hooks 7.0.1 present, no babel config to conflict) — Next.js 16 exposes it as a simple top-level reactCompiler flag that would let the team retire most of the pervasive manual useMemo/useCallback (including the heavy memoization in the 6- and 5-context provider trees) and close the "performance issues" zero-tolerance gap structurally. (2) The 41 useMutation sites have zero optimistic UI (no onMutate, no useOptimistic) — quick interactions like notification mark-read and surrogate stage changes wait for a round-trip. (3) Several genuinely free cleanups: the legacy <Context.Provider> syntax (the deeply nested provider trees are the worst offenders), the hand-rolled fetch/loading/error lifecycle in auth-context that duplicates what TanStack Query already does everywhere else, and useDeferredValue to replace the manual 300ms setTimeout debounce in the surrogates search. The form-Action hooks (useActionState/useFormStatus/<form action>) are a poorer fit here because the app deliberately routes all mutations through TanStack Query rather than React/Server Actions, so I rank those lower and scope them narrowly. All recommendations respect org-scoping, thin routers, cookie-JWT+CSRF (these are frontend-only ergonomics changes), and the no-auto-send-AI rule.

#### 1. Enable the React Compiler via Next.js 16's top-level reactCompiler flag to retire manual memoization  
`[performance]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** React Compiler is not enabled: next.config.js (apps/web/next.config.js) has no reactCompiler option, babel-plugin-react-compiler is not installed, and there is no babel config. Memoization is entirely manual — useMemo/useCallback are used throughout, most heavily in the context-value memoization of the 6-context tree (components/surrogates/detail/SurrogateDetailLayout/context.tsx, e.g. the large useMemo deps array ending at line 745-753) and the 5-context tree (components/surrogates/profile/ProfileCard/context.tsx), and in the ~12 useCallback filter handlers in app/(app)/surrogates/page.client.tsx:436-756.
- **Proposed:** Install babel-plugin-react-compiler as a dev dependency and add `reactCompiler: true` (top-level, NOT under experimental) to apps/web/next.config.js. Next.js 16 ships an SWC optimization that only runs the compiler on files with JSX/Hooks, keeping builds fast. The compiler auto-memoizes components and hooks, letting the team progressively delete hand-written useMemo/useCallback (especially the brittle, easy-to-desync dependency arrays in the surrogate context providers and filter handlers). The project already satisfies the prerequisites: all function components, eslint-plugin-react-hooks 7.0.1 (which surfaces Rules-of-Hooks violations the compiler relies on), and no conflicting babel config. Roll out by first running `pnpm tsc --noEmit` and the existing test suite, then watching for the compiler's bailout diagnostics; use compilationMode:'annotation' + 'use memo' for a gradual opt-in if a global flip is too risky. This directly addresses the project's zero-tolerance 'Performance issues' rule at an architectural level.
- **Doc:** Next.js 16 docs: https://nextjs.org/docs/app/api-reference/config/next-config-js/reactCompiler (local copy .next-docs/01-app/03-api-reference/05-config/01-next-config-js/reactCompiler.mdx) and https://react.dev/learn/react-compiler
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/next.config.js, /Users/chason/GenAI-assited-CRM-Tool/apps/web/package.json, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates/detail/SurrogateDetailLayout/context.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates/profile/ProfileCard/context.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/surrogates/page.client.tsx

#### 2. Adopt useOptimistic (or TanStack onMutate) for instant-feedback mutations like notification read and surrogate stage changes  
`[feature-adoption]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** There is zero optimistic UI: 0 useOptimistic calls and 0 onMutate handlers across the 41 useMutation sites; the 9 setQueryData calls are post-success cache writes, not optimistic. For example useMarkRead/useMarkAllRead in lib/hooks/use-notifications.ts:55-77 only invalidate on onSuccess, so the unread badge and row state visibly wait for the server round-trip before updating. Surrogate stage/status changes flow through the SurrogateDetailLayout actions (mutations whose isPending is tracked at context.tsx:746-752) with the same lag.
- **Proposed:** Add optimistic updates to the highest-frequency, low-risk interactions. For client-state-derived UI, React 19's useOptimistic gives an immediate optimistic value that auto-reverts on failure (ideal for the notification read toggle). For TanStack-managed server state, the idiomatic equivalent is a useMutation onMutate that snapshots + writes the cache and onError that rolls back — pairing well with the existing setQueryData pattern. Prioritize: (1) notification mark-read / mark-all-read (instant badge decrement), (2) surrogate stage/status change in the detail layout (instant pill update). Keep destructive or AI-related actions non-optimistic to honor the human-review rule.
- **Doc:** React 19: https://react.dev/reference/react/useOptimistic ; TanStack Query optimistic updates: https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-notifications.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates/detail/SurrogateDetailLayout/context.tsx

#### 3. Replace legacy <Context.Provider> with React 19's <Context> provider syntax, starting with the deeply nested provider trees  
`[cleanup]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** Every provider still uses the legacy <Context.Provider> JSX even though use() is already adopted for consuming. The worst offenders are the 6-level nested tree at components/surrogates/detail/SurrogateDetailLayout/context.tsx:756-768 and the 5-level tree in components/surrogates/profile/ProfileCard/context.tsx:484-492, plus lib/auth-context.tsx:83, app/(app)/dashboard/context/dashboard-filters.tsx, lib/context/ai-context.tsx, and the InterviewTab/InterviewComments contexts.
- **Proposed:** In React 19 a Context object can be rendered directly as the provider: <MyContext value={...}> instead of <MyContext.Provider value={...}>. This is a pure syntactic simplification (no runtime/behavior change) that removes the .Provider noise and makes the deeply nested surrogate provider stacks more readable. Apply across all provider files; it pairs naturally with already having migrated consumers to use().
- **Doc:** React 19 release notes: https://react.dev/blog/2024/12/05/react-19#context-as-a-provider ; https://react.dev/reference/react/createContext#provider
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates/detail/SurrogateDetailLayout/context.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates/profile/ProfileCard/context.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/auth-context.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/dashboard/context/dashboard-filters.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/context/ai-context.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates/interviews/InterviewTab/context.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates/interviews/InterviewComments/context.tsx

#### 4. Migrate the hand-rolled auth fetch lifecycle in auth-context.tsx to TanStack Query  
`[architecture]` · impact=medium · effort=medium · risk=medium · breaking=no

- **Current:** lib/auth-context.tsx:37-87 hand-rolls a data lifecycle: useState for user/isLoading/error, a manual fetchUser async function with try/catch/finally, manual 401-vs-error discrimination, and a useEffect that calls it on mount with route-based gating. This is the exact loading/error/refetch surface TanStack Query already provides everywhere else in the app (useQuery in ~52 files), and it is the single most-consumed context (useAuth) in the codebase.
- **Proposed:** Replace the manual state machine with a useQuery wrapping api.get<User>('/auth/me') (queryKey ['auth','me'], treat 401 as a null/not-logged-in result rather than an error, keep the ops/mfa route gating via the query's `enabled` option). Expose { user, isLoading, error, refetch } from the query so the AuthContext public shape and useRequireAuth stay unchanged. Benefits: dedup across components, automatic caching/refetch-on-focus, consistency with the rest of the app, and removal of a bespoke effect. This also makes session refresh trivial via queryClient.invalidateQueries(['auth','me']) after login/MFA instead of the current full-page navigations.
- **Doc:** TanStack Query queries guide: https://tanstack.com/query/latest/docs/framework/react/guides/queries ; React docs 'You Might Not Need an Effect': https://react.dev/learn/you-might-not-need-an-effect#fetching-data
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/auth-context.tsx

#### 5. Use useDeferredValue for the surrogates search to replace the manual setTimeout debounce  
`[dx]` · impact=medium · effort=medium · risk=medium · breaking=no

- **Current:** app/(app)/surrogates/page.client.tsx:413 keeps a separate debouncedSearch state, and lines 770-774 implement a manual 300ms setTimeout debounce effect (plus a separate sync effect at 796-820). This manual debounce coexists with the existing useTransition (line 432) and feeds ~12 updateUrlParams callsites, making the search/filter state flow hard to follow.
- **Proposed:** For the typeahead rendering path, React 19's useDeferredValue (which supports an initialValue) lets the input stay responsive while the expensive filtered list/URL recompute uses the deferred value, removing the need for the hand-managed setTimeout debounce + debouncedSearch mirror state. Note: keep a small debounce ONLY for the network query key if you want to limit backend requests (useDeferredValue defers rendering, it does not rate-limit fetches), but the local UI debounce machinery can be simplified and the circular-update effects collapsed. This reduces the effect surface in the most complex client file in the app.
- **Doc:** React 19: https://react.dev/reference/react/useDeferredValue (incl. initialValue, added in React 19)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/surrogates/page.client.tsx

#### 6. Use useFormStatus to remove pending-state prop drilling in react-hook-form / manual submit flows  
`[dx]` · impact=low · effort=medium · risk=low · breaking=no

- **Current:** Submit buttons read pending state via props/manual state: 32 files manage isSubmitting/isSaving/setSubmitting by hand alongside onSubmit, and react-hook-form's handleSubmit is used in ~22 files. Submit/disabled-while-saving state is threaded down to button components manually. 0 uses of useFormStatus.
- **Proposed:** For native <form> submissions, useFormStatus lets a nested submit button read the parent form's pending state without prop drilling, so a shared <SubmitButton> component can auto-disable + show a spinner. This is a targeted ergonomics win for the manual onSubmit forms (e.g. settings forms) that submit through a real <form>. Note the constraint: useFormStatus only reflects status when the form is driven by a React form Action, so the biggest payoff comes if a given form also moves to an action function. Scope this to a few high-traffic forms rather than a blanket migration, since the app intentionally centralizes server work in TanStack Query mutations.
- **Doc:** React 19: https://react.dev/reference/react-dom/hooks/useFormStatus
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/settings/page.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/ui

#### 7. Add react-dom resource hints (preconnect / prefetchDNS) for the API and storage origins  
`[performance]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** 0 uses of react-dom's preload/preinit/prefetchDNS/preconnect. The only resource-hint-adjacent config is the static HSTS preload directive in next.config.js (unrelated). The SPA-style client app makes its first /auth/me and TanStack Query calls to the API origin only after hydration, with no connection warming.
- **Proposed:** Call preconnect()/prefetchDNS() from react-dom against the backend API origin (and any S3/CDN origin used for avatars/attachments) early in the app shell so the TLS/DNS handshake overlaps with hydration, shaving latency off the first authenticated request. For App Router, these can be invoked in the root layout's client boundary or a small client component mounted in app/layout.tsx. Keep it limited to known first-party origins to avoid leaking destinations.
- **Doc:** React 19 resource preloading APIs: https://react.dev/reference/react-dom/preconnect and https://react.dev/reference/react-dom/prefetchDNS
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/layout.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/auth-context.tsx

### TanStack Query 5 (5.90.20) + data layer modernization for apps/web

The app is on a current TanStack Query v5 (5.90.20 + React 19.2.4) but is using roughly the v4-era subset of the API: a single client-side QueryClient, hand-rolled key factories, invalidate-then-refetch everywhere, and Server Components that render a skeleton then defer all fetching to the client on mount. The biggest unrealized capabilities of this version are (1) the App-Router server-prefetch + HydrationBoundary/useSuspenseQuery SSR flow — currently zero usage despite detail pages ALREADY fetching the resource server-side (in getServerRouteResourceStatus) just to throw the body away and refetch on the client; (2) the queryOptions()/infiniteQueryOptions() typed factory that would unify the ~40 key objects with their queryFn/options into one shareable source of truth for hook + prefetch + setQueryData; (3) optimistic updates (onMutate / variables approach) which are completely absent across ~261 mutations; and (4) operational ergonomics that are free wins — devtools, a global QueryCache/MutationCache onError to collapse error toasts repeated across ~299 call sites, and explicit gcTime/global mutation defaults that are currently library defaults in prod. None of these require a version bump; they are features already shipped in 5.90.20. All recommendations respect org-scoping (server prefetch forwards cookies + x-org-* exactly as the existing helper does), thin routers (frontend-only changes), and production quality.

#### 1. Adopt the App Router server-prefetch + HydrationBoundary + useSuspenseQuery SSR flow (start with detail pages that already fetch server-side)  
`[architecture]` · impact=high · effort=high · risk=medium · breaking=no

- **Current:** Every page.tsx Server Component renders a skeleton inside <Suspense> and defers ALL data fetching to a 'use client' component that fires queries on mount (e.g. app/(app)/dashboard/page.tsx -> page.client.tsx:93-98 fires 6 queries; app/(app)/surrogates/page.tsx, app/(app)/intended-parents/matches/[id]/page.tsx). Zero usage of HydrationBoundary/dehydrate/prefetchQuery/ensureQueryData anywhere. Critically, the detail/match pages ALREADY do a server-side fetch of the exact resource in getServerRouteResourceStatus (lib/server-route-resource.ts:40 fetches /matches/{id} etc. forwarding cookies + x-org-id/slug/name) only to check 404/401-403 and discard the body — then page.client.tsx refetches the same resource on mount, producing a guaranteed double round-trip + post-mount waterfall.
- **Proposed:** Introduce a request-scoped server QueryClient via React cache() (get-query-client.ts), then in the Server Component await queryClient.prefetchQuery(...) using the SAME query key as the client hook and render <HydrationBoundary state={dehydrate(qc)}>. Replace the corresponding client useQuery with useSuspenseQuery so the page renders with data already populated (no isLoading branch). Begin with the pages that already fetch server-side: fold the existence check INTO the prefetch (a successful prefetch implies it exists; a 404 -> notFound(), 401/403 -> pass through) so the server fetch is reused instead of thrown away — eliminating the double fetch. Forward cookies + x-org-* headers in the prefetch queryFn exactly as buildServerApiHeaders/server-route-resource.ts does today to preserve org scoping.
- **Doc:** https://tanstack.com/query/v5/docs/framework/react/guides/advanced-ssr (Advanced SSR — Next.js App Router prefetch + HydrationBoundary; cache() per-request client) + local .next-docs/01-app/01-getting-started/07-fetching-data.mdx
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/query-provider.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/server-route-resource.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/intended-parents/matches/[id]/page.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/surrogates/page.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/surrogates/[id]/page.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/dashboard/page.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/dashboard/page.client.tsx

#### 2. Replace the ~40 hand-rolled key objects with queryOptions()/infiniteQueryOptions() typed factories  
`[feature-adoption]` · impact=high · effort=medium · risk=low · breaking=no

- **Current:** ~40 '<entity>Keys = { all, lists(), list(params), detail(id), ... } as const' objects live separately from their queryFn/options, and each useQuery re-specifies queryKey + queryFn + staleTime inline (e.g. lib/hooks/use-surrogates.ts:10-27 keys vs :69-132 hooks; lib/hooks/use-tasks.ts:11-17). The same query's config is duplicated between the hook, the (planned) prefetch, and the 26 setQueryData call sites — there is no single typed source of truth, and queryOptions()/infiniteQueryOptions() are unused anywhere.
- **Proposed:** Co-locate each query as a queryOptions(...) factory (e.g. surrogateDetailOptions(id) returning { queryKey, queryFn, staleTime }). useQuery/useSuspenseQuery/prefetchQuery/useQueries all accept the factory directly, and setQueryData(surrogateDetailOptions(id).queryKey, data) reuses the same key — eliminating drift between hook, prefetch, and cache write. Convert the one infinite query (lib/hooks/use-meta-oauth.ts:77-90) to infiniteQueryOptions for the same benefit. The existing key objects can be kept for invalidation prefixes (lists()/all) since those remain useful for broad invalidation.
- **Doc:** https://tanstack.com/query/v5/docs/framework/react/guides/query-options and https://tanstack.com/query/v5/docs/framework/react/reference/infiniteQueryOptions
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-surrogates.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-tasks.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-meta-oauth.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/

#### 3. Add a global QueryCache/MutationCache onError to centralize error toasts and 401/403 handling  
`[dx]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** QueryProvider (lib/query-provider.tsx:19-27) sets only queries.staleTime + queries.retry; there is no QueryCache or MutationCache with a global onError, and no global mutation defaults. Error handling is hand-repeated: ~299 toast/.error calls across components and 44 components with toast.error, plus only 10 per-hook onError handlers — so most mutation errors are surfaced ad hoc at each call site (e.g. app/(app)/surrogates/page.client.tsx:134,137,1181).
- **Proposed:** Construct the QueryClient with new QueryClient({ queryCache: new QueryCache({ onError }), mutationCache: new MutationCache({ onError }), defaultOptions: { mutations: { onError, retry } } }). Default onError shows a toast.error and, for 401/403 (reusing the shouldRetryQuery status check), triggers the existing auth/redirect path once. Per-mutation handlers opt out via meta (e.g. meta: { suppressGlobalError: true }) where a call site wants custom messaging. This removes boilerplate from dozens of components while keeping the 'never auto-send / production-quality error states' rule — errors still surface, just from one place.
- **Doc:** https://tanstack.com/query/v5/docs/framework/react/reference/QueryCache and https://tanstack.com/query/v5/docs/framework/react/guides/mutations#mutation-side-effects (global onError via cache)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/query-provider.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/

#### 4. Add optimistic updates (onMutate rollback or variables approach) for high-frequency mutations  
`[feature-adoption]` · impact=high · effort=high · risk=medium · breaking=no

- **Current:** Zero onMutate handlers across ~261 useMutation calls; every mutation is invalidate-then-refetch or setQueryData(serverResponse) AFTER the round-trip (e.g. useUpdateTask use-tasks.ts:90-102, useCompleteTask :107-120, useChangeSurrogateStatus use-surrogates.ts:205-225). So toggling a task complete or changing a status shows a spinner/latency before the UI reflects the change, and there is no rollback path.
- **Proposed:** For the snappiest interactions (task complete/uncomplete, status change, assignment), add onMutate that cancelQueries the affected key, snapshots previous data, optimistically setQueryData (list + detail), and onError rolls back from the snapshot with onSettled invalidate to reconcile. For single-surface, transient cases (e.g. inline create in a list), the simpler v5 variables approach (render pending row from mutation.variables while isPending) needs no cache surgery. This is purely a UX upgrade that fits the 'polished, not MVP' standard.
- **Doc:** https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates (cache via onMutate/onError/onSettled, and the variables-based UI approach)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-tasks.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-surrogates.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/

#### 5. Install @tanstack/react-query-devtools for development cache inspection  
`[dx]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** @tanstack/react-query-devtools is absent from package.json and pnpm-lock.yaml. With ~180 useQuery + ~261 useMutation + ~413 invalidateQueries calls and WebSocket-driven invalidation (use-dashboard-socket.ts:95), there is no in-app way to see which keys are cached/stale/refetching, making the heavy invalidation web hard to debug.
- **Proposed:** pnpm add -D @tanstack/react-query-devtools and mount <ReactQueryDevtools initialIsOpen={false} /> inside QueryProvider. The package is tree-shaken out of production builds automatically (only included when NODE_ENV === 'development'), so there is no prod-bundle cost. Lets developers verify the new prefetch/hydration keys match client keys and inspect the socket-driven invalidations.
- **Doc:** https://tanstack.com/query/v5/docs/framework/react/devtools (separate package, dev-only by default)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/package.json, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/query-provider.tsx

#### 6. Coordinate the dashboard's 6 independent queries with useQueries({ combine })  
`[performance]` · impact=medium · effort=medium · risk=low · breaking=no

- **Current:** The dashboard fires 6 separate hooks on mount (page.client.tsx:93-98: useSurrogateStats/useSurrogatesTrend/useSurrogatesByStatus/useAttention/useTasks/useUpcoming) and then manually reduces across them in useMemo — e.g. lastUpdated computes Math.max over 6 .dataUpdatedAt fields (:113-130) and kpiTotalForCheck cross-reads two queries (:105-110). useQueries is unused.
- **Proposed:** Use useQueries({ queries: [...queryOptions factories...], combine: (results) => ({ ...derived totals, lastUpdated, isPending }) }) to compute aggregate/derived state (lastUpdated, statusTotal, kpiTotalForCheck, combined isPending/isError) in one place with a single memoized combine, instead of six hook results plus several hand-written useMemos. Pairs naturally with the queryOptions refactor and the suspense/prefetch work.
- **Doc:** https://tanstack.com/query/v5/docs/framework/react/reference/useQueries (combine option)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/dashboard/page.client.tsx

#### 7. Migrate paginated lists from discrete page-param useQuery to useInfiniteQuery  
`[feature-adoption]` · impact=medium · effort=high · risk=low · breaking=no

- **Current:** useInfiniteQuery is used in exactly one file (use-meta-oauth.ts:77). Paginated surfaces bake page/perPage into the queryKey with discrete useQuery calls and no getNextPageParam — e.g. useSurrogateActivity(surrogateId, page, perPage) (use-surrogates.ts:422-428) keys each page separately, and unassigned-queue/tasks lists follow the same page param pattern. Each page change is a fresh query with its own cache entry and a loading flash.
- **Proposed:** Convert append-style feeds (surrogate activity log, unassigned queue, activity feeds) to useInfiniteQuery with initialPageParam + getNextPageParam, giving 'load more'/infinite scroll with accumulated pages and maxPages trimming, plus placeholderData: keepPreviousData behavior for smooth paging. Keep table-style lists that need jump-to-page on discrete useQuery. Express via infiniteQueryOptions for reuse.
- **Doc:** https://tanstack.com/query/v5/docs/framework/react/guides/infinite-queries
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-surrogates.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-tasks.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/

#### 8. Drive list-page loading via useSuspenseQuery + the existing page.tsx Suspense boundaries (and add error.tsx + throwOnError)  
`[feature-adoption]` · impact=medium · effort=high · risk=medium · breaking=no

- **Current:** Pages already render <Suspense fallback={Skeleton}> in page.tsx (e.g. surrogates/page.tsx, dashboard/page.tsx, matches/[id]/page.tsx) but the client components still branch on isLoading/isPending internally rather than suspending — so the Suspense boundary mostly wraps a component that resolves instantly and then shows its own internal loading state. No throwOnError / QueryErrorResetBoundary / error.tsx integration, so query errors are surfaced via per-hook isError.
- **Proposed:** Switch the primary data hook on these pages to useSuspenseQuery (data is non-undefined; the page.tsx Suspense fallback becomes the single loading UI, removing per-component isLoading branches) and add a route error.tsx that uses useQueryErrorResetBoundary()/reset so Retry re-runs the failed query. Combined with prefetch (rec #1), the suspense boundary resolves immediately from hydrated cache. Honor the retry policy: keep shouldRetryQuery and rely on throwOnError defaults for suspense queries.
- **Doc:** https://tanstack.com/query/v5/docs/framework/react/guides/suspense and https://tanstack.com/query/v5/docs/framework/react/reference/useQueryErrorResetBoundary + local .next-docs/01-app/03-api-reference/03-file-conventions/error.mdx
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/surrogates/page.client.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/dashboard/page.client.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/intended-parents/matches/[id]/page.client.tsx

#### 9. Set explicit global gcTime and mutation defaults in the production QueryClient  
`[cleanup]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** lib/query-provider.tsx only sets queries.staleTime (60s) and queries.retry. gcTime, networkMode, and any mutations defaults are left at library defaults in production — gcTime is only ever set in the test client (tests/utils/integration-wrapper.tsx). With 11 polling refetchInterval queries and WebSocket invalidation, cache lifetime and mutation retry are implicit rather than intentional.
- **Proposed:** Set explicit defaults in the app QueryClient: queries.gcTime (e.g. 5min, longer than the 60s staleTime so backgrounded data isn't dropped prematurely), mutations.retry: false (mutations are usually non-idempotent here — explicit beats implicit), and reuse shouldRetryQuery for queries. This makes cache behavior intentional and documented, and is the natural home for the dehydrate.shouldDehydrateQuery config needed by the SSR work (rec #1).
- **Doc:** https://tanstack.com/query/v5/docs/reference/QueryClient (defaultOptions: gcTime, mutations.retry) and https://tanstack.com/query/v5/docs/framework/react/guides/important-defaults
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/query-provider.tsx

#### 10. Expose cross-component mutation state via mutationKey + useMutationState/useIsMutating  
`[feature-adoption]` · impact=low · effort=medium · risk=low · breaking=no

- **Current:** No mutationKey on any useMutation, and useMutationState/useIsMutating are unused. Components that need to know whether a related mutation is in-flight (e.g. disable a global 'Save'/bulk bar while a bulk assign/archive runs, or show a busy indicator in a parent while a child mutates) cannot read that state without prop-drilling the mutation object.
- **Proposed:** Assign stable mutationKeys to the bulk/long-running mutations (useBulkAssign/useBulkArchive/useBulkChangeStage in use-surrogates.ts:314-359, useBulkCompleteTasks in use-tasks.ts:158) and read pending/variables in toolbars or headers via useMutationState({ filters: { mutationKey } }) / useIsMutating({ mutationKey }). Enables a single source-of-truth busy state and optimistic 'pending row' rendering without lifting mutation objects through the tree.
- **Doc:** https://tanstack.com/query/v5/docs/framework/react/reference/useMutationState and https://tanstack.com/query/v5/docs/framework/react/reference/useIsMutating
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-surrogates.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-tasks.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/surrogates/page.client.tsx

### Tailwind CSS 4 + shadcn/ui + Base UI modernization (apps/web)

The frontend is already on a clean, modern foundation: CSS-first Tailwind v4 (no tailwind.config, single @theme inline block in globals.css), a complete Base UI migration of all 21 ui/ primitives off Radix, the useRender/render-prop idiom replacing asChild, oklch tokens, container queries, and tw-animate-css for motion. The remaining opportunities are not version bumps but (1) finishing the Base UI migration story — dead Radix-era data-[state=*] selectors left over in three primitives, plus three orphaned dependencies (tailwindcss-animate, autoprefixer, vaul) that no longer do anything, (2) adopting genuinely useful Tailwind v4.1 utilities this CRM would benefit from (wrap-anywhere for long emails/tokens, the gradient color-stop API to retire a hardcoded arbitrary gradient, @utility to formalize hand-rolled CSS), and (3) a real correctness bug (tiptap.css uses hsl() against oklch tokens, producing an invalid placeholder color). Highest leverage is consolidating the brand gradient into theme tokens and fixing the dead selectors/bug, both low-risk. Optional larger plays: replacing sonner with Base UI Toast and cmdk/vaul with Base UI Combobox/Context Menu to drop the residual @radix-ui transitive bundle entirely.

#### 1. Remove dead Radix-era data-[state=*] selectors left behind after the Base UI migration  
`[cleanup]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** Three migrated Base UI primitives still carry Radix-style data-[state=...] selectors that Base UI never emits, so the styling is silently dead: tooltip.tsx:60 (`data-[state=delayed-open]:animate-in/fade-in-0/zoom-in-95`), toggle-group.tsx:75 (`data-[state=on]:bg-muted` plus `group-data-horizontal`/`group-data-vertical`), table.tsx:43 (`data-[state=selected]:bg-muted`). Base UI emits data-open/data-closed, data-pressed (Toggle), data-selected/data-highlighted, and data-orientation — not data-state. Verified via node_modules/@base-ui/react (Toggle exposes pressed state; ToggleGroup exposes data-orientation/data-multiple).
- **Proposed:** Replace each dead selector with the Base UI equivalent: tooltip → drop the `data-[state=delayed-open]:*` triplet (the `data-open:*` triplet already covers the open animation); toggle-group → `data-[state=on]:bg-muted` becomes `data-pressed:bg-muted`, and `group-data-horizontal`/`group-data-vertical` become `group-data-[orientation=horizontal]`/`group-data-[orientation=vertical]` (the codebase already uses the correct `group-data-[orientation=vertical]` form in tabs.tsx:27); table → `data-[state=selected]:bg-muted` becomes `data-selected:bg-muted` and the row must actually set `data-selected` when selected. This restores the intended selected-row highlight, the toggle 'on' background, and removes confusing dead classes.
- **Doc:** Base UI component docs — Toggle Group (data-orientation, data-multiple) and Toggle (pressed state) attribute tables: https://base-ui.com/react/components/toggle-group ; verified against installed @base-ui/react 1.1.0
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/ui/tooltip.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/ui/toggle-group.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/ui/table.tsx

#### 2. Promote the brand gradient into @theme color-stop tokens and use the v4 gradient API instead of an arbitrary bg-[linear-gradient(...)]  
`[dx]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** button.tsx:14 hardcodes the primary CTA gradient as `bg-[linear-gradient(135deg,var(--primary-gradient-from),var(--primary-gradient-to))]`. The `--primary-gradient-from`/`--primary-gradient-to` oklch values are defined in :root (globals.css:73-76) and .dark (137-140) but are NOT registered in the `@theme inline` block (globals.css:7-48), so no Tailwind color utility exists for them — forcing the arbitrary CSS escape hatch. 13 other call sites use the v3-era `bg-gradient-to-*` (app/ops/page.client.tsx, components/reports/MetaSpendDashboard.tsx, components/surrogates/journey/*, etc.).
- **Proposed:** Add `--color-primary-gradient-from: var(--primary-gradient-from)` and `--color-primary-gradient-to: var(--primary-gradient-to)` to the @theme inline block, then replace the arbitrary string in button.tsx with the v4 linear-gradient utilities: `bg-linear-[135deg] from-primary-gradient-from to-primary-gradient-to` (or define a single `@utility btn-brand-gradient`). Migrate the 13 `bg-gradient-to-*` sites to the v4 `bg-linear-to-*` names. This makes the brand gradient theme-aware, hover/dark-variant-able, and removes magic CSS from the most-used component.
- **Doc:** Tailwind v4 gradient utilities (bg-linear-*, color-stop from-/to-) and theme color registration: https://tailwindcss.com/docs/background-image ; @theme: https://tailwindcss.com/docs/theme
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/globals.css, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/ui/button.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/ops/page.client.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/reports/MetaSpendDashboard.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates/journey/SurrogateJourneyTab.tsx

#### 3. Fix the hsl()-on-oklch placeholder color bug in tiptap.css  
`[cleanup]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** styles/tiptap.css:3 sets the editor empty-placeholder color with `color: hsl(var(--muted-foreground))`, but every token in globals.css is defined as `oklch(...)` (e.g. --muted-foreground: oklch(0.528 0 89.876)). Wrapping an oklch string in hsl() yields an invalid color, so the TipTap placeholder falls back to the inherited/default color rather than the intended muted gray. This is a leftover from the pre-oklch (v3 hsl) theme.
- **Proposed:** Replace `hsl(var(--muted-foreground))` with `var(--muted-foreground)` (the token is already a complete color value), or better, express the placeholder via Tailwind by using `@apply text-muted-foreground/...` in a layered rule. This is a one-line correctness fix that restores the muted placeholder appearance in the rich-text editor used across the CRM.
- **Doc:** Tailwind v4 theme variables resolve to complete color values (oklch); custom CSS should reference the var directly: https://tailwindcss.com/docs/theme#referencing-other-variables
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/styles/tiptap.css

#### 4. Remove three orphaned styling dependencies: tailwindcss-animate, autoprefixer, vaul  
`[cleanup]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** package.json declares tailwindcss-animate@1.0.7 (v3-era; tw-animate-css is the one actually imported in globals.css:2 — zero imports of tailwindcss-animate anywhere), autoprefixer@10.4.24 (absent from postcss.config.mjs, which under v4 only needs @tailwindcss/postcss; Lightning CSS handles prefixing), and vaul@1.1.2 (grep shows ZERO imports — the Sheet is implemented with @base-ui/react/dialog in sheet.tsx:4, so vaul is fully dead and is the main source of residual @radix-ui transitive entries in the lockfile).
- **Proposed:** Drop all three from package.json dependencies and reinstall to prune the lockfile. Removing vaul also strips its @radix-ui transitive subtree from node_modules/bundle. None are referenced by any import, config, or CSS, so this is pure deletion with no code changes.
- **Doc:** Tailwind v4 PostCSS setup requires only @tailwindcss/postcss (no autoprefixer): https://tailwindcss.com/docs/installation/using-postcss ; tw-animate-css replaces tailwindcss-animate for v4: https://github.com/Wombosvideo/tw-animate-css
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/package.json

#### 5. Adopt Tailwind v4.1 wrap-anywhere for long unbreakable strings (emails, tokens, URLs)  
`[feature-adoption]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** 16 occurrences of v3-era `break-all`/`break-words` exist across components, and the CRM renders long unbreakable strings (lead/IP email addresses, magic-link/unsubscribe tokens, form slugs, file names) inside flex rows where `break-words` does not break the flex item's intrinsic min-width, causing overflow. v4.1's `wrap-anywhere` (overflow-wrap: anywhere) is not used anywhere (0 occurrences).
- **Proposed:** Replace `break-all`/`break-words` with `wrap-anywhere` in the flex contexts where long emails/tokens overflow (contact cards, lead lists, form/email detail panels). Unlike break-words, wrap-anywhere also collapses the flex item's min-content width so truncation/wrapping actually engages — eliminating horizontal overflow without manual `min-w-0` plumbing.
- **Doc:** Tailwind CSS v4.1 release notes — wrap-anywhere / overflow-wrap utilities: https://tailwindcss.com/blog/tailwindcss-v4-1#wrapping-with-overflow-wrap
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/forms, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/email

#### 6. Formalize hand-rolled CSS in globals.css as v4 @utility / theme keyframes  
`[dx]` · impact=low · effort=medium · risk=low · breaking=no

- **Current:** globals.css contains ~150 lines of plain CSS that bypass Tailwind's system: the .surrogates-floating-scrollbar-viewport scrollbar styling (184-229) with hardcoded rgba() literals duplicating oklch token values, and the View Transition circle-blur keyframes/::view-transition selectors (234-290). These get no variant support and can drift from the design tokens. The codebase never uses v4's `@utility` directive (only one `@custom-variant`).
- **Proposed:** Express the scrollbar treatment as an `@utility floating-scrollbar { ... }` (variant-capable, so dark mode is handled by `dark:` rather than the duplicated `.dark .surrogates-...` block) and reference theme tokens via color-mix on --muted-foreground/--border instead of the 6+ hardcoded rgba() literals. Keep the view-transition keyframes but move the magic numbers (durations/easing) behind theme custom properties. This removes color duplication and lets the scrollbar follow the theme automatically.
- **Doc:** Tailwind v4 @utility directive (variant-capable custom utilities): https://tailwindcss.com/docs/adding-custom-styles#adding-custom-utilities
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/globals.css

#### 7. Replace sonner with Base UI Toast to finish the Base UI consolidation  
`[architecture]` · impact=medium · effort=high · risk=medium · breaking=yes

- **Current:** Toast notifications are provided by sonner@2.0.7 (81 import/usage sites). The component library is otherwise 100% Base UI; node_modules/@base-ui/react/toast is present and stable in the installed 1.1.0 (Toast.Provider, Toast.Portal/Viewport/Root, useToastManager with add/promise/update). Keeping sonner means a second motion/animation system alongside Base UI's data-open/data-closed + tw-animate-css idiom already used everywhere else.
- **Proposed:** Build a thin ui/toast.tsx + ui/sonner-shim wrapper on @base-ui/react/toast styled with the existing data-open/data-closed/data-starting-style animation idiom (matching dialog/sheet/popover), expose a `toast()` helper with the same call signature to minimize churn across the 81 sites, then drop sonner. This unifies on one a11y/animation system and removes a dependency. Per project no-backward-compat policy this is an acceptable internal break; do it as one PR with the helper preserving current call sites.
- **Doc:** Base UI Toast (Provider/useToastManager/toast.add/promise): https://base-ui.com/react/components/toast
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/ui, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/layout.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/package.json

#### 8. Migrate cmdk (command palette) to Base UI Combobox/Autocomplete to drop residual @radix-ui from the bundle  
`[architecture]` · impact=medium · effort=high · risk=medium · breaking=yes

- **Current:** components/ui/command.tsx is the last component still importing a non-Base-UI primitive: `Command as CommandPrimitive from "cmdk"` (command.tsx:4). cmdk pulls @radix-ui transitively, which (together with now-removable vaul) is why ~76 @radix-ui entries remain in the lockfile despite the direct migration being complete. Installed @base-ui/react 1.1.0 ships combobox and autocomplete (verified in node_modules), which cover command-palette/filterable-list use cases natively.
- **Proposed:** Reimplement command.tsx on @base-ui/react/combobox (or autocomplete) using the same data-slot + data-highlighted/data-selected styling idiom as the other primitives. After this and the vaul removal, the @radix-ui transitive subtree can be fully eliminated, completing the single-primitive-library architecture and shrinking the client bundle. Validate keyboard nav and filtering parity (the command palette is a power-user surface — production-quality, not MVP).
- **Doc:** Base UI Combobox / Autocomplete: https://base-ui.com/react/components/combobox ; release notes (loopFocus, placeholder prop in 1.1.0): https://base-ui.com/react/overview/releases
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/ui/command.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/package.json

#### 9. Use v4.1 user-valid / user-invalid variants for form validation feedback  
`[feature-adoption]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** Forms use React Hook Form + Zod and surface errors via aria-invalid styling (e.g. button.tsx and field components key off `aria-invalid:ring-destructive/20`). There is no use of v4.1's `user-valid:`/`user-invalid:` variants (0 occurrences), which only style fields AFTER the user has interacted — avoiding the jarring all-red-on-load behavior that pure :invalid can cause.
- **Proposed:** In the shared input/field primitives (components/ui/field.tsx, input/textarea/select), layer `user-invalid:border-destructive user-invalid:ring-destructive/20` and `user-valid:border-green-500` (matching the design-system status colors) for native constraint feedback that complements the RHF/Zod error messages. Low effort, improves perceived polish on the heavily-used public intake forms.
- **Doc:** Tailwind CSS v4.1 release notes — user-valid / user-invalid variants: https://tailwindcss.com/blog/tailwindcss-v4-1#user-valid-and-user-invalid-variants
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/ui/field.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/ui/input.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/forms/PublicFormFieldRenderer.tsx

### React Hook Form 7 + Zod 4 modernization for apps/web (validation stack)

The modern validation stack (react-hook-form 7.71.1, zod 4.3.6, @hookform/resolvers 5.2.2) is installed and current, but effectively dormant: exactly one file in the entire frontend (apps/web/app/(app)/welcome/page.tsx) uses RHF+Zod, and it is written in pure Zod v3 idioms (legacy string-message args, .optional().or(z.literal("")) for empty handling). Every other form — most importantly the ~1684-line public intake form (apps/web/app/intake/[slug]/page.client.tsx) and the surrogate application editor — hand-rolls validation with raw useState, an imperative getFieldValidationError that re-implements min/max/pattern/coerce checks Zod 4 ships natively, manual addRow/removeRow that duplicates RHF's useFieldArray, and toast-only error surfacing instead of inline field state. The biggest unlocked opportunity is structural: the field-validation contract is a Pydantic v2 model on the backend (apps/api/app/schemas/forms.py:56) mirrored as a hand-kept TS interface (apps/web/lib/api/forms.ts:56), and Zod 4's z.toJSONSchema() + .meta()/registries + improved discriminatedUnion would let the data-driven field model be validated by a single compiled schema-builder instead of bespoke imperative code per form. The highest-value, lowest-risk wins are: (1) build a Zod-schema generator for the dynamic intake form to replace the imperative validator and move errors inline, (2) adopt useFieldArray for repeatable tables, (3) modernize the welcome page to Zod 4 idioms as the canonical pattern. None of these require version bumps; they exercise capabilities the project already pays for but does not use.

#### 1. Replace the imperative intake validator with a Zod 4 schema built from the field model, and surface errors inline via RHF  
`[architecture]` · impact=high · effort=high · risk=medium · breaking=no

- **Current:** The public intake form (apps/web/app/intake/[slug]/page.client.tsx) manages all state in raw useState (answers/fileUploads/currentStep, lines 545-563) and validates with a 130-line hand-rolled getFieldValidationError (lines 976-1105) plus validateStep (1113-1129). It re-implements min_length/max_length (1059-1068), anchored-regex pattern matching with try/catch (1069-1083), and number coercion via Number()/Number.isNaN (1086-1090). Errors are shown only as a single toast.error per step (line 1123) rather than inline per field.
- **Proposed:** Write a buildFieldSchema(field: FormField) helper that maps each FormField (lib/api/forms.ts:95) to a Zod 4 schema: text/textarea/email/phone -> z.string() with .min(validation.min_length)/.max(validation.max_length)/.regex(new RegExp(anchored)); email type -> z.email(); number -> z.coerce.number().min().max() (replacing the manual Number()/NaN logic); repeatable_table/table -> z.array(z.object(...)).min(min_rows).max(max_rows). Compose pages into z.object(...) and drive the multi-step form with useForm({ resolver: zodResolver(pageSchema) }) so errors render inline under each field (errors[field.key].message) instead of toast-only. Use z.coerce.number() to delete the manual NaN handling entirely.
- **Doc:** Zod 4 docs (zod.dev/v4): top-level z.email()/z.coerce; @hookform/resolvers README zodResolver for Zod 4
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/intake/[slug]/page.client.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/api/forms.ts

#### 2. Adopt RHF useFieldArray for repeatable-table rows instead of hand-rolled addRow/removeRow  
`[feature-adoption]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** Repeatable tables are managed manually: addRow (page.client.tsx:1222) and removeRow (1231) splice into the answers array via setAnswers, with row identity, min/max row gating, and per-cell state all hand-managed. The same array is then re-validated imperatively in getFieldValidationError (986-1011). No react-hook-form field-array primitive is used anywhere in the repo.
- **Proposed:** Once the intake form is on RHF (see the schema recommendation), drive each repeatable_table with useFieldArray({ name: field.key }). Use the returned fields/append/remove/move helpers for row management (replacing addRow/removeRow), letting RHF own row keys, dirty tracking, and re-render batching. Min/max row constraints become z.array(...).min(min_rows).max(max_rows) in the schema rather than imperative length checks, and per-row required-cell errors surface inline through the resolver.
- **Doc:** react-hook-form.com/docs/usefieldarray (useFieldArray: fields/append/remove/move)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/intake/[slug]/page.client.tsx

#### 3. Derive a single Zod schema-builder + JSON Schema from the field model to unify validation and form-builder metadata  
`[architecture]` · impact=high · effort=high · risk=medium · breaking=no

- **Current:** The field-validation contract is duplicated: Pydantic FormFieldValidation on the backend (apps/api/app/schemas/forms.py:56-61) is the source of truth, mirrored as a hand-kept TS interface FormFieldValidation (apps/web/lib/api/forms.ts:56-62), and then re-interpreted a third time at runtime by the imperative intake validator. Form-builder field metadata (label, help_text, validation, sensitivity) are plain TS objects threaded through lib/forms/*. There is no Zod schema and no JSON Schema bridge; grep confirms z.toJSONSchema / .meta() / registries are unused.
- **Proposed:** Centralize a buildFieldSchema (recommended above) and attach builder metadata with Zod 4 .meta()/z.registry() (label, helperText, sensitivity, FieldType). Use z.toJSONSchema() to emit a JSON Schema artifact that can be diffed in CI against the Pydantic model (which already exposes model_json_schema) — catching frontend/backend validation drift the same way scripts/gen_surrogate_contracts.py keeps types in sync today. This makes one schema the single source for runtime validation, builder UI metadata, and the client/server contract instead of three hand-maintained copies.
- **Doc:** Zod 4 docs (zod.dev/v4): z.toJSONSchema(), .meta()/z.registry()/z.globalRegistry
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/api/forms.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/forms/form-builder-document.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/forms.py, /Users/chason/GenAI-assited-CRM-Tool/scripts

#### 4. Model the field-type union as a Zod 4 discriminatedUnion instead of if (field.type === ...) branches  
`[feature-adoption]` · impact=medium · effort=medium · risk=low · breaking=no

- **Current:** FieldType (lib/api/forms.ts:34-49) is a discriminated shape with type-specific validation (text vs number vs repeatable_table vs table vs height), but it is validated with a long chain of if (field.type === ...) branches in getFieldValidationError (page.client.tsx:980-1090). No z.discriminatedUnion or z.union exists in the repo.
- **Proposed:** Define a FieldSchema as z.discriminatedUnion('type', [...]) with one z.object per FieldType variant, leveraging Zod 4's improved discriminatedUnion (supports union/nested discriminators and composes with other discriminated unions). This gives exhaustive, type-narrowed validation and editor metadata per field type, replacing the manual branch chain and producing precise per-variant error messages. It also makes the form-builder's allowed-validation-per-type rules schema-enforced rather than convention.
- **Doc:** Zod 4 docs (zod.dev/v4): discriminated unions now support union/pipe/nested discriminators
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/api/forms.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/intake/[slug]/page.client.tsx

#### 5. Modernize the welcome form to Zod 4 idioms as the canonical RHF pattern  
`[dx]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** welcome/page.tsx is the only RHF+Zod file and uses pure v3 idioms: legacy 2nd-arg string messages .min(2, 'Name must be...') (lines 27-37), and the .max(20).optional().or(z.literal('')) workaround for optional phone (lines 33-37). Submission state is tracked with a manual useState isSubmitting (line 51) plus try/catch (67-88) instead of RHF formState.isSubmitting.
- **Proposed:** Switch to the Zod 4 unified error param ({ error: '...' } or { error: (issue) => ... }) so messages are consistent and type-validation errors are customizable. Replace .optional().or(z.literal('')) with a cleaner empty-string-to-undefined transform (e.g. z.string().max(20).optional().or(z.literal('')) -> z.preprocess/transform or simply allow empty and normalize on submit). Drop the manual isSubmitting useState in favor of formState.isSubmitting from RHF. Use this file as the reference implementation other forms copy.
- **Doc:** Zod 4 docs (zod.dev/v4): unified `error` param replacing message/invalid_type_error/required_error/errorMap; react-hook-form.com/docs/useform formState.isSubmitting
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/welcome/page.tsx

#### 6. Migrate the surrogate application editor to RHF + Zod for inline validation and dirty tracking  
`[feature-adoption]` · impact=medium · effort=high · risk=medium · breaking=no

- **Current:** apps/web/components/surrogates/SurrogateApplicationTab.tsx is a pure useState editor with manual onChange handlers and no react-hook-form import. It shares the same FormSchema field model as the public intake form, so it has the same validation needs but zero schema validation, no inline errors, and no dirty/isSubmitting tracking.
- **Proposed:** Reuse the buildFieldSchema helper (recommended above) so the case-manager-facing editor and the public intake form validate identically from one source. Wrap the editor in useForm + FormProvider/useFormContext (and useFieldArray for tables) to get inline field errors, formState.isDirty for unsaved-changes prompts, and formState.isSubmitting for save buttons — matching the production-quality standard (complete error/loading states) instead of the current ad-hoc useState.
- **Doc:** react-hook-form.com/docs/useform (formState.isDirty/isSubmitting); react-hook-form.com/docs/formprovider
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/components/surrogates/SurrogateApplicationTab.tsx

#### 7. Standardize on standardSchemaResolver and a shared zod helper module to make the modern stack reusable  
`[dx]` · impact=medium · effort=medium · risk=low · breaking=no

- **Current:** Validation logic is duplicated per form (the intake validator, the surrogate editor handlers, the welcome schema) with no shared module. The single RHF file imports zodResolver directly. @hookform/resolvers 5.2.2 ships a standard-schema subpath (confirmed at node_modules/@hookform/resolvers/standard-schema) that is unused, and there is no lib/forms/validation module to house reusable schemas.
- **Proposed:** Create apps/web/lib/forms/schema.ts exporting buildFieldSchema, buildPageSchema, and shared primitives (e.g. phoneSchema = z.string().max(20), emailSchema = z.email()). Adopt standardSchemaResolver from @hookform/resolvers/standard-schema as the project-wide resolver — it is Zod-4-native via the Standard Schema interface and keeps the door open to other validators, decoupling form code from the Zod-specific zodResolver path. Every new form imports from this one module.
- **Doc:** @hookform/resolvers README: standardSchemaResolver from '@hookform/resolvers/standard-schema' (Standard Schema, Zod 4 native)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/forms, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/welcome/page.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/intake/[slug]/page.client.tsx

#### 8. Use z.treeifyError/z.prettifyError for structured multi-error reporting in the form builder and intake submit  
`[dx]` · impact=medium · effort=medium · risk=low · breaking=no

- **Current:** Errors are surfaced either per-field manually (welcome/page.tsx:131-168) or as a single toast.error per step in the intake form (page.client.tsx:1123) and as toast-based gating in the builder hooks (lib/forms/use-automation-form-builder-page.ts:397,561 'Form name is required'). When multiple fields are invalid, the user sees one message at a time and must resubmit repeatedly. z.treeifyError/z.prettifyError are unused.
- **Proposed:** When validating a whole page or the full form-builder document with a Zod schema, use z.treeifyError(result.error) to map all issues to fields at once (drives RHF's per-field errors and lets the step show every failing field, not just the first), and z.prettifyError() for a human-readable summary toast. This replaces the first-error-only toast UX with complete error reporting, satisfying the production-quality 'edge cases covered' standard.
- **Doc:** Zod 4 docs (zod.dev/v4): z.treeifyError() and z.prettifyError()
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/app/intake/[slug]/page.client.tsx, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/forms/use-automation-form-builder-page.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/forms/use-template-form-builder-page.ts

#### 9. Rename the TanStack useForm hook to remove the react-hook-form name collision  
`[cleanup]` · impact=low · effort=low · risk=low · breaking=yes

- **Current:** apps/web/lib/hooks/use-forms.ts:128 exports a TanStack-Query hook named useForm(formId) (a useQuery wrapper) that collides with react-hook-form's useForm. As RHF adoption broadens across the codebase, this guarantees import confusion and false-positive greps (already noted in the inventory).
- **Proposed:** Rename the data hook to useFormQuery (or useFormDetails) and update its call sites. This is a no-backward-compat-friendly cleanup (project policy allows breaking changes) that prevents accidental shadowing once multiple files import react-hook-form's useForm, and makes future audits of RHF usage reliable.
- **Doc:** react-hook-form.com/docs/useform (the canonical useForm owner); project CLAUDE.md No-Backward-Compatibility policy
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/lib/hooks/use-forms.ts

### Frontend tooling (TypeScript 5.9 / ESLint 9 flat + typescript-eslint v8 + react-hooks v7 / Vitest 4 / Next 16 build / pnpm 10) in apps/web

The toolchain is already on current versions with a genuinely strong baseline (strict TS with noUncheckedIndexedAccess + exactOptionalPropertyTypes, flat ESLint, no-`any` enforced, no build-error suppression, security-pinned pnpm overrides). The gap is almost entirely unadopted CAPABILITIES of these versions rather than configuration mistakes. The single biggest miss is that the React tooling for a 287-client-component, query-driven app is set up but switched off: eslint-plugin-react-hooks@7 ships 14 React-Compiler/Rules-of-React rules but only the two legacy rules are wired, Next 16's `reactCompiler` is off (and 389 useMemo + 403 useCallback indicate exactly the manual-memoization burden the compiler removes), and `typedRoutes: true` is not set even though Next 16 already generates and wires `.next/types/routes.d.ts` (56 `<Link>` + literal hrefs would gain compile-time validation for free). typescript-eslint is limited to the `recommended` preset with no type-aware linting, so high-value correctness rules (no-floating-promises, no-misused-promises) can't run despite verified candidates (5 unawaited `mutateAsync`, 40 async `onClick`). eslint-config-next is not installed at all, so zero Next-specific lint rules run on a Next app. Vitest 4 runs two duplicated standalone config files instead of one `projects` config, and has no coverage. None of these are version bumps — they are features already paid for and left on the table. Recommendations are ordered by impact.

#### 1. Enable React Compiler rules from eslint-plugin-react-hooks@7 (the 12 RoR/compiler rules currently switched off)  
`[feature-adoption]` · impact=high · effort=low · risk=medium · breaking=no

- **Current:** eslint.config.mjs:13-24 manually wires only the two legacy rules (react-hooks/rules-of-hooks: error, react-hooks/exhaustive-deps: warn). The installed eslint-plugin-react-hooks@7.0.1 also ships react-hooks/set-state-in-effect, set-state-in-render, purity, immutability, refs, preserve-manual-memoization, static-components, error-boundaries, globals, use-memo, config, incompatible-library — none are enabled. The app has 270 useEffect and 500 `.current` usages across 287 client components, exactly the surface these rules guard.
- **Proposed:** Replace the two hand-wired rules with the official flat preset `reactHooks.configs.flat.recommended` (which includes rules-of-hooks + exhaustive-deps + the React-Compiler-aware rules). Land it with the new compiler rules dialed to 'warn' first (override severities in the rules block) so the existing 160-test/CI gate stays green, then ratchet to 'error' file-by-file. This catches real React 19 correctness bugs (state set during render, mutation of props/state, impure render, ref reads in render) statically — DX and correctness win with no runtime change.
- **Doc:** https://github.com/facebook/react/blob/main/packages/eslint-plugin-react-hooks/README.md#installation (reactHooks.configs.flat.recommended); rule list confirmed via plugin introspection
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/eslint.config.mjs

#### 2. Enable Next 16 reactCompiler to auto-memoize and delete most of the 792 manual useMemo/useCallback calls  
`[performance]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** next.config.js has no `reactCompiler` flag and babel-plugin-react-compiler is not installed. The codebase carries 389 useMemo + 403 useCallback + 11 memo() across 287 client components — heavy manual memoization maintained by hand. React Compiler (stable/production-ready on React 19) is exactly the tool that replaces this.
- **Proposed:** Install `babel-plugin-react-compiler` and set `reactCompiler: true` in next.config.js. Next 16 applies the compiler only to files with JSX/Hooks via its SWC pre-pass, so build cost is localized. Adopt incrementally: turn it on globally for auto-memoization, then progressively remove now-redundant useMemo/useCallback (guarded by the preserve-manual-memoization lint rule from the item above). Reduces re-renders and removes a large class of stale-closure dependency-array bugs. Pair with the lint rules first so violations are surfaced before the compiler silently skips a component.
- **Doc:** /Users/chason/GenAI-assited-CRM-Tool/.next-docs/01-app/03-api-reference/05-config/01-next-config-js/reactCompiler.mdx ; https://react.dev/learn/react-compiler/introduction (stable, production-ready)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/next.config.js, /Users/chason/GenAI-assited-CRM-Tool/apps/web/package.json

#### 3. Turn on typedRoutes for compile-time-validated <Link href> and router.push  
`[dx]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** next-env.d.ts already imports `./.next/types/routes.d.ts` (Next 16 generates route typing), but next.config.js does NOT set `typedRoutes: true`, so the static `href`/router validation is not active. The app has 56 `<Link>` with many literal hrefs (e.g. /ops/agencies/new, /settings/integrations/meta/forms) plus 7 router.push/replace and 29 template-literal hrefs.
- **Proposed:** Add `typedRoutes: true` to next.config.js (stable in Next 16, no longer experimental). TypeScript will then reject typo'd or removed routes in `<Link href>` and `next/navigation` push/replace/prefetch at build time; dynamic template hrefs can be cast `as Route` where needed. Near-zero cost since the type artifact is already generated and wired into tsconfig include — this just flips on enforcement and prevents dead-link regressions across the multi-tenant ops/app/settings route trees.
- **Doc:** /Users/chason/GenAI-assited-CRM-Tool/.next-docs/01-app/03-api-reference/05-config/01-next-config-js/typedRoutes.mdx ; .next-docs/01-app/03-api-reference/05-config/02-typescript.mdx (Statically Typed Links)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/next.config.js

#### 4. Add type-aware linting (projectService) + adopt typescript-eslint strict-type-checked  
`[dx]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** eslint.config.mjs:8 spreads only `tseslint.configs.recommended` and sets no `parserOptions.project`/`projectService`. So type-checked rules cannot run. Verified candidates that would be caught: 5 `mutateAsync(` calls with no await, 40 `onClick={async ...}` / async handlers (no-misused-promises / no-floating-promises territory). For a codebase that already runs strict TS with exactOptionalPropertyTypes, this is the biggest unused lint surface.
- **Proposed:** Add `languageOptions.parserOptions.projectService: true` (v8 flat-config way to enable type info without manual project globs) and swap `...tseslint.configs.recommended` for `...tseslint.configs.strictTypeChecked` (optionally plus `stylisticTypeChecked`). This unlocks no-floating-promises, no-misused-promises, await-thenable, no-unnecessary-condition, require-await, etc. Scope type-checked rules to app/components/lib and keep config/JS files on a non-type-checked block to avoid parser errors. High correctness value, especially for fire-and-forget mutations that silently swallow errors in a no-auto-send AI / human-review product.
- **Doc:** https://typescript-eslint.io/users/configs (strict-type-checked, projectService); https://typescript-eslint.io/getting-started/typed-linting
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/eslint.config.mjs, /Users/chason/GenAI-assited-CRM-Tool/apps/web/tsconfig.json

#### 5. Install and wire eslint-config-next — zero Next-specific lint rules currently run  
`[dx]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** package.json devDependencies contain no `eslint-config-next` or `@next/eslint-plugin-next`, and eslint.config.mjs references no `@next/next` rules. On a Next 16 app, none of the Next.js correctness/Core-Web-Vitals rules execute (no-img-element, no-html-link-for-pages, no-sync-scripts, no-async-client-component, inline-script-id, etc.). Note `next lint` was removed in Next 16, so wiring the flat config manually is now the only path.
- **Proposed:** Add `eslint-config-next` and spread `eslint-config-next/core-web-vitals` (and `eslint-config-next/typescript`) into the flat config array, with `globalIgnores` for `.next/**`, `out/**`, `build/**`, `next-env.d.ts`. This is the officially recommended ESLint 9 flat-config setup for Next 16 and surfaces App-Router-specific mistakes the current generic recommended config can't see.
- **Doc:** /Users/chason/GenAI-assited-CRM-Tool/.next-docs/01-app/03-api-reference/05-config/03-eslint.mdx (Setup ESLint flat config; next lint removed in v16)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/eslint.config.mjs, /Users/chason/GenAI-assited-CRM-Tool/apps/web/package.json

#### 6. Consolidate the two Vitest config files into one Vitest 4 projects config  
`[cleanup]` · impact=medium · effort=medium · risk=low · breaking=no

- **Current:** vitest.config.ts (unit) and vitest.integration.config.ts (integration) are standalone files duplicating plugins (@vitejs/plugin-react), the `@`->root alias, env: jsdom, and globals. JSDOM polyfills (matchMedia, ResizeObserver, IntersectionObserver, clipboard, scrollIntoView, getAnimations) are duplicated across tests/setup.ts and tests/setup-integration.ts, and tests/setup-integration.ts:1-6 itself comments it 'should be added as a separate project'.
- **Proposed:** Use Vitest 4's `test.projects` array in a single vitest.config.ts: one 'unit' project (include current unit globs, setupFiles tests/setup.ts) and one 'integration' project (include **/integration/**, setupFiles tests/setup-integration.ts), with `extends: true` so plugins/alias/env are inherited from the root once. Extract the shared JSDOM polyfills into a common setup module imported by both. The legacy `workspace` field was removed/renamed to `projects` in Vitest 3.2+/4 — this is the supported pattern. Removes drift between the two polyfill copies and lets `vitest` run all suites in one pass.
- **Doc:** https://vitest.dev/guide/projects (test.projects, extends: true; workspace deprecated/removed)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/vitest.config.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/vitest.integration.config.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/tests/setup.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/tests/setup-integration.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/package.json

#### 7. Add Vitest 4 coverage (@vitest/coverage-v8) with thresholds in CI  
`[dx]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** No coverage is configured: @vitest/coverage-v8 is not installed and there is no `test.coverage` block in either config, despite 160 test files and a `check` script that gates typecheck+lint+test. There is no visibility into which org-scoping/service paths are tested.
- **Proposed:** Install `@vitest/coverage-v8` and add a `test.coverage` block (v8 is the default provider in Vitest 4) with reporters ['text','html','lcov'], sensible `include`/`exclude`, and minimal thresholds to prevent regressions. Add a `test:coverage` script. Cheap, standard Vitest 4 feature that turns the existing large test suite into an enforceable signal.
- **Doc:** https://vitest.dev/guide/coverage (default provider v8, test.coverage config)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/vitest.config.ts, /Users/chason/GenAI-assited-CRM-Tool/apps/web/package.json

#### 8. Enable verbatimModuleSyntax to lock in type-only import elision  
`[cleanup]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** tsconfig.json has isolatedModules: true and the codebase already uses `import type` 277 times, but `verbatimModuleSyntax` is not set. So nothing enforces that type-only imports are actually marked `type`, and elision behavior is left implicit.
- **Proposed:** Add `verbatimModuleSyntax: true` to tsconfig.json. With isolatedModules already on and `import type` widely adopted, this is low-risk and makes import elision explicit and consistent (each import is emitted or erased exactly as written), preventing accidental value imports of type-only modules and aligning the source with the bundler-resolution setup. Run `tsc --noEmit` once and add `type` to any flagged imports.
- **Doc:** https://www.typescriptlang.org/tsconfig/#verbatimModuleSyntax
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/tsconfig.json

#### 9. Raise tsconfig target/lib above ES2017 to match the Node 24/25 runtime and esnext lib  
`[cleanup]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** tsconfig.json:3 sets `target: ES2017` while lib includes `esnext`, @types/node is ^25.1.0, and the dev runtime is Node v24.13.0. Output is downleveled far more than necessary for a Next 16 app that ships to modern browsers and Node.
- **Proposed:** Bump `target` to ES2022 (or ESNext) so async/await, class fields, top-level patterns, and modern syntax aren't transpiled away, reducing helper bloat and matching the toolchain. This also makes TS 5.x explicit-resource-management (`using`/`await using` via Symbol.dispose/asyncDispose) available — useful for deterministic teardown of MSW servers and WebSocket/test resources currently torn down manually in tests/setup-integration.ts. Verify Browserslist/Next build targets still cover required browsers before merging.
- **Doc:** https://www.typescriptlang.org/tsconfig/#target ; https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html (using / Symbol.dispose)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/web/tsconfig.json

### FastAPI 0.136 + Starlette 1.0 feature-adoption modernization (apps/api)

The API is already on a modern FastAPI (0.136.3) / Starlette (1.0.1) baseline with the right structural choices (lifespan instead of on_event, Pydantic v2 ConfigDict, thin routers, response_model coverage, OTel/Sentry wiring). The gap is that the codebase is NOT using the new ergonomics those versions unlock: a half-finished codemod left 1511+ meaningless `Annotated[X, "fastapi_param"] = Depends(...)` markers instead of idiomatic `Annotated[X, Depends(...)]` + reusable type aliases; query filters are declared as long lists of individual `Query()` params (17 on list_surrogates alone) instead of Pydantic query-param models (0.115+); there are no global exception handlers to normalize 422/4xx bodies to the project's JSON contract; the custom `get_db_for_stream()` contextmanager is now obsolete because 0.118 fixed dependency-with-yield teardown to run after the StreamingResponse finishes; FastAPI 0.118's automatic per-request dependency caching makes the hand-rolled `request.state.user_session` memoization partly redundant; and several `async def` handlers still call the sync SQLAlchemy Session directly on the event loop. None of these are version bumps — they are concrete features already shipped in the installed versions but unused. The highest-leverage items are the Annotated/type-alias cleanup (touches all 74 routers, big DX win, low risk) and adopting query-param models on the heavy list/filter endpoints. All recommendations preserve org-scoping, thin-router, and cookie-JWT+CSRF constraints.

#### 1. Finish the Annotated dependency migration with shared type aliases (DbSession / CurrentSession / OrgScope)  
`[dx]` · impact=high · effort=high · risk=low · breaking=no

- **Current:** A codemod left a half-finished state: 1511+ occurrences of `Annotated[X, "fastapi_param"] = Depends(...)` across 74 router files (e.g. attachments.py:93-97, surrogates_read.py:69-70, meta_oauth.py:202-203). The literal string "fastapi_param" is a meaningless marker; the actual Depends() still lives in the default argument, so the code reads like the legacy `= Depends()` style with extra noise. Every handler repeats the full `Annotated[Session, ...] = Depends(get_db)` and `Annotated[UserSession, ...] = Depends(get_current_session)` instead of reusing one alias. `Annotated` is already imported in all 74 routers.
- **Proposed:** Adopt FastAPI's recommended idiomatic form `Annotated[Type, Depends(dep)]` and define reusable type aliases once in app/core/deps.py: `DbSession = Annotated[Session, Depends(get_db)]`, `CurrentSession = Annotated[UserSession, Depends(get_current_session)]`, `OrgScope = Annotated[UUID, Depends(get_org_scope)]`, and factory-based aliases helper for require_permission. Handlers become `def handler(db: DbSession, session: CurrentSession)`. Run a codemod to strip the `"fastapi_param"` marker and move the dependency into Annotated. This removes ~1500 lines of noise and gives a single source of truth for the auth/db wiring.
- **Doc:** FastAPI docs - Dependencies ("Prefer to use the Annotated version if possible") and Classes as Dependencies / Shared Annotated dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/#share-annotated-dependencies
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/deps.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/ (all 74 router files, e.g. attachments.py, surrogates_read.py, meta_forms.py, meta_oauth.py)

#### 2. Delete get_db_for_stream() and use the normal get_db dependency for SSE streaming (fixed in FastAPI 0.118)  
`[cleanup]` · impact=medium · effort=medium · risk=medium · breaking=no

- **Current:** deps.py:136-143 defines a separate `@contextmanager get_db_for_stream()` that opens its own SessionLocal(), and ai_chat.py:192 manually does `with get_db_for_stream() as stream_db:` inside the SSE `event_generator()` because the regular `get_db` yield-dependency used to be torn down before the StreamingResponse body ran. This is a workaround for pre-0.118 behavior and means the streaming session bypasses the normal dependency graph (no request.state.request_db, separate lifecycle).
- **Proposed:** FastAPI 0.118 reverted the teardown timing so exit code after `yield` now runs AFTER the response (including a StreamingResponse) is sent. The injected `db` from `Depends(get_db)` is therefore valid for the entire stream. Drop `get_db_for_stream`, remove the manual `with` block in chat_stream, and stream using the already-injected `db` (or move the streaming DB work to the external worker if you want to fully isolate it). Audit the other 56 StreamingResponse/text-event-stream call sites for the same now-unnecessary pattern.
- **Doc:** FastAPI 0.118.0 release notes - dependencies with yield + StreamingResponse teardown reverted to run after response is sent: https://fastapi.tiangolo.com/release-notes/#01180
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/deps.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/ai_chat.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/utils/sse.py

#### 3. Group repeated list/filter query params into Pydantic query-param models (FastAPI 0.115+)  
`[feature-adoption]` · impact=medium · effort=medium · risk=low · breaking=no

- **Current:** List endpoints declare long flat lists of individual `Query()` params: list_surrogates (surrogates_read.py:159-189) has 17 separate query parameters; get_surrogate_stats (surrogates_read.py:67-86) repeats from_date/to_date/timezone/pipeline_id/owner_id. There are 223 `= Query(` declarations across 27 routers, with the same pagination/date-range/owner-filter trios duplicated across surrogates, intended_parents, analytics, audit, and notifications.
- **Proposed:** Define Pydantic query-param models (e.g. `PaginationParams`, `DateRangeParams`, `SurrogateListFilters`) and inject them as `filters: Annotated[SurrogateListFilters, Query()]`. Set `model_config = ConfigDict(extra="forbid")` so unknown query params return a clean 422 (tighter API contract for a multi-tenant product). This centralizes validation (ge/le bounds, regex patterns like `^(asc|desc)$`), removes duplication, and produces cleaner OpenAPI. Keep org-scoping unchanged - the model carries only filter inputs; org_id still comes from get_org_scope/session.
- **Doc:** FastAPI docs - Query Parameter Models (added 0.115.0), incl. forbidding extra params: https://fastapi.tiangolo.com/tutorial/query-param-models/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/surrogates_read.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/analytics.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/intended_parents.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/audit.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/utils/pagination.py

#### 4. Register global exception handlers for RequestValidationError and StarletteHTTPException to normalize error bodies  
`[dx]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** main.py:482 registers exactly one handler: `add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)`. There is no @app.exception_handler for RequestValidationError or StarletteHTTPException, so 422 validation errors emit FastAPI's default verbose array shape and other 4xx bodies aren't normalized to a consistent JSON contract. Cross-cutting error capture is done by re-catching exceptions inside gcp_error_reporting_middleware (main.py:237-294) rather than via handlers.
- **Proposed:** Add `@app.exception_handler(RequestValidationError)` and `@app.exception_handler(StarletteHTTPException)` that return the project's canonical error envelope (e.g. `{"detail": ..., "error_code": ..., "request_id": ...}`), wrapping the default handlers (`from fastapi.exception_handlers import request_validation_exception_handler`) so behavior is preserved while adding the request_id and stable shape the frontend already keys off. This also lets you stop relying on middleware catch-and-reraise for 4xx normalization. Keep the existing 5xx alerting/error-reporting middleware for server errors.
- **Doc:** FastAPI docs - Handling Errors (override RequestValidationError / StarletteHTTPException, reuse default handlers): https://fastapi.tiangolo.com/tutorial/handling-errors/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/ (new errors handler module)

#### 5. Make async handlers that touch the sync Session non-blocking (def, run_in_threadpool, or worker offload)  
`[performance]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** 16 routers contain `async def` handlers that call the sync SQLAlchemy Session directly on the event loop: meta_oauth.meta_callback (meta_oauth.py:196-310 calls db.commit()/save_oauth_connection synchronously), attachments.upload_attachment (attachments.py:89-141 db.commit() + attachment_service.upload_attachment), plus integrations.py, webhooks.py, invites.py, settings.py, ai_studio.py, surrogates_import.py, etc. With a sync DB, each synchronous db call inside an async def blocks the single event loop, undermining the threadpool model the rest of the app (744 sync def handlers) relies on.
- **Proposed:** For handlers that are async only to await a couple of HTTP calls (meta_callback awaits token exchange), wrap the blocking DB section in `await run_in_threadpool(...)` (Starlette helper already used in utils/file_upload.py) or split the awaited I/O from the sync DB work. For handlers that have no real reason to be async, convert them to plain `def` so FastAPI auto-runs them in the anyio worker threadpool (safe with the sync Session). Audit all 16 files identified by grepping `async def` + `db.commit()`.
- **Doc:** FastAPI docs - Concurrency and async/await (sync funcs run in external threadpool; don't block the loop) + Starlette concurrency.run_in_threadpool: https://fastapi.tiangolo.com/async/#path-operation-functions
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/meta_oauth.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/attachments.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/integrations.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/webhooks.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/invites.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/settings.py

#### 6. Lean on FastAPI 0.118 automatic per-request dependency caching instead of hand-rolled request.state.user_session memoization  
`[architecture]` · impact=medium · effort=high · risk=medium · breaking=no

- **Current:** get_current_session (deps.py:185-396) hand-caches its result on `request.state.user_session` (deps.py:199-201) to avoid re-running for every dependency that needs it (require_permission, get_org_scope, etc. each call get_current_session(request, db) imperatively rather than via Depends). This bypasses FastAPI's dependency graph: the authz factories manually invoke get_current_session(request, db) instead of declaring `session: CurrentSession`.
- **Proposed:** FastAPI 0.118 added automatic caching of dependencies that don't use scopes and have no scoped sub-dependencies, so a single `Depends(get_current_session)` resolved once per request is reused by all dependents for free. Refactor the authz factories to declare `session: Annotated[UserSession, Depends(get_current_session)]` and `db: Annotated[Session, Depends(get_db)]` as real sub-dependencies instead of calling them imperatively; then the framework's cache replaces the manual request.state.user_session memo. This makes the dependency graph honest, improves testability (override-able deps), and removes a subtle source of state. Keep the support/MFA logic identical.
- **Doc:** FastAPI 0.118.0 release notes - non-scoped dependencies are now cached per request; Dependencies caching docs: https://fastapi.tiangolo.com/release-notes/#01180 and https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/#using-the-same-dependency-multiple-times
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/deps.py

#### 7. Standardize Form/File parameter declarations on the idiomatic Annotated[..., File()] style  
`[cleanup]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** Upload params are declared two ways: idiomatic `file: Annotated[UploadFile, File()]` (e.g. attachments.py:91, 290) vs the codemod hybrid `file: Annotated[UploadFile, "fastapi_param"] = File()` (e.g. auth.py:404, forms_public.py:530-531). Only about half are in the modern single-style form, so the same concept reads two different ways across ~12 routers.
- **Proposed:** As part of the Annotated cleanup, normalize all File()/Form()/UploadFile declarations to put the marker inside Annotated: `Annotated[UploadFile, File()]`, `Annotated[str, Form()]`, `Annotated[list[UploadFile], File()]`. Remove the `"fastapi_param"` literal. This is the same codemod pass as recommendation #1 but called out separately because multipart endpoints have extra cases (list[UploadFile], Form fields mixed with File).
- **Doc:** FastAPI docs - Request Files / Form Models (Annotated metadata form): https://fastapi.tiangolo.com/tutorial/request-files/ and https://fastapi.tiangolo.com/tutorial/request-form-models/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/auth.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/forms_public.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/attachments.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/admin_imports.py

#### 8. Manage shared long-lived resources via lifespan state instead of module-level singletons  
`[architecture]` · impact=medium · effort=medium · risk=medium · breaking=no

- **Current:** The lifespan handler (main.py:198-218) only runs the migration check, binds the asyncio loop, and starts the websocket/session-revocation listeners. Long-lived resources - the Redis client (get_sync_redis_client), the SQLAlchemy engine, and the websocket manager - are module-level globals imported across the app. There is no shutdown cleanup (no listener teardown, no engine.dispose(), no Redis close) in the lifespan exit, and no use of FastAPI's typed lifespan state.
- **Proposed:** Move shared-resource setup/teardown into the lifespan: start listeners on entry and cancel/await them after `yield`; call `engine.dispose()` and close the Redis pool on shutdown for clean Cloud Run SIGTERM handling. Optionally expose resources via `app.state` (or the yielded lifespan state) so they're injectable/overridable in tests instead of imported globals. This gives deterministic startup/shutdown and removes import-time side effects.
- **Doc:** FastAPI docs - Lifespan Events (manage resources, yield state, cleanup after yield): https://fastapi.tiangolo.com/advanced/events/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/redis_client.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/db/session.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/websocket.py

#### 9. Add shared error responses= and a stable generate_unique_id_function for cleaner OpenAPI / client codegen  
`[dx]` · impact=low · effort=medium · risk=low · breaking=no

- **Current:** OpenAPI is left at defaults: no APIRouter-level `responses=` declaring the common 401/403/422/429 error schemas (which every authed router returns), no `generate_unique_id_function`, no `separate_input_output_schemas` tuning, no `servers`/`root_path`. operationIds default to `<name>_<path>_<method>`, which produces noisy, churny names for any TS client generated from the schema. Docs are simply disabled in prod (main.py:225-226).
- **Proposed:** Define a shared `ERROR_RESPONSES` dict (401/403/422/429 -> a project error schema) and attach it via `APIRouter(responses=ERROR_RESPONSES)` on the authed routers, and/or app-level. Add a `generate_unique_id_function` that yields stable `tag-route` operationIds so the frontend's generated client stays diff-friendly. These are pure OpenAPI/DX improvements with zero runtime behavior change and pair naturally with the new global exception handlers (#4) so documented and actual error shapes match.
- **Doc:** FastAPI docs - Generate Clients (generate_unique_id_function) and Additional Responses (shared responses=): https://fastapi.tiangolo.com/advanced/generate-clients/#custom-generate-unique-id and https://fastapi.tiangolo.com/advanced/additional-responses/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/ (shared responses module), /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/ (APIRouter constructors)

### SQLAlchemy 2.0 + psycopg3 feature adoption (apps/api)

The codebase is already on modern SQLAlchemy 2.0 declarative mapping (Mapped[]/mapped_column everywhere, single DeclarativeBase, psycopg3 sync driver) — the foundation is excellent. What is unadopted is the set of behavioral/feature capabilities these versions unlock: (1) a framework-level multi-tenant backstop via with_loader_criteria + a do_orm_execute event (today all ~1593 organization_id filters are hand-written, so one miss is a cross-tenant leak with zero safety net); (2) raiseload / lazy="raise_on_sql" to make accidental N+1 lazy loads fail loudly instead of silently (294 of 296 relationships use default lazy="select"); (3) psycopg3 COPY for the bulk import/export hot paths that currently loop db.add() per row; (4) the 2.0 unified select()+execute() idiom rolling out over the ~1057 legacy db.query() calls; (5) modern bulk INSERT/UPDATE via Session.execute(insert/update(Model), [dicts]) replacing the deprecated bulk_update_mappings and per-row add loops; and (6) pool hardening (pool_recycle is -1 / disabled). The multi-tenant backstop and raiseload items are the highest-value because they directly harden the project's #1 non-negotiable (org-scoping) and the zero-tolerance N+1 rule. None of these require version bumps — they are pure feature adoption on the versions already installed.

#### 1. Add a defense-in-depth org-scoping backstop with with_loader_criteria + do_orm_execute event  
`[security]` · impact=high · effort=high · risk=medium · breaking=no

- **Current:** Multi-tenant isolation is 100% manual: ~1593 hand-written organization_id filters in services, supplied via get_org_scope() (apps/api/app/core/deps.py:569-577). There is no framework-level enforcement — a single forgotten .filter(Model.organization_id == org_id) is a silent cross-tenant data leak. The session is plain SessionLocal() from apps/api/app/db/session.py:33 with no ORM events attached.
- **Proposed:** Attach a do_orm_execute event listener to the session that injects with_loader_criteria(<Entity>, lambda cls: cls.organization_id == current_org_id, include_aliases=True) for every org-scoped entity on SELECTs (skipping is_column_load/is_relationship_load per the official pattern). Carry the request's org_id in session.info (set it in get_db/get_current_session). This auto-propagates the org filter into relationship loads and subqueries too, becoming a backstop layer behind the existing manual filters — not a replacement. Keep manual filters; this catches the one that gets missed. This is the single highest-value adoption because it directly hardens the project's #1 non-negotiable rule.
- **Doc:** SQLAlchemy 2.0 docs — ORM Query Guide, with_loader_criteria() and the 'do_orm_execute' / ORMExecuteState event recipe (docs.sqlalchemy.org/en/20/orm/queryguide/api.html#sqlalchemy.orm.with_loader_criteria and /en/20/orm/session_events.html)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/db/session.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/deps.py

#### 2. Make accidental N+1 lazy loads fail loudly with lazy="raise_on_sql" / raiseload()  
`[performance]` · impact=high · effort=medium · risk=medium · breaking=yes

- **Current:** 294 of 296 relationship() declarations use the default lazy="select" (only Surrogate.owner_user/owner_queue set lazy="selectin" at apps/api/app/db/models/surrogates.py:415,422). N+1 protection relies entirely on per-query joinedload/selectinload (only ~79 such options total). Any code path that touches a relationship without explicit eager-loading silently emits an N+1 query with no signal, directly violating the project's zero-tolerance performance rule. No use of raiseload() or lazy="raise" anywhere.
- **Proposed:** Set lazy="raise_on_sql" on hot/large relationships (e.g. Surrogate.status_history and Surrogate.contact_attempts at surrogates.py:426,429; Organization.surrogates at auth.py:114) so any unintended lazy load raises instead of quietly running a query — forcing callers to declare joinedload/selectinload. For list endpoints, add a project convention of raiseload('*') after explicit eager-loads to guarantee the query graph is fully specified (surrogate_service.py list paths at surrogate_service.py:1739-1745, 1860-1907 already use joinedload(...).load_only(...) and would benefit immediately). Roll out incrementally per-relationship so existing eager-loaded paths keep working.
- **Doc:** SQLAlchemy 2.0 docs — Relationship Loading Techniques: 'Preventing unwanted lazy loads using raiseload' and lazy="raise"/"raise_on_sql" (docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#preventing-unwanted-lazy-loads-using-raiseload)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/db/models/surrogates.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/db/models/auth.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/surrogate_service.py

#### 3. Use psycopg3 COPY for bulk CSV import/export hot paths  
`[performance]` · impact=high · effort=high · risk=medium · breaking=no

- **Current:** admin_import_service.py imports surrogates by looping db.add(surrogate) one object per CSV row (apps/api/app/services/admin_import_service.py:1003 inside a per-row loop; ~20 other per-row db.add() calls at lines 317-709) then db.flush()/db.commit(). Export uses ORM query.yield_per(500) feeding csv.writer row-by-row (apps/api/app/services/admin_export_service.py:163-173, 292). psycopg3's first-class COPY support (cursor.copy() / copy.write_row(), and COPY TO for export) is completely unused — these are an order of magnitude faster than per-row ORM INSERT/SELECT for large batches.
- **Proposed:** For large imports, build the rows and use COPY ... FROM STDIN via the raw psycopg3 cursor obtained from the SQLAlchemy connection (connection.connection.cursor().copy(...)), writing rows with copy.write_row(). For large exports, stream COPY (...) TO STDOUT directly into the StreamingResponse instead of ORM yield_per + csv.writer. Keep encryption (EncryptedString/Date TypeDecorators in db/types.py) in mind — only use COPY for non-encrypted bulk columns or pre-encrypt values before writing; fall back to the ORM path for rows needing per-field transformation. This keeps the existing endpoints but swaps the engine room for the big-batch case.
- **Doc:** psycopg 3 docs — 'Using COPY TO and COPY FROM' (psycopg.org/psycopg3/docs/basic/copy.html); SQLAlchemy 2.0 docs — accessing the DBAPI connection via Connection.connection
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/admin_import_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/admin_export_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/import_service.py

#### 4. Replace deprecated bulk_update_mappings and per-row add loops with 2.0 bulk Session.execute(insert/update(Model), [dicts])  
`[feature-adoption]` · impact=medium · effort=medium · risk=low · breaking=no

- **Current:** admin_import_service.py:1009 still calls the legacy db.bulk_update_mappings(MetaLead, [...]). Write paths loop-and-add individual ORM objects (admin_import_service.py:317-709, ~20 db.add() calls; pipeline_service.py:650,895 and form_service.py:499 use db.add_all but most writes are per-row). SQLAlchemy 2.0's insertmanyvalues-backed bulk path (Session.execute(insert(Model), [list_of_dicts])) and bulk-by-PK update (Session.execute(update(Model), [list_of_dicts])) are barely used (21 update/delete statements, 1 bulk_update_mappings total).
- **Proposed:** Convert db.bulk_update_mappings(MetaLead, ...) to db.execute(update(MetaLead), [{...}]) — the documented modern equivalent that integrates with session synchronization and supports RETURNING. Convert the surrogate import loop to a single db.execute(insert(Surrogate), [row_dicts]) batch (using render_nulls where server defaults aren't needed), which fires insertmanyvalues batching automatically (default 1000 rows/statement) instead of one INSERT per object. bulk_*_mappings is documented as legacy in 2.0.
- **Doc:** SQLAlchemy 2.0 docs — 'ORM-Enabled INSERT, UPDATE, and DELETE statements': ORM Bulk INSERT/UPDATE by Primary Key and the legacy-to-modern mapping table (docs.sqlalchemy.org/en/20/orm/queryguide/dml.html)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/admin_import_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/pipeline_service.py

#### 5. Standardize on the 2.0 unified select()+execute()/scalars() idiom over legacy db.query()  
`[dx]` · impact=medium · effort=high · risk=low · breaking=no

- **Current:** Query API is split: ~1057 legacy db.query(...) calls vs only ~123 select() statements and ~75 .execute(). Heaviest legacy users verified: ticketing_service.py (72), pipeline_service.py (35), surrogate_service.py (25), workflow_service.py (25). The clean 2.0 style already exists and is proven in session_service.py:133-343 and search_service.py (0 .query(), 23 select(), all via db.execute(stmt).fetchall()). Two idioms in one codebase increases cognitive load and makes the with_loader_criteria/raiseload adoptions (above) inconsistent, since the loader-criteria event keys off SELECT statements.
- **Proposed:** Adopt a project convention that new code uses select()+db.scalars()/db.execute(), and migrate the legacy Query call sites service-by-service starting with the heaviest (ticketing_service.py, pipeline_service.py). The 2.0 select() path is what with_loader_criteria options attach to cleanly and what makes raiseload composition uniform. Use session_service.py and search_service.py as the in-repo reference implementations. This is a gradual cleanup, not a big-bang rewrite.
- **Doc:** SQLAlchemy 2.0 docs — 'What's New in SQLAlchemy 2.0?' / ORM Querying Guide: 1.x Query API vs 2.0 select() unified style (docs.sqlalchemy.org/en/20/changelog/whatsnew_20.html and /en/20/orm/queryguide/select.html)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/ticketing_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/pipeline_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/surrogate_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/workflow_service.py

#### 6. Use WriteOnlyMapped (lazy="write_only") for large unbounded one-to-many collections  
`[performance]` · impact=medium · effort=medium · risk=medium · breaking=yes

- **Current:** Organization.surrogates (apps/api/app/db/models/auth.py:114) is a one-to-many that can hold an entire tenant's surrogate population, declared with default lazy="select" — accessing org.surrogates materializes the full collection into memory. Same shape for Surrogate.status_history / Surrogate.contact_attempts (surrogates.py:426,429), which grow unbounded over a case's lifetime. No WriteOnlyMapped / DynamicMapped anywhere in the models.
- **Proposed:** Declare these large/unbounded collections as WriteOnlyMapped[...] with relationship(lazy="write_only"). This blocks accidental full-collection loads entirely (only .add()/.add_all()/.remove() are allowed; reads require an explicit .select() the caller paginates/filters), which is exactly the behavior you want on big tenants. It pairs naturally with raiseload above. DynamicMapped is the legacy precursor and is superseded by write-only per the docs — use write_only.
- **Doc:** SQLAlchemy 2.0 docs — 'Write Only Relationships' / WriteOnlyMapped (docs.sqlalchemy.org/en/20/orm/large_collections.html#write-only-relationships)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/db/models/auth.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/db/models/surrogates.py

#### 7. Harden connection pool: enable pool_recycle and pool_use_lifo  
`[architecture]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** DB_POOL_RECYCLE defaults to -1 — recycling disabled, so pooled connections are never proactively refreshed (apps/api/app/core/config.py:111, wired in apps/api/app/db/session.py:25). This is risky behind cloud load balancers / PgBouncer / Postgres idle-timeout that silently drop idle connections; today only pool_pre_ping (config.py:112) masks it, at the cost of an extra round-trip per checkout. poolclass and pool_use_lifo are left at defaults (FIFO QueuePool).
- **Proposed:** Set a sane DB_POOL_RECYCLE (e.g. 1800s) so connections are refreshed before infra reaps them, reducing reliance on pre-ping round-trips. Add pool_use_lifo=True to create_engine in session.py so a small steady-state load keeps reusing a hot subset of connections and lets idle ones age out (works well with recycle). These are deployment-shape tunables exposed cleanly by SQLAlchemy 2.0's pool config.
- **Doc:** SQLAlchemy 2.0 docs — Connection Pooling: 'Setting Pool Recycle' and 'Using FIFO vs. LIFO' (docs.sqlalchemy.org/en/20/core/pooling.html#setting-pool-recycle and #using-fifo-vs-lifo)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/db/session.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/config.py

#### 8. Use begin-once transaction blocks instead of implicit autoflush + scattered manual commit()  
`[cleanup]` · impact=low · effort=medium · risk=low · breaking=no

- **Current:** There are 0 uses of with db.begin() / engine.begin() begin-once blocks; only begin_nested() (savepoints) appears (task_service.py:1102,1123; surrogate_service.py:641; version_service.py:201). The session is autoflush=False (apps/api/app/db/session.py:33) and transaction boundaries are implicit, relying on scattered manual db.commit() calls across services. This makes it easy to leave a transaction open or commit partial work on an error path.
- **Proposed:** For multi-step write operations in services, wrap the unit of work in a with db.begin(): block (begin-once) so commit-on-success / rollback-on-exception is automatic and the transaction boundary is explicit in one place. This is the idiomatic 2.0 transaction-scoping pattern and removes a class of partial-write bugs without changing the per-request session lifecycle in deps.py.
- **Doc:** SQLAlchemy 2.0 docs — Working with Transactions and the DBAPI: 'Begin Once' / Session.begin() context manager (docs.sqlalchemy.org/en/20/orm/session_transaction.html)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/admin_import_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/pipeline_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/surrogate_service.py

### Pydantic 2.12 + pydantic-settings 2.12 modernization for apps/api

The backend is fully on Pydantic v2 with no v1 leftovers (no class Config, no @validator, no .dict()), which is a healthy baseline. The highest-value untapped capabilities are security-oriented and architectural rather than syntactic: every credential in core/config.py is a plain str (zero SecretStr), which directly conflicts with the project's "never log raw PII / keys are write-only" rule since these values currently render in repr/tracebacks/error dumps. Beyond that, the schema layer never uses the Annotated pattern, so the same phone/state normalizers and length/pattern constraints are copy-pasted across surrogate.py and intended_parent.py instead of living in one reusable constrained type; polymorphic shapes (forms.py FormField family, AI/workflow dict payloads) are validated as untyped dict[str, object] rather than discriminated unions; and the native pydantic.JsonValue type is hand-rolled as `object` in types.py. There are also genuine quick wins: standardizing the 39 plain-dict model_config literals on ConfigDict, adopting typed ValidationInfo, and using a cached TypeAdapter(list[Model]) for the repeated `[Model(**item).model_dump() for item in data]` loops in analytics.py. Recommendations are ordered by impact; the SecretStr migration is the only one with meaningful call-site fan-out (all changes are internal-only, which project policy permits).

#### 1. Type all credentials in Settings as SecretStr to prevent leaking keys in logs/tracebacks  
`[security]` · impact=high · effort=medium · risk=medium · breaking=yes

- **Current:** Every secret in apps/api/app/core/config.py is a plain `str` with zero SecretStr usage: JWT_SECRET (117), JWT_SECRET_PREVIOUS (118), GOOGLE_CLIENT_SECRET (124), META_APP_SECRET (177), META_ENCRYPTION_KEY (180), FERNET_KEY (203), DATA_ENCRYPTION_KEY (206), PII_HASH_KEY (207), ZOOM_CLIENT_SECRET (198), AWS_SECRET_ACCESS_KEY (382), DUO_CLIENT_SECRET (398), DUO_ADMIN_SECRET_KEY (402), AUDIT_HMAC_SECRET (158), INTERNAL_SECRET (194), DEV_SECRET (170), WIF_OIDC_PRIVATE_KEY (222), etc. Because `Settings` is a normal Pydantic model, any `repr(settings)`, exception dump, or Sentry/GCP error context that touches the settings object will print these values in cleartext.
- **Proposed:** Change the sensitive fields to `SecretStr` (`from pydantic import SecretStr`). SecretStr renders as `**********` in repr/str/JSON/tracebacks and only exposes the real value via `.get_secret_value()`. Consumers are a small, bounded set in core/encryption.py, core/security.py, services/meta_api.py, services/meta_oauth_service.py, services/duo_service.py, services/storage_client.py, services/oauth_service.py, services/google_oauth.py, services/*_settings_service.py, services/platform_service.py — update each to call `.get_secret_value()` (e.g. `settings.FERNET_KEY.get_secret_value().encode()`, `hmac.new(settings.META_APP_SECRET.get_secret_value().encode(), ...)`). The `@property` accessors jwt_secrets/duo_enabled also need a `.get_secret_value()`/truthiness tweak. This directly enforces the CLAUDE.md 'never log raw PII / keys are write-only' boundary at the type level.
- **Doc:** Pydantic docs — Secret types / SecretStr (https://pydantic.dev/docs/validation/latest/concepts/types/) and pydantic-settings concepts (https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/config.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/encryption.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/security.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/meta_api.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/meta_oauth_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/duo_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/oauth_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/google_oauth.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/storage_client.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/platform_service.py

#### 2. Adopt the Annotated pattern to define reusable constrained types (PhoneStr, StateCode, NormalizedSSN) and collapse duplicated field_validators  
`[architecture]` · impact=high · effort=medium · risk=low · breaking=no

- **Current:** Zero `Annotated[...]`/`StringConstraints`/`AfterValidator` usage. The same normalization logic is re-declared as separate @field_validator blocks across schemas — surrogate.py alone repeats normalize_phone over `phone` + 15 optional phone fields (203-248) and normalize_state over `state` + 7 state fields (211-275), and intended_parent.py duplicates the same families. Length/pattern constraints are also inlined per-field (e.g. `Field(min_length=1, max_length=100)` repeated dozens of times across forms.py:75/84/85/93/94/99/100/235/252, custom_field.py, task.py).
- **Proposed:** Define shared annotated types once in app/types.py (or a new app/schemas/_types.py): `PhoneStr = Annotated[str | None, BeforeValidator(normalize_phone)]`, `StateCode = Annotated[str | None, BeforeValidator(normalize_state)]`, `NormalizedSSN = Annotated[str | None, AfterValidator(normalize_ssn)]`, and reusable constrained primitives like `FieldKey = Annotated[str, StringConstraints(min_length=1, max_length=100)]`. Then annotate fields directly (`phone: PhoneStr = None`), deleting the ~6 duplicated validator methods. Validators travel with the type, stay DRY, and any new schema referencing a phone/state field gets normalization for free. Imports: `from typing import Annotated; from pydantic import StringConstraints, BeforeValidator, AfterValidator`.
- **Doc:** Pydantic docs — Types: the Annotated pattern & reusable constrained types (https://pydantic.dev/docs/validation/latest/concepts/types/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/types.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/surrogate.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/intended_parent.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/forms.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/custom_field.py

#### 3. Model polymorphic form fields as a discriminated union instead of one dict-shaped FormField  
`[feature-adoption]` · impact=high · effort=high · risk=medium · breaking=yes

- **Current:** apps/api/app/schemas/forms.py defines a single FormField (98-112) carrying every type-specific attribute as optional (options, validation, columns, rows, min_rows, max_rows) and a `type: FieldType` Literal of 16 values. A `select`/`radio` field semantically requires `options`; a `table`/`repeatable_table` requires `columns`; a `number` uses min_value/max_value — but nothing enforces this, so invalid combinations validate cleanly. The same shape gap exists for `value: object | None` conditions and the many `dict[str, object]` answer/config payloads.
- **Proposed:** Split FormField into per-type variants (e.g. ChoiceField with required `options`, TableField with required `columns`, TextField, NumberField with numeric validation) joined as `Annotated[Union[...], Field(discriminator='type')]`. Pydantic then validates only the matched variant — faster, and emits a precise error (e.g. 'options required for select') instead of silently accepting a malformed field. Imports: `from typing import Annotated, Union; from pydantic import Field` (or `Discriminator`/`Tag` for the callable case). This hardens the public intake/embed surface (forms_public.py) where untrusted JSON is parsed.
- **Doc:** Pydantic docs — Unions: discriminated unions / Field(discriminator=...) (https://pydantic.dev/docs/validation/latest/concepts/unions/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/forms.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/forms_public.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/form_submission_service.py

#### 4. Replace hand-rolled JsonValue alias with pydantic.JsonValue for real recursive JSON validation  
`[cleanup]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** apps/api/app/types.py:7 declares `JsonValue: TypeAlias = object` (with JsonObject/JsonArray built on it). `object` accepts literally anything, so JSON-shaped fields get no structural validation — and the alias collides in name with Pydantic's own type. Many schema fields use `dict[str, object]` / `list[dict]` for JSON payloads (forms.py answers/thank_you_config/embed_theme_json, ai_tasks.py BulkTaskCreateResponse.created).
- **Proposed:** Import Pydantic's native `JsonValue` (`from pydantic import JsonValue`) which is a recursive `str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]` that actually validates the value is JSON-serializable. Re-export it (or alias JsonObject = `dict[str, JsonValue]`) from app/types.py and use it where genuine free-form JSON is stored, so non-JSON values (e.g. a datetime that won't serialize) are rejected at the boundary rather than blowing up later at model_dump(mode='json').
- **Doc:** Pydantic docs — Standard library / JsonValue type (https://pydantic.dev/docs/validation/latest/api/types/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/types.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/forms.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/ai_tasks.py

#### 5. Use a cached TypeAdapter(list[Model]) for the repeated [Model(**item).model_dump() for item in data] loops  
`[performance]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** apps/api/app/routers/analytics.py builds 9 endpoints (lines 403, 458, 494, 522, 546, 565, 584, 603) as `[SomeItem(**item).model_dump() for item in data]`, instantiating and dumping each model individually in a Python loop. TypeAdapter is used only once in the entire backend (surrogate_service.py:57 for EmailStr).
- **Proposed:** Define module-level cached adapters once, e.g. `_SPEND_TREND_ADAPTER = TypeAdapter(list[SpendTrendPoint])`, then `return {'data': _SPEND_TREND_ADAPTER.dump_python(_SPEND_TREND_ADAPTER.validate_python(data))}`. TypeAdapter validates/serializes the whole list in pydantic-core (Rust) in one call and the schema is built once at import instead of per-request, cutting per-request overhead on these analytics list endpoints. Same pattern applies to the bulk `[m.model_dump() for m in ...]` loops in meta_forms.py:205, zapier.py:324, import_templates.py:63/105, appointments.py:268, forms.py:687.
- **Doc:** Pydantic docs — TypeAdapter (https://pydantic.dev/docs/validation/latest/concepts/type_adapter/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/analytics.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/meta_forms.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/import_templates.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/appointments.py

#### 6. Standardize model_config on typed ConfigDict instead of plain dict literals  
`[dx]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** Two inconsistent styles coexist: 39 plain-dict literals like `model_config = {"from_attributes": True}` (e.g. custom_field.py:73/87/110, task.py:88/121, user.py:19, surrogate.py:753, surrogate_mass_edit.py:55 `{"extra": "forbid"}`) versus only 14 typed `ConfigDict(...)` calls confined to 5 files (entity_note.py, email.py, job.py, intended_parent.py, platform_templates.py). The dict form is valid but gives no key/type checking or IDE autocomplete, so a typo like `{"from_attribute": True}` silently does nothing.
- **Proposed:** Convert every `model_config = {...}` to `model_config = ConfigDict(...)` (add `from pydantic import ConfigDict`). Mechanical, fully covered by the existing test suite, and gives static type-checking of config keys. Optionally codify shared base configs (e.g. an `ORMModel(BaseModel)` with `model_config = ConfigDict(from_attributes=True)`) so the 17 ORM-read schemas inherit it rather than repeating the flag.
- **Doc:** Pydantic docs — Configuration / ConfigDict (https://pydantic.dev/docs/validation/latest/api/config/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/custom_field.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/task.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/user.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/surrogate.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/surrogate_mass_edit.py

#### 7. Annotate cross-field validators with typed ValidationInfo  
`[dx]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** apps/api/app/schemas/custom_field.py:43 `validate_options(cls, v, info)` takes `info` untyped and reads `info.data.get('field_type')` with no type safety; the same untyped-info shape appears in the cross-field validators in ai_tasks.py and others that inspect sibling fields.
- **Proposed:** Annotate as `info: ValidationInfo` (`from pydantic import ValidationInfo`). This gives static typing for `info.data` / `info.field_name` and is the documented modern v2 signature for cross-field field_validators, catching typos in field-name lookups at type-check time (the project enforces zero TypeScript/lint warnings; the same standard should apply to typed Python).
- **Doc:** Pydantic docs — Validators / ValidationInfo (https://pydantic.dev/docs/validation/latest/concepts/validators/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/custom_field.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/ai_tasks.py

#### 8. Group the ~150-field flat Settings into nested settings models via env_nested_delimiter / secrets_dir  
`[architecture]` · impact=medium · effort=high · risk=high · breaking=yes

- **Current:** apps/api/app/core/config.py is one flat Settings class with ~150 fields spanning DB, JWT, CORS, Google/Zoom/Gmail/Meta/Duo OAuth, S3/export storage, ClamAV, rate limits, OTEL, etc. Cross-cutting groups (e.g. all DUO_*, all META_*, all S3_*) are only loosely related by prefix, and there is no secrets_dir support for Docker/Cloud Run mounted secrets — every secret must arrive via env/.env.
- **Proposed:** Introduce nested `BaseModel` groups (DbSettings, MetaSettings, DuoSettings, StorageSettings, ...) composed into Settings with `model_config = SettingsConfigDict(env_nested_delimiter='__', secrets_dir='/run/secrets', env_file='.env', extra='ignore')`. This makes the config self-documenting, lets each integration's config be passed around as one object, and enables loading secrets from mounted files (relevant for the GCP Cloud Run deployment). Note this changes env var names (e.g. DUO_CLIENT_ID -> DUO__CLIENT_ID) so .env.example and deployment manifests must be updated in the same change — acceptable under the project's no-backward-compat policy, but flag it as breaking for ops.
- **Doc:** pydantic-settings docs — nested models, env_nested_delimiter, secrets_dir (https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/config.py

#### 9. Emit serialization aliases on output (by_alias) so platform template schema_json round-trips correctly  
`[cleanup]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** apps/api/app/schemas/platform_templates.py defines `Field(alias='schema_json')` + `ConfigDict(populate_by_name=True)` on PlatformFormTemplateDraft/Update and FormTemplateLibraryDetail (89/92, 101/104, 143/144), so the alias is honored on INPUT only. No model_dump call anywhere uses `by_alias=True` (grep confirms zero), and platform.py serializes via attribute access (e.g. platform.py:2203 `schema_json=body.form_schema.model_dump()`), so the `schema_json` external key name is never produced symmetrically from these models.
- **Proposed:** Either (a) make the alias symmetric by calling `model_dump(by_alias=True)` wherever these template models are serialized to the persisted/API JSON shape, or (b) if the external name is purely an input convenience, drop the unused output expectation and document it. Pick one consistently so the field name contract is the same on read and write. If symmetric aliasing is wanted broadly, consider `ConfigDict(serialize_by_alias=True)` on those models so callers don't have to remember the flag.
- **Doc:** Pydantic docs — Serialization / by_alias & serialize_by_alias (https://pydantic.dev/docs/validation/latest/concepts/serialization/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/platform_templates.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/platform.py

### Python runtime / Alembic / async / packaging modernization (apps/api)

The backend is on current tooling (Python 3.11 floor, SQLAlchemy 2.0 typed ORM fully adopted, Alembic 1.18.3, uv with lockfile v1/rev3) but is leaving a meaningful set of post-3.11 features on the table — almost entirely because the runtime target is frozen at 3.11 even though the codebase already ships Python 3.14 forward-compat shims (slowapi/asyncio patch, protobuf pin). The highest-leverage wins are: (1) raise the runtime to 3.13 to unlock free-threading, JIT, faster startup/imports, and far better tracebacks for production debugging; (2) adopt asyncio.TaskGroup to supervise the worker's fan-out and the fire-and-forget websocket tasks that are currently un-tracked footguns; (3) parallelize the strictly-sequential job batch; (4) wake the worker via Postgres LISTEN/NOTIFY instead of fixed 10s polling to cut job latency. Packaging hygiene (PEP 735 dependency-groups, [tool.uv], .python-version, uv lock --locked in CI) and Alembic ergonomics (enable the new ruff module post-write hook, modernize script.py.mako typing) are genuine quick wins. PEP 695 generics/type aliases and typing.Self are real cleanups but are gated on first raising the floor to 3.12+. None of these compromise org-scoping, thin routers, or the human-review-before-send AI policy.

#### 1. Raise the runtime floor to Python 3.13 across pyproject/ruff/mypy/Docker/CI  
`[performance]` · impact=high · effort=medium · risk=medium · breaking=yes

- **Current:** Everything is pinned to 3.11: requires-python '>=3.11' (apps/api/pyproject.toml:5), ruff target-version='py311' (pyproject.toml:106), mypy python_version=3.11 (apps/api/mypy.ini:2), both Dockerfiles FROM python:3.11.14-slim-bookworm, and all 5 CI jobs python-version '3.11' (.github/workflows/ci.yml:45,100,156,226,316). Yet the code already carries 3.14 forward-compat shims (apps/api/app/core/rate_limit.py:16-17 patches the 3.14-deprecated asyncio.iscoroutinefunction; protobuf==6.33.5 is pinned 'to avoid deprecated PyType_Spec usage warnings in Python 3.14+', pyproject.toml:59-60) and uv.lock already resolves markers for 3.13/3.14 — so the intent to move forward exists but the target was never raised.
- **Proposed:** Move the floor to 3.13: requires-python '>=3.13', ruff target-version='py313', mypy python_version=3.13, Dockerfiles to python:3.13-slim-bookworm, CI matrix to '3.13'. This unlocks (vs 3.11): ~33% faster typing import + faster enum/functools/threading imports for quicker container cold-starts (relevant for Cloud Run scale-to-zero), much-improved colorized tracebacks and 'Did you mean' suggestions that show up directly in Cloud Logging for faster incident triage, the optional copy-and-patch JIT (PYTHON_JIT=1), and the free-threaded build (python3.13t) as a future option for the CPU-bound worker. It also makes PEP 695 generics/type aliases and typing.Self (separate items below) available. Do it as one floor bump rather than stair-stepping through 3.12.
- **Doc:** https://docs.python.org/3/whatsnew/3.13.html (import-time reductions, colorized tracebacks, PEP 744 JIT, PEP 703 free-threading); https://docs.python.org/3.12/whatsnew/3.12.html (per-interpreter GIL, comprehension inlining PEP 709, sys.monitoring PEP 669)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/pyproject.toml, /Users/chason/GenAI-assited-CRM-Tool/apps/api/mypy.ini, /Users/chason/GenAI-assited-CRM-Tool/apps/api/Dockerfile, /Users/chason/GenAI-assited-CRM-Tool/apps/api/Dockerfile.worker, /Users/chason/GenAI-assited-CRM-Tool/.github/workflows/ci.yml

#### 2. Supervise the worker's fire-and-forget and per-batch tasks with asyncio.TaskGroup  
`[architecture]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** asyncio.TaskGroup is unused anywhere (0 hits). The worker's fire-and-forget websocket pushes use bare asyncio.create_task whose handle is never retained or awaited (apps/api/app/services/notification_service.py:346-352 _spawn -> create_task(_runner); same pattern in apps/api/app/services/dashboard_service.py:515-526). The AI chat heartbeat and pub/sub listeners use bare create_task + asyncio.wait (apps/api/app/routers/ai_chat.py:207-220, apps/api/app/core/websocket.py:248,273). Un-retained tasks can be garbage-collected mid-flight and exceptions vanish silently.
- **Proposed:** Replace bare create_task + wait/gather with asyncio.TaskGroup (3.11+, with improved cancellation semantics in 3.13). TaskGroup retains strong references to child tasks (no GC mid-flight), propagates child failures as an ExceptionGroup, and cancels siblings on first error — exactly the supervision these un-tracked spawns lack. For genuinely detached websocket pushes, at minimum keep a module-level set of task references and add done-callbacks; for request-scoped fan-out (heartbeat + receive loops) wrap them in `async with asyncio.TaskGroup() as tg`.
- **Doc:** https://docs.python.org/3/library/asyncio-task.html#task-groups
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/notification_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/dashboard_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/ai_chat.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/websocket.py

#### 3. Parallelize the worker's job batch with bounded concurrency (TaskGroup + semaphore) and per-job sessions  
`[performance]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** process_job is awaited one job at a time in a for-loop (apps/api/app/worker.py:605-607) inside a single shared DB session opened per loop iteration (worker.py:562 `with SessionLocal() as db`). A batch of up to BATCH_SIZE=10 (worker.py:55) runs strictly sequentially, so one slow handler (e.g. a Meta API call or interview transcription) stalls the entire batch, and all jobs in the batch share one session with no isolation.
- **Proposed:** Process the claimed batch concurrently with asyncio.TaskGroup gated by an asyncio.Semaphore (e.g. WORKER_BATCH_CONCURRENCY, default 5), giving each job its own `with SessionLocal() as db` so a failure/rollback in one job can't corrupt another's unit of work. Heterogeneous I/O-bound handlers (Meta, Google, email, AI) benefit directly. Keep claim_pending_jobs as-is (SELECT ... FOR UPDATE SKIP LOCKED already makes concurrent claims safe, apps/api/app/services/job_service.py:108-109). This is the single biggest worker throughput win and is independent of switching to an external queue.
- **Doc:** https://docs.python.org/3/library/asyncio-task.html#task-groups
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/worker.py

#### 4. Wake the worker via Postgres LISTEN/NOTIFY instead of fixed-interval polling  
`[performance]` · impact=high · effort=high · risk=medium · breaking=no

- **Current:** The worker loop sleeps a fixed POLL_INTERVAL_SECONDS (default 10s) after each pass (apps/api/app/worker.py:561,664 `await asyncio.sleep(POLL_INTERVAL_SECONDS)`). Job latency is therefore bounded by the poll interval — an enqueued job (apps/api/app/services/job_service.py:13-43 enqueue_job) can wait up to ~10s before pickup even when the worker is idle. psycopg 3.3.2 (sync) is already the driver.
- **Proposed:** Have enqueue_job emit `NOTIFY jobs_channel` (or pg_notify) on commit, and have the worker LISTEN on that channel so it wakes immediately when work arrives, falling back to a longer safety poll (e.g. 30-60s) for scheduled/run_at-in-future jobs. psycopg 3 exposes connection.notifies() for consuming notifications. This cuts perceived latency for interactive paths (AI chat dispatch, ticket outbound send, exports) from up to 10s to sub-second while reducing idle DB query churn. Keep the existing claim path unchanged; NOTIFY is purely a wake signal.
- **Doc:** https://www.psycopg.org/psycopg3/docs/advanced/async.html#asynchronous-notifications ; https://www.postgresql.org/docs/current/sql-notify.html
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/worker.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/job_service.py

#### 5. Migrate test/dev deps to PEP 735 [dependency-groups] and add a [tool.uv] table  
`[dx]` · impact=medium · effort=low · risk=low · breaking=yes

- **Current:** Test dependencies live in legacy [project.optional-dependencies].test (apps/api/pyproject.toml:89-99) and are installed via `uv sync --frozen --extra test` everywhere (.github/workflows/ci.yml:54,109,165,325; Dockerfile). There is no [dependency-groups] table, no [tool.uv] table, and no default-groups config. The CLAUDE.md command reference still uses `uv sync --extra test`.
- **Proposed:** Move the test list into [dependency-groups] (PEP 735, fully supported by the installed uv) — e.g. `[dependency-groups]\ntest = ["pytest==9.0.3", ...]` — and install via `uv sync --group test`. dependency-groups are the modern, tool-agnostic standard for local-only dev deps (never published, unlike optional-dependencies which are user-facing extras). Add a [tool.uv] table for project-level uv config (e.g. default-groups) so contributors get the right env with a bare `uv sync`. Update CI run lines and the CLAUDE.md commands accordingly.
- **Doc:** https://docs.astral.sh/uv/concepts/projects/dependencies/ (Development dependencies / [dependency-groups], uv sync --group); PEP 735
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/pyproject.toml, /Users/chason/GenAI-assited-CRM-Tool/.github/workflows/ci.yml

#### 6. Verify lockfile freshness in CI with uv lock --locked  
`[dx]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** CI installs with `uv sync --frozen --extra test` (good — fails if the lock is out of sync with the environment) but never independently checks that uv.lock is up to date with pyproject.toml. There is no `uv lock --locked` / `--check` step (.github/workflows/ci.yml). A drifted-but-consistent lock can slip through.
- **Proposed:** Add a fast CI step `uv lock --locked` (errors if the lockfile would change) early in the api jobs, before sync. This guarantees uv.lock reflects pyproject.toml on every PR and catches a contributor who edited dependencies without re-locking — cheap insurance given the single-package layout.
- **Doc:** https://docs.astral.sh/uv/reference/cli/#uv-lock (--locked / --check); https://docs.astral.sh/uv/concepts/projects/sync/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/.github/workflows/ci.yml

#### 7. Add a pinned .python-version for reproducible local + CI interpreter selection  
`[dx]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** There is no .python-version at the repo root or in apps/api (verified absent). requires-python is a floor ('>=3.11'), so `uv run` / `uv python install` can pick any satisfying interpreter locally, which can diverge from the 3.11.14 used in Docker/CI.
- **Proposed:** Add apps/api/.python-version pinning the exact interpreter (matching whatever floor you land on — e.g. 3.13.x if you take the runtime-bump item, otherwise 3.11.14 to lock the current state). uv reads .python-version to auto-select and auto-install the interpreter, eliminating 'works on my machine' drift between contributors, Docker, and CI.
- **Doc:** https://docs.astral.sh/uv/concepts/python-versions/#project-python-versions (.python-version)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/.python-version

#### 8. Enable the Alembic ruff post-write hook and modernize script.py.mako typing  
`[dx]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** The [post_write_hooks] section in apps/api/alembic.ini is entirely commented out (lines 90-111), including the ruff 'module' runner example. As a result every freshly autogenerated migration is emitted unformatted and unlinted. The template apps/api/alembic/script.py.mako:8,16-18 still imports `from typing import Sequence, Union` and renders `down_revision: Union[str, Sequence[str], None]`, so every new migration reintroduces legacy typing.Union into a codebase that has otherwise eliminated typing.Union (0 hits) in favor of X|None.
- **Proposed:** Uncomment and enable the ruff 'module' post-write hook (`hooks = ruff` / `ruff.type = module` / `ruff.module = ruff` / `ruff.options = check --fix REVISION_SCRIPT_FILENAME`) — Alembic 1.18 added the module runner specifically for binary tools like ruff that lack a console_scripts entrypoint, and it finds the ruff available to the running interpreter. Optionally add a second `ruff format` hook. Separately, rewrite script.py.mako to use `from collections.abc import Sequence` and `str | Sequence[str] | None` so generated migrations stop reintroducing legacy typing. Together this keeps the 117-file versions/ directory consistently formatted going forward with zero manual cleanup.
- **Doc:** https://alembic.sqlalchemy.org/en/latest/changelog.html (1.18: 'module' post-write hook for tools like ruff); https://alembic.sqlalchemy.org/en/latest/autogenerate.html#applying-post-processing-and-python-code-formatters-to-generated-revisions
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic.ini, /Users/chason/GenAI-assited-CRM-Tool/apps/api/alembic/script.py.mako

#### 9. Replace asyncio.run() in sync request paths with the existing run_async() bridge  
`[cleanup]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** apps/api/app/services/platform_service.py calls asyncio.run() directly inside sync request paths at lines 548, 1221, 1323 (asyncio.run(invite_email_service.send_invite_email(...))). asyncio.run() creates and tears down a brand-new event loop on every call, which is wasteful and can conflict with FastAPI's running loop. The project already has a purpose-built bridge, apps/api/app/core/async_utils.py run_async(), which uses anyio.from_thread.run on the request loop and guards against being called from an async context.
- **Proposed:** Route these three calls through run_async() (or, better, make the surrounding endpoints async and `await` directly). This removes redundant event-loop construction, reuses the request's loop, and centralizes the sync/async boundary in one audited place instead of three ad-hoc asyncio.run() calls. Low risk and improves consistency with the rest of the codebase.
- **Doc:** https://docs.python.org/3/library/asyncio-runner.html#asyncio.run (note: 'should be used as a main entry point ... should ideally only be called once'); internal apps/api/app/core/async_utils.py
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/platform_service.py

#### 10. Adopt PEP 695 type aliases / native generics and typing.Self (after raising to 3.12+)  
`[cleanup]` · impact=low · effort=medium · risk=low · breaking=no

- **Current:** Type aliases and generics use pre-3.12 forms: JobHandler = Callable[...] (apps/api/app/jobs/registry.py:30), PaginatedResponse(Generic[T]) with a module-level TypeVar and a string forward-ref return `-> 'PaginatedResponse[T]'` on the classmethod (apps/api/app/utils/pagination.py:4,10,51,63), and run_async uses typing.TypeVar (apps/api/app/core/async_utils.py:4,8). typing.Self is unused. PEP 695 'type X =' and 'class Foo[T]' are absent (0 hits).
- **Proposed:** Once the floor is 3.12+ (depends on the runtime-bump item), convert to PEP 695: `type JobHandler = Callable[[object, object], Awaitable[None]]`, `class PaginatedResponse[T]`, `def run_async[T](...)`, and change pagination's classmethod return to `-> Self` (typing.Self is actually available on 3.11 already, so the Self change can land independently). This removes module-level TypeVar boilerplate and the brittle string forward-ref, and is exactly the modern typing style the codebase is already trending toward (typing.Union already at 0). Pure readability/maintainability; no runtime behavior change.
- **Doc:** https://docs.python.org/3.12/whatsnew/3.12.html#pep-695-type-parameter-syntax ; https://docs.python.org/3/library/typing.html#typing.Self
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/jobs/registry.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/utils/pagination.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/async_utils.py

#### 11. Finish the typing modernization: eliminate residual typing.Optional and uppercase Dict/List/Set  
`[cleanup]` · impact=low · effort=low · risk=low · breaking=no

- **Current:** Despite the modern X|None style dominating, 118 typing.Optional[ uses remain across dozens of files (e.g. routers/ops.py, routers/analytics.py, core/csrf.py, services/notification_service.py) plus 11 uppercase Dict/List/Tuple/Set[ uses in core/websocket.py, services/duo_service.py, services/mfa_service.py. This is inconsistent with the prevailing X|None / lowercase-builtin convention.
- **Proposed:** Run ruff's pyupgrade rules (UP006/UP007/UP045) with --fix to mechanically rewrite Optional[X] -> X | None and Dict/List/Set -> dict/list/set, then drop the now-unused typing imports. Add the UP rule group to [tool.ruff.lint] so new violations are blocked in CI. This is a pure, low-risk consistency cleanup and is fully supported on the current 3.11 floor (no version bump required).
- **Doc:** https://docs.astral.sh/ruff/rules/#pyupgrade-up (UP006 non-pep585-annotation, UP007/UP045 non-pep604-annotation-optional)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app, /Users/chason/GenAI-assited-CRM-Tool/apps/api/pyproject.toml

### Observability / security / platform deps modernization (OpenTelemetry 1.39, Sentry 2.51, slowapi+redis 7.1, cryptography 46, boto3, secrets) — FastAPI backend

This backend already pins fully current observability/security deps, but it uses very little of what those versions unlock. The headline gaps: OpenTelemetry 1.39 ships OTLP logs and metrics (LoggerProvider + LoggingHandler bridge, MeterProvider + PeriodicExportingMetricReader) and the SDK's standard OTEL_* env auto-config, yet telemetry.py is traces-only, is hard-disabled in prod (no OTEL_* vars wired into Cloud Run), uses the deprecated deployment.environment semconv key, omits service.version, and hand-parses headers/trace IDs instead of reading the active span. Sentry 2.51 supports structured Logs (enable_logs + before_send_log), continuous profiling, RedisIntegration, traces_sampler, release/dist tagging and before_send PII scrubbing — none are used, and Sentry duplicates a parallel GCP Error Reporting path (three overlapping error stacks with the modern one disabled). cryptography 46 offers MultiFernet for zero-downtime data-key rotation (the JWT path already rotates, the Fernet data/meta keys do not). redis 7.1 offers a real Retry/backoff policy object and RESP3, but the three ad-hoc pools only set retry_on_timeout=True. slowapi 0.1.9 needed a Python 3.14 monkeypatch and uses sync redis on async routes. The highest-value moves are: (1) make OTel actually run in prod and add logs+metrics so the hand-rolled Postgres request-metrics path and the parallel GCP stack can be retired, (2) modernize Sentry 2.x config (release/profiling/before_send/RedisIntegration or consolidate onto OTel), (3) MultiFernet key rotation for PII-at-rest, (4) tighten the Redis retry policy. Breaking changes are acceptable per project policy; most items below are additive.

#### 1. Wire OpenTelemetry into Cloud Run so tracing actually runs in production  
`[architecture]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** configure_telemetry() (apps/api/app/core/telemetry.py:37-67) is gated on settings.OTEL_ENABLED (default False, config.py:265) plus OTEL_EXPORTER_OTLP_ENDPOINT, but NO OTEL_* env vars are present in infra/terraform/locals.tf (common_env/api_env 26-67) or cloudrun.tf, and grep for OTEL across infra/ returns nothing. The tracing code path almost certainly never executes in prod; all telemetry runs through the parallel GCP Cloud Logging + Error Reporting stack (gcp_monitoring.py) and a hand-rolled Postgres metrics writer (main.py:297-313).
- **Proposed:** Decide whether OTel is the observability strategy. If yes: add OTEL_ENABLED=true and OTEL_EXPORTER_OTLP_ENDPOINT (Cloud Trace OTLP endpoint or a collector) to the Cloud Run env in infra/terraform/locals.tf + cloudrun.tf, and prefer the SDK's native OTEL_EXPORTER_OTLP_* / OTEL_RESOURCE_ATTRIBUTES / OTEL_SERVICE_NAME env auto-configuration instead of the hand-written settings + _parse_headers (telemetry.py:24-34). If OTel is not the strategy, delete telemetry.py and its deps to remove dead code and a third overlapping path. Half-configured-but-disabled is the worst state.
- **Doc:** OpenTelemetry Python — Instrumentation / OTLP exporter env-var configuration (https://opentelemetry.io/docs/languages/python/instrumentation/ and https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/)
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/infra/terraform/locals.tf, /Users/chason/GenAI-assited-CRM-Tool/infra/terraform/cloudrun.tf, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/telemetry.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/config.py

#### 2. Adopt OTLP metrics (MeterProvider) and retire the hand-rolled Postgres request-metrics writer  
`[feature-adoption]` · impact=high · effort=high · risk=medium · breaking=yes

- **Current:** Every request opens a fresh SessionLocal() and writes request metrics into Postgres via metrics_service.record_request (main.py:297-313, metrics_middleware 406-426) — a per-request DB write/connection on the hot path. The installed opentelemetry-sdk 1.39.1 + opentelemetry-exporter-otlp 1.39.1 (pyproject.toml:52-53) fully support OTLP metrics, but there is zero MeterProvider/metrics usage anywhere.
- **Proposed:** Configure a MeterProvider with PeriodicExportingMetricReader + OTLPMetricExporter in telemetry.py, and record request count/latency/status as OTel counters+histograms (or rely on opentelemetry-instrumentation-fastapi's built-in HTTP metrics) instead of synchronous Postgres writes. This removes a per-request DB connection from the hot path and unifies metrics with traces. Keep any org-scoped business metrics that genuinely need to be queried in-app, but move pure ops metrics to OTLP.
- **Doc:** OpenTelemetry Python — Metrics SDK (MeterProvider, PeriodicExportingMetricReader): https://opentelemetry.io/docs/languages/python/instrumentation/#metrics and https://opentelemetry-python.readthedocs.io/en/stable/sdk/metrics.html
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/telemetry.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/metrics_service.py

#### 3. Bridge stdlib logging into OTLP logs via LoggingHandler instead of the GCP-only handler  
`[feature-adoption]` · impact=high · effort=medium · risk=medium · breaking=no

- **Current:** Structured logs (structured_logging.py) are emitted via the 'app.ops' stdlib logger with extra={'json_fields': ...} (185-193) and only materialize as JSON when google-cloud-logging's handler is installed (gcp_monitoring.py:91). There is no LoggerProvider/LoggingHandler and no logging.dictConfig — outside GCP (local dev, CI, alternate hosts) the json_fields extra is silently dropped to plain text. The OTel 1.39 logs SDK is installed but unused.
- **Proposed:** Add a LoggerProvider + BatchLogRecordProcessor + OTLPLogExporter and attach opentelemetry.sdk._logs.LoggingHandler to the app loggers (or root) in telemetry.py, so application logs flow as OTLP logs with automatic trace correlation. This makes logs portable off GCP and consolidates the third (logging) signal with traces/metrics. Pairs naturally with the trace-context fix below.
- **Doc:** OpenTelemetry Python SDK _logs (LoggerProvider, BatchLogRecordProcessor, LoggingHandler, set_logger_provider): https://opentelemetry-python.readthedocs.io/en/stable/sdk/_logs.html
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/telemetry.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/structured_logging.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py

#### 4. Correlate logs with OTel trace IDs by reading the active span instead of re-parsing headers  
`[feature-adoption]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** extract_trace_id() (structured_logging.py:55-69) hand-parses X-Cloud-Trace-Context / W3C traceparent headers. When OTel is enabled it generates its own trace IDs from the active span, so OTel spans and the trace_id stamped on logs will NOT match, breaking trace<->log correlation. gcp_monitoring._build_request_id (gcp_monitoring.py:58-66) has the same header-only approach.
- **Proposed:** When a span is active, read trace/span IDs from opentelemetry.trace.get_current_span().get_span_context() (format trace_id as 32-hex, span_id as 16-hex) and use those in build_request_log_context (structured_logging.py:151-182), falling back to the header parser only when no span is active. GCP Cloud Logging auto-populates trace/spanId/trace_sampled from the active OTel context, giving real end-to-end correlation.
- **Doc:** Google Cloud — Link log entries with traces / OpenTelemetry span context auto-population: https://cloud.google.com/trace/docs/trace-log-integration ; OTel API trace.get_current_span().get_span_context()
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/structured_logging.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/gcp_monitoring.py

#### 5. Fix OTel Resource attributes: add service.version, drop deprecated deployment.environment key  
`[feature-adoption]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** Resource.create only sets SERVICE_NAME and ResourceAttributes.DEPLOYMENT_ENVIRONMENT (telemetry.py:43-50). DEPLOYMENT_ENVIRONMENT is the deprecated semconv key (modern semconv is deployment.environment.name). service.version is omitted even though settings.VERSION exists (config.py:94) and is already passed to GCP Error Reporting (gcp_monitoring.py:100). No service.instance.id.
- **Proposed:** Add service.version=settings.VERSION and a service.instance.id (e.g. Cloud Run revision / hostname), and emit deployment.environment.name (or set them all via OTEL_RESOURCE_ATTRIBUTES). This unlocks per-release filtering and regression attribution in any OTLP backend and aligns with current semantic conventions.
- **Doc:** OpenTelemetry Semantic Conventions — Resource service.* and deployment.environment.name: https://opentelemetry.io/docs/specs/semconv/resource/#service and https://opentelemetry.io/docs/specs/semconv/resource/deployment-environment/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/telemetry.py

#### 6. Add custom spans around business-critical flows (AI generation, email send, Meta sync, exports, webhooks)  
`[feature-adoption]` · impact=medium · effort=medium · risk=low · breaking=no

- **Current:** There is zero manual instrumentation: no get_tracer/start_as_current_span/set_attribute/add_event anywhere in apps/api/app (grep confirmed). Business-critical, multi-step async flows produce only auto-instrumented HTTP/DB spans, so latency in AI generation, outbound email, Meta sync, PDF export, and webhook processing is invisible at the operation level.
- **Proposed:** Create a tracer (trace.get_tracer(__name__)) and wrap the key service operations in start_as_current_span with org_id/entity-type attributes (never raw PII — reuse the SHA-256 email hashing already in structured_logging.hash_email_for_log). This gives actionable latency breakdowns for the slowest, most failure-prone paths. Respect org-scoping: tag spans with org_id, not patient/surrogate PII.
- **Doc:** OpenTelemetry Python — Creating spans / manual instrumentation: https://opentelemetry.io/docs/languages/python/instrumentation/#creating-spans
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/ai_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/email_service.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/webhooks.py

#### 7. Consolidate error reporting: pick Sentry OR GCP Error Reporting, not both  
`[architecture]` · impact=high · effort=medium · risk=medium · breaking=yes

- **Current:** Two error paths run in parallel. Sentry is init'd inline (main.py:176-191) when SENTRY_DSN is set and ENV!='dev'. Independently, gcp_error_reporting_middleware (main.py:237-294) calls report_exception() into GCP Error Reporting (gcp_monitoring.py:111-135) for 5xx/unhandled. Both can fire for the same exception, producing duplicate/inconsistent reports, and config.py:347-350 treats them as interchangeable. There is no manual capture_exception/set_user/set_tag/add_breadcrumb anywhere (grep confirmed — only unrelated set_user_override).
- **Proposed:** Choose one as the source of truth. Given Sentry 2.x's FastAPI/SQLAlchemy integrations + profiling + logs, standardize on Sentry and remove the GCP Error Reporting middleware path (keep GCP Cloud Logging if desired), OR keep GCP and drop Sentry. Whichever stays, add sentry_sdk.set_user (hashed id + org_id) and set_tag('org_id', ...) in the auth middleware so errors are attributable per-tenant.
- **Doc:** Sentry Python — FastAPI integration & scope/set_user/set_tag: https://docs.sentry.io/platforms/python/integrations/fastapi/ and https://docs.sentry.io/platforms/python/enriching-events/identify-user/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/gcp_monitoring.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/config.py

#### 8. Add Sentry release tagging + before_send PII scrubber for this PHI-handling app  
`[security]` · impact=high · effort=low · risk=low · breaking=no

- **Current:** sentry_sdk.init (main.py:181-190) sets only dsn/environment/integrations/traces_sample_rate=0.1/send_default_pii=False. It does NOT pass release/dist (settings.VERSION is available and already used elsewhere), and has no before_send hook. For an app handling surrogacy PHI, send_default_pii=False alone does not scrub application-level PII captured in exception messages, local variables, breadcrumbs, or request bodies.
- **Proposed:** Pass release=settings.VERSION (enables regression detection + suspect-commit linking) and add a before_send callback that strips known PHI fields (emails, phones, names, DOB, addresses) from event.request, exception values, and extra/breadcrumbs — reusing the existing PHI-safe allowlist concept from structured_logging.SAFE_PATH_ENTITY_ID_KEYS. This is a meaningful HIPAA-posture improvement, not just a nicety.
- **Doc:** Sentry Python — Releases (release option) https://docs.sentry.io/platforms/python/configuration/releases/ and Filtering / before_send https://docs.sentry.io/platforms/python/configuration/filtering/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py

#### 9. Enable Sentry continuous profiling and a traces_sampler (if standardizing on Sentry)  
`[performance]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** Sentry config (main.py:181-190) uses a flat traces_sample_rate=0.1 with no profiling. Sentry 2.x exposes profiles_sample_rate / profile_session_sample_rate (continuous profiling) and a traces_sampler callback for per-route sampling — none are configured, so there is no code-level profiling of slow endpoints and high-traffic health/webhook routes are sampled at the same rate as rare critical flows.
- **Proposed:** Add profiles_sample_rate (or continuous profiling via profile_session_sample_rate + start_profiler) to capture function-level flame graphs on slow AI/export/PDF endpoints, and replace the flat traces_sample_rate with a traces_sampler that lowers sampling on noisy routes (health, metrics, webhooks) and raises it on auth/AI/export. Only pursue if Sentry is the chosen stack (see consolidation item).
- **Doc:** Sentry Python — Profiling (profiles_sample_rate / continuous): https://docs.sentry.io/platforms/python/profiling/ and Sampling (traces_sampler): https://docs.sentry.io/platforms/python/configuration/sampling/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py

#### 10. Use MultiFernet for zero-downtime rotation of DATA_ENCRYPTION_KEY / META_ENCRYPTION_KEY  
`[security]` · impact=high · effort=medium · risk=low · breaking=no

- **Current:** encryption.py uses a single Fernet per key (get_fernet 17-27, get_data_fernet 30-40). There is no rotation: changing DATA_ENCRYPTION_KEY would make all existing 'enc:'-prefixed PII (encryption.py:14,60-84) undecryptable, forcing a full re-encrypt. This contrasts with the JWT path which DOES support rotation via jwt_secrets=[JWT_SECRET, JWT_SECRET_PREVIOUS] (security.py:105-111, config.py:490-493).
- **Proposed:** Wrap the data and meta keys in cryptography.fernet.MultiFernet built from [CURRENT_KEY, PREVIOUS_KEY] (add *_KEY_PREVIOUS settings mirroring JWT_SECRET_PREVIOUS). New writes use the first key; reads try all keys; MultiFernet.rotate() can lazily re-encrypt records. This brings PII-at-rest to the same zero-downtime rotation maturity the JWT layer already has — important for a HIPAA-style key-rotation policy.
- **Doc:** cryptography — Fernet key rotation via MultiFernet / MultiFernet.rotate(): https://cryptography.io/en/stable/fernet/#cryptography.fernet.MultiFernet
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/encryption.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/config.py

#### 11. Configure an explicit Redis Retry/backoff policy across all pools  
`[performance]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** All three pools in redis_client.py (sync 43-51, async 64-72, pubsub 85-93) are built with from_url(..., retry_on_timeout=True) but no Retry object, so there is no real backoff strategy or retry on transient connection errors — retry_on_timeout alone is a coarse, legacy knob. redis 7.1 supports a structured Retry policy with backoff (ExponentialBackoff) and a configurable retryable-error set.
- **Proposed:** Pass retry=Retry(ExponentialBackoff(), retries=N) and retry_on_error=[ConnectionError, TimeoutError] (or set the modern retry_on_timeout + retry together) when building each pool. This hardens the rate limiter, WebSocket pub/sub, and session-revocation listeners against transient Redis blips — directly relevant since the FailOpenLimiter (rate_limit.py:38-101) currently absorbs these failures by degrading to in-memory limiting.
- **Doc:** redis-py — Retry / Backoff and connection resilience: https://redis.readthedocs.io/en/stable/retry.html and https://redis.io/docs/latest/develop/clients/redis-py/produsage/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/redis_client.py

#### 12. Replace slowapi+FailOpenLimiter with the 'limits' library directly using async Redis storage  
`[architecture]` · impact=medium · effort=high · risk=medium · breaking=yes

- **Current:** Rate limiting uses slowapi 0.1.9, which required a Python 3.14 monkeypatch (rate_limit.py:17 patches slowapi_extension.asyncio.iscoroutinefunction) and uses sync redis storage even on async routes. The custom FailOpenLimiter (rate_limit.py:38-101) re-implements per-call resilience that the underlying 'limits' library handles natively, and ~21 routers depend on @limiter.limit decorators.
- **Proposed:** Migrate to the 'limits' library (which slowapi already wraps) directly, using its async Redis storage ('async+redis://') and the moving-window strategy via a small FastAPI dependency/middleware. This drops the monkeypatch, makes rate-limit storage truly async on async routes, and lets you delete the FailOpenLimiter wrapper in favor of limits' native storage error handling. Large but removes an unmaintained-shim dependency; sequence it after the higher-impact observability work.
- **Doc:** limits library — async storage & strategies: https://limits.readthedocs.io/en/stable/ ; slowapi/limits relationship: https://slowapi.readthedocs.io/
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/rate_limit.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers

#### 13. Remove DEFAULT_JWT_SECRET / DEFAULT_DEV_SECRET fallbacks to eliminate the placeholder-secret foot-gun  
`[security]` · impact=medium · effort=low · risk=medium · breaking=yes

- **Current:** config.py defines DEFAULT_JWT_SECRET='change-this-in-production' and DEFAULT_DEV_SECRET='change-me' (config.py:12-13) and silently assigns JWT_SECRET=DEFAULT_JWT_SECRET when unset (config.py:278-279). It is guarded for non-dev (validation rejects it at config.py:307-308), but the placeholder still exists at runtime in dev/test and is a classic accidental-promotion risk. Secrets are otherwise injected as plain Cloud Run env vars from Secret Manager (locals.tf:69-94) with no runtime Secret Manager access.
- **Proposed:** Drop the hardcoded placeholder secrets; require JWT_SECRET (and dev secret) to be explicitly set in every environment including dev/test (generate per-developer/per-CI ephemeral values). Optionally add a runtime google-cloud-secret-manager fetch with caching as a cleaner alternative to baking secrets into env vars, enabling rotation without redeploy. This removes a known foot-gun and tightens the secret surface.
- **Doc:** Google Cloud Secret Manager — access secret versions / caching guidance: https://cloud.google.com/secret-manager/docs/access-control and https://cloud.google.com/secret-manager/docs/best-practices
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/config.py

#### 14. Add a logging.dictConfig JSON formatter for non-GCP runtimes  
`[dx]` · impact=medium · effort=low · risk=low · breaking=no

- **Current:** JSON log structure depends entirely on google-cloud-logging's handler picking up the json_fields extra (gcp_monitoring.py:91; structured_logging.py:188-193). There is no logging.dictConfig and no standalone JSON formatter (only logging.basicConfig in worker.py:46, clamav_update.py, scan_job_runner.py). Outside GCP — local dev, CI, alternate hosts — the rich json_fields context is dropped and logs are plain text, so the carefully-built PHI-safe context is invisible where engineers debug most.
- **Proposed:** Add a logging.dictConfig (or a small JSON formatter) installed at startup that serializes the json_fields/extra context to JSON when the GCP handler is not active. This makes structured logs available everywhere and gives consistent, greppable output in dev/CI — a genuine quick win that complements the OTLP-logs item.
- **Doc:** Python logging.config.dictConfig: https://docs.python.org/3/library/logging.config.html#logging.config.dictConfig
- **Where:** /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/structured_logging.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/main.py, /Users/chason/GenAI-assited-CRM-Tool/apps/api/app/worker.py
