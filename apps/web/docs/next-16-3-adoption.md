# Next.js 16.3 adoption

Next.js and `@next/bundle-analyzer` are pinned to 16.3.7. React remains on 19.2.7. TypeScript uses the supported split toolchain described below.

## Package maturation gate

The repository's 24-hour `minimumReleaseAge` policy accepts the frozen 16.3.0 lockfile as of 2026-08-06. A clean CI-equivalent Linux image build completed with the policy intact. Do not add a package-age exclusion or bypass the policy in CI.

The 2026-10-01 dependency audit validated 16.3.7 with the full frontend check, Webpack build and Linux amd64 standalone image. Next 16.3.8 clears the same policy at 2026-10-01 12:07:21 EDT and remains a security follow-up; see the [dependency audit](../../../output/dependency-modernization-20260930/audit.md).

## Production defaults

The production-safe profile keeps all three experimental adoption switches off:

- `NEXT_ENABLE_INSTANT_NAVIGATIONS`
- `NEXT_EXPERIMENTAL_OFFLINE_RETRY`
- `NEXT_EXPERIMENTAL_RUST_REACT_COMPILER`

Do not enable in production until the corresponding gate below passes. These are build-time switches, so changing one requires a new web image.

## Production bundler boundary

Production builds use the documented Webpack fallback through `next build --webpack`; development continues to use Turbopack. The stable React Compiler remains enabled.

The minimized Next 16.3 reproduction, `next build --debug-build-paths=app/health/route.ts`, stalls in Turbopack with `reactCompiler: true` but advances to the font-fetch boundary when either Webpack is selected or the React Compiler is disabled. Keep the Webpack production boundary until that interaction is resolved and the same Turbopack repro completes.

Trade-off: production compilation does not receive Turbopack's build-speed improvements, but the application retains React Compiler optimizations and a deterministic production build. Do not remove `--webpack` based only on a successful development server run.

## Instant Navigations and Cache Components

Use `NEXT_ENABLE_INSTANT_NAVIGATIONS=true` only in an isolated build. It enables Cache Components and Partial Prefetching together.

The first full production-prerender audit found 17 production-prerender blockers:

- `/intended-parents/[id]`
- `/settings/integrations/meta/forms/[id]`
- `/surrogates/[id]`
- `/surrogates/[id]/ai`
- `/surrogates/[id]/application`
- `/surrogates/[id]/emails`
- `/surrogates/[id]/history`
- `/surrogates/[id]/interviews`
- `/surrogates/[id]/journey`
- `/surrogates/[id]/notes`
- `/surrogates/[id]/profile`
- `/surrogates/[id]/tasks`
- `/tickets/[ticketId]`
- `/book/preview`
- `/book/self-service/[orgId]/manage/[token]`
- `/invite/[id]`
- `/ops/agencies/[orgId]`

The first route-family preparation covers `/intended-parents/[id]`. Its generic loading shell contains no tenant-derived data. Authenticated browser QA verified that the owning tenant can navigate to a real intended-parent record while a second tenant receives `404` for the record and all related endpoints.

This route is not ready to activate in production. Next rejects an `instant` route export while Cache Components is disabled, so the activation flag is intentionally not committed. The shared authenticated layout still exports `dynamic = "force-dynamic"` and `revalidate = 0`, which are incompatible with Cache Components. After removing those global blockers, the opt-in Webpack build also fails inside Next 16.3 because `React.unstable_postpone` is unavailable. Other routes retain independent prerender blockers, including `/ops/agencies/[orgId]` and `/book/preview`.

Migrate one route family at a time. Preserve `organization_id` scoping at every request boundary, never place tenant or token-derived data in a shared `use cache` scope, and require an authenticated cross-organization navigation test before removing an opt-out. A production build, Linux image build, and browser navigation smoke test must pass before this switch can be promoted.

Trade-off: leaving the switch off defers App Shell and Partial Prefetching gains, but preserves the current tenant-safe rendering behavior while the global semantic change is audited.

## Offline recovery

`NEXT_EXPERIMENTAL_OFFLINE_RETRY=true` enables Next's experimental retry behavior for soft navigations, prefetches, and Server Actions. Direct `fetch` calls and React Query retain their own policies. The UI integration should use `useOffline` from `next/offline`; it must not replace `window.fetch` globally.

Promote only after authenticated browser checks cover losing and restoring connectivity during a navigation and a reviewed mutation. A full page reload still requires the network, and replaying a mutation carries duplicate-submission risk if its server-side operation is not idempotent.

Current audit: the opt-in build did not complete its compile phase within the local verification window and was stopped. Treat that as a failed promotion gate, not as proof of runtime safety.

## Rust React compiler

`NEXT_EXPERIMENTAL_RUST_REACT_COMPILER=true` selects the Turbopack-only experimental compiler while keeping the stable React compiler enabled. Keep it off by default until a clean production build, complete frontend suite, and repeatable build-time comparison show a benefit.

Current audit: the opt-in build panics while processing `app/globals.css`; the stable compiler builds the same source successfully. Keep the Rust profile held until that failure is resolved upstream or isolated to a reproducible environment constraint.

## TypeScript 7 split toolchain

The standalone application type-check uses TypeScript 7's native CLI, while ESLint, Next's built-in checker, and other JavaScript compiler-API consumers retain the TypeScript 6 compatibility package:

```json
{
  "@typescript/native": "npm:typescript@7.0.2",
  "typescript": "npm:@typescript/typescript6@6.0.2"
}
```

`pnpm run typecheck` generates Next route types and invokes the native `tsc` binary. ESLint and source-scanning tests resolve the `typescript` package name to the TypeScript 6 API. The compatibility package is version 6.0.2; its compiler and API report version 6.0.3.

Next 16.3 resolves the `typescript` package name directly during a production build and recognizes the compatibility package's `tsc6` executable. Enabling `experimental.useTypeScriptCli` under this alias layout would run the TypeScript 6 CLI, not the native TypeScript 7 CLI. Keep `experimental.useTypeScriptCli: false` to retain Next's JavaScript API checker and its diagnostic handling; the separate `typecheck` command provides native application checking. Docker builds currently run the API checker through `pnpm build`.

TypeScript 7 enables stable type ordering by default. Compare compatibility diagnostics with the same ordering after route generation:

```sh
cd apps/web
mise exec -- pnpm run typecheck
mise exec -- pnpm run typecheck:compat --stableTypeOrdering --incremental false
```

For continuous native application checking after route generation:

```sh
mise exec -- pnpm exec tsc --noEmit --watch
```

The application project excludes test files. The separate `tests/tsconfig.json` is not a CI gate. On 2026-09-30, adopting the official `@testing-library/jest-dom/vitest` entrypoint removed 5,129 missing matcher diagnostics; 358 existing test-source diagnostics across 75 files remain. Resolve those errors before adding the test project to required checks; see [the TypeScript audit](../../../output/dependency-modernization-20260930/typescript.md).

Retain the compatibility alias until `typescript-eslint` and source-scanning tests support TypeScript 7's API. Carrying both compiler packages preserves typed linting and Next build validation while the application check uses the native compiler. The split follows [Microsoft's side-by-side guidance](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/); Next's checker selection follows [its TypeScript CLI contract](https://nextjs.org/docs/app/api-reference/config/next-config-js/useTypeScriptCli).
