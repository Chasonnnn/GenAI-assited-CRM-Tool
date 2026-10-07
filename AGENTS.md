# Surrogacy Force Platform

Multi-tenant operations platform for surrogacy agencies. This is the repository's only agent instruction file; root `CLAUDE.md` symlinks here. Inspect relevant live code, tests, and manifests before changing an unfamiliar surface.

## Priorities

1. Follow the user's requested outcome and scope.
2. Preserve the safety, tenant-isolation, approval, and data-integrity invariants below.
3. Match surrounding code and verify behavior in proportion to risk.

## Working with unknowns

For routine, reversible, well-scoped work, inspect the local surface and proceed with best judgment.

Before unfamiliar, cross-cutting, security-sensitive, preference-heavy, or irreversible work, do a blind-spot pass over callers, tests, data, operations, and prior patterns. Surface only choices that would materially change architecture, user experience, security, data migration, external effects, or task scope.

Use a cheap prototype or artifact when the user can recognize the right answer more easily than describe it. If implementation reveals a material deviation, choose the conservative reversible path when possible, record the decision, and report it. Ask before crossing an authorization or irreversibility boundary.

## Non-negotiables

- Never commit or expose secrets; never log raw PII, message bodies, provider credentials, or tokens. Keep provider failures sanitized at the API boundary.
- Never send AI-authored messages without human review.
- Every tenant-owned read, write, relationship traversal, export, job, and cache key derives organization scope from authenticated membership—not a client-supplied organization id. New access paths need a cross-org negative test. Platform-global entities must be explicit.
- Public token flows derive scope from the validated token or its bound resource, never from a client-supplied organization id.
- Use centralized membership, role, and CSRF dependencies. Cookie-authenticated mutations keep the repository's CSRF contract; browser API calls preserve credentials.
- Never merge, release, deploy, send externally, or irreversibly transform production data without explicit authorization.

## Quality boundary

Do not introduce warnings, test failures, security regressions, or obvious performance regressions. Report unrelated pre-existing issues; fix them only when requested, blocking verification, or inseparable from the change.

Review severity, the bot-review stop rule, and the backend/frontend judgement calls: `docs/review-standards.md`.

## Local gotchas

- Pipeline stages are configurable. `apps/api/app/core/stage_definitions.py` and the pipeline services are the source of truth; trace API, automation, analytics, and frontend consumers when stage semantics change.
- When backend stage or surrogate contracts change, run the existing generators and commit the synchronized frontend outputs in the same change. Do not hand-edit generated files such as `apps/web/lib/constants/stages.generated.ts`.

## Migrations

- Use Alembic revision ids and filenames in `YYYYMMDD_HHMM_<slug>` form.
- Inspect generated migrations before running them. Cover upgrade behavior and schema invariants in tests.
- Do not perform a baseline reset as part of an ordinary schema change. Ask before recovery, consolidation, or baseline work.

## Verification

For a reported bug, first add or identify a failing regression test. Then implement the smallest fix and prove it passes. Update tests with behavior changes.

Run validation proportionate to blast radius:

- Localized: focused regression plus relevant lint/type checks.
- Cross-cutting: full affected suites.
- Migration, auth, tenancy, or release: invariant and negative tests.

Run Ruff for changed Python surfaces. Add denied and cross-organization tests for new protected operations, plus CSRF, idempotency, and retry tests when relevant.

For UI changes, verify the rendered states that changed, including loading, empty, error, and populated states when applicable.

Run `apps/api/scripts/ci_gates.sh` for the database-free backend gates (FastAPI conventions, one Alembic head, Ruff). Run `git config core.hooksPath .githooks` once per checkout so pre-push runs it.

## Commands and routing

Use repo-pinned runtimes in `mise.toml` and `mise.lock`, plus existing package scripts. Inspect manifests before adding commands.

- Backend verification: start local PostgreSQL only when needed, then use `apps/api/run_tests.sh <pytest args>` from the repo root. It selects pinned runtimes and creates, migrates, and drops a unique local database per invocation. Omit arguments for the full serial suite. Use direct `mise exec -- uv run -m pytest` only against an explicitly configured, migrated disposable database; never inherited shared data. See README for setup and `.github/workflows/ci.yml` for the parallel-safe test split.
- Frontend validation: focused Vitest files while iterating; `cd apps/web && mise exec -- pnpm run check` runs type checking, lint, and the test suite. `test:all` aliases the same test command and adds no coverage after `check`.
- Browser end-to-end tests (local pilot, not in CI): `cd apps/web && mise exec -- pnpm run test:e2e`; see `apps/web/README.md`. Before writing or changing one, read `mise exec -- pnpm exec e2e guide` and its `writing-tests` topic. The `e2e` MCP server in `.mcp.json` opens a live session on the disposable stack for checking locators.
- Runtime versions: `mise.toml`; dependencies: manifests under `apps/`.
- Environment contract: `apps/api/.env.example`; never put secrets in `NEXT_PUBLIC_*`.
- Release policy: `release-please-config.json` and release CI tests; do not edit versions manually unless that workflow requires it.
- For Next.js routing, rendering, caching, framework API, or upgrade work, read the relevant version-matched guide in `apps/web/node_modules/next/dist/docs/`. Read only what the change requires. Keep `agentRules: false` in `apps/web/next.config.js` so Next.js does not generate nested instruction files.

## Delivery and cleanup

After completing each task, always commit the changes in small logical groups. Before each commit, inspect staged files, include only task-owned work, run appropriate validation, and use `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, or `chore:`. Do not create a branch, push, or open a PR unless the user requests it. Work on the current branch unless told otherwise.

Start local servers only for active QA; start Postgres or workers only when verification needs them. Record their PIDs, stop only processes started for this task, verify they exited, remove temporary QA artifacts, and report any service intentionally left running.
