# Surrogacy Force Platform

Multi-tenant operations platform for surrogacy agencies. This root guide contains durable invariants and routing. Inspect live code, tests, manifests, and nested guidance before changing an unfamiliar surface.

## Priorities

1. Follow the user's requested outcome and scope.
2. Preserve the safety, tenant-isolation, approval, and data-integrity invariants below.
3. Match surrounding code and verify behavior in proportion to risk.

## Working with unknowns

For routine, reversible, well-scoped work, inspect the local surface and proceed with best judgment.

Before unfamiliar, cross-cutting, security-sensitive, preference-heavy, or irreversible work, do a blind-spot pass over callers, tests, data, operations, and prior patterns. Surface only choices that would materially change architecture, user experience, security, data migration, external effects, or task scope.

Use a cheap prototype or artifact when the user can recognize the right answer more easily than describe it. If implementation reveals a material deviation, choose the conservative reversible path when possible, record the decision, and report it. Ask before crossing an authorization or irreversibility boundary.

## Non-negotiables

- Never commit or expose secrets; never log raw PII.
- Never send AI-authored messages without human review.
- Every tenant-owned read, write, relationship traversal, export, job, and cache key derives organization scope from authenticated membership—not a client-supplied organization id. New access paths need a cross-org negative test. Platform-global entities must be explicit.
- Use centralized membership, role, and CSRF dependencies. Cookie-authenticated mutations keep the repository's CSRF contract; browser API calls preserve credentials.
- Never merge, release, deploy, send externally, or irreversibly transform production data without explicit authorization.

## Quality boundary

Do not introduce warnings, test failures, security regressions, or obvious performance regressions. Report unrelated pre-existing issues; fix them only when requested, blocking verification, or inseparable from the change.

This is an internal product: do not preserve legacy behavior by default. Before a breaking API, data, or workflow change, surface its impact and migration/reset plan. Match completeness to the requested artifact. Production features include relevant loading, error, validation, and polish; prototypes must be isolated and clearly labeled. Preserve existing semantic and keyboard behavior; treat broader accessibility work as separate scope unless requested.

## Architecture and local gotchas

- Keep FastAPI routers thin. Services own use-case logic and transaction boundaries. Use timezone-aware UTC.
- TanStack Query owns server state; Zustand owns UI-only state.
- Extend the customized shadcn/Base UI primitives; do not replace the component system in a focused feature change.
- Shared Base UI `SelectValue` may expose a stored id, enum, slug, or sentinel. Map it through one label helper everywhere it appears—triggers, chips, badges, summaries, and empty states. When one filter leaks a raw value, audit siblings and test the trigger plus related labels.
- Pipeline stages are configurable. Treat `apps/api/app/core/stage_definitions.py` and pipeline services as the source of truth; keep generated frontend constants synchronized. Trace API, automation, analytics, and frontend consumers when stage semantics change.
- Prefer nearby production code and behavior tests as references. Match local naming, comment density, transaction ownership, errors, and composition.

## Verification

For a reported bug, first add or identify a failing regression test. Then implement the smallest fix and prove it passes. Update tests with behavior changes.

Run validation proportionate to blast radius:

- Localized: focused regression plus relevant lint/type checks.
- Cross-cutting: full affected suites.
- Migration, auth, tenancy, or release: invariant and negative tests.

Use parallel agents only when independent work is useful and supported; they are not part of the product invariant.

## Commands and routing

Use repo-pinned runtimes in `mise.toml` and `mise.lock`, plus existing package scripts. Inspect manifests before adding commands.

- Backend setup/test: `cd apps/api && uv sync --extra test`, then `cd apps/api && uv run -m pytest -v`.
- Frontend validation: `cd apps/web && pnpm run check`; use `pnpm run test:all` for cross-cutting or integration changes.
- Migrations and recovery: `docs/migration-runbook.md`.
- Runtime versions: `mise.toml`; dependencies: manifests under `apps/`.
- Environment contract: `apps/api/.env.example`; never put secrets in `NEXT_PUBLIC_*`.
- Release policy: `release-please-config.json` and release CI tests; do not edit versions manually unless that workflow requires it.
- Backend-specific guidance: `apps/api/AGENTS.md`.
- Frontend-specific guidance: `apps/web/AGENTS.md`. For Next.js work, search `.next-docs` and read only the relevant local documentation before coding.

## Delivery and cleanup

Do not create a branch, commit, push, or PR unless the user requests it. Work on the current branch unless told otherwise. Before a requested commit, inspect staged files, include only task-owned work, run appropriate validation, and use `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, or `chore:`.

Start local servers only for active QA. Record their PIDs, stop only processes started for this task, verify they exited, remove temporary QA artifacts, and report any service intentionally left running.
