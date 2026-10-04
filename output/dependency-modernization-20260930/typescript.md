# TypeScript dependency adoption — 2026-09-30

Source revision: `595bf5b7`, branch `fix/log-client-error-codes`. Native compiler: 7.0.2. Compatibility package: `@typescript/typescript6` 6.0.2; executable/API version: 6.0.3. Installed `typescript-eslint` 8.62.1 requires TypeScript `>=4.8.4 <6.1.0`.

## Adopted changes

- `tests/setup.ts` imports `@testing-library/jest-dom/vitest`, replacing the Jest entrypoint and duplicate manual matcher registration. The official entrypoint registers matchers on Vitest's `expect` and loads its assertion declarations. `tests/tsconfig.json` selects the same Vitest declarations. [Official integration](https://github.com/testing-library/jest-dom#with-vitest)
- `apps/web/docs/next-16-3-adoption.md` records the actual Next compiler resolution, native watch command, and TypeScript 6 parity command with `--stableTypeOrdering`.
- The TypeScript aliases remain unchanged. Native TypeScript checks application code; ESLint, Next's API checker, and source-scanning tests retain TypeScript 6. [Microsoft's split-package guidance](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)

## Native test-project baseline

Command, run from `apps/web` before and after the matcher integration:

```sh
mise exec -- node_modules/.bin/tsc --noEmit --incremental false -p tests/tsconfig.json
```

Both runs exited 1. Emission and incremental writes were disabled. The test config selects 367 root files and inherits `strict`, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes`. Production modules imported by tests are also checked. Every reported diagnostic location was in `tests/`.

| State | Diagnostics | Files with diagnostics | Missing DOM matcher diagnostics |
| --- | ---: | ---: | ---: |
| Original setup | 5,487 | 257 | 5,129 |
| Official Vitest entrypoint | 358 | 75 | 0 |

The remaining diagnostic messages match the original baseline after normalizing line numbers changed by the setup edit. This change removes the declaration mismatch; it does not make the test project ready for a required compiler gate. Normal Vitest execution does not replace test-source type checking. [Vitest type testing](https://vitest.dev/guide/testing-types)

### Diagnostic counts

| Code | Before | After |
| --- | ---: | ---: |
| TS2339 | 5,135 | 6 |
| TS2345 | 77 | 77 |
| TS2532 | 73 | 73 |
| TS2322 | 64 | 64 |
| TS2769 | 53 | 53 |
| TS18048 | 35 | 35 |
| TS2741 | 8 | 8 |
| TS2578 | 6 | 6 |
| TS2503 | 6 | 6 |
| TS2349 | 4 | 4 |
| TS2739 | 4 | 4 |
| TS2375 | 3 | 3 |
| TS2353 | 2 | 2 |
| TS7034 | 2 | 2 |
| TS7005 | 2 | 2 |
| TS2740 | 2 | 2 |
| TS2554 | 2 | 2 |
| TS5097 | 1 | 1 |
| TS7031 | 1 | 1 |
| TS2488 | 1 | 1 |
| TS2551 | 1 | 1 |
| TS7006 | 1 | 1 |
| TS2352 | 1 | 1 |
| TS18047 | 1 | 1 |
| TS2304 | 1 | 1 |
| TS2556 | 1 | 1 |

### Remaining examples

- `tests/activity-timeline.test.tsx:100`: a `TaskListItem` fixture makes required fields optional.
- `tests/agency-users-tab.test.tsx:63`: fixtures do not satisfy `OrgMember`.
- `tests/appointments-google-meet.test.tsx:643`: unchecked array access passes a possibly undefined element to Testing Library.
- `tests/api-ai-contracts.test.ts:16`: a `.ts` import requires `allowImportingTsExtensions` in the test compiler contract.
- `tests/no-nested-interactive.test.ts:60`: `ts` is a runtime constant used as a type namespace; the imported `TypeScript` namespace is available.
- `tests/setup.ts`: existing unused `@ts-expect-error` directives remain on browser polyfills.

The largest remaining files contain 47 diagnostics in `pipelines-settings-page.test.tsx`, 44 in `integrations-page.test.tsx`, 29 in `permission-workspace.test.tsx`, and 19 in `platform-form-template-page.test.tsx`. Resolve fixture and assertion typing by feature area before introducing a passing gate; do not weaken application strictness to absorb these errors.

## Existing adoption and boundaries

| Surface | Evidence | Decision |
| --- | --- | --- |
| Application compiler | `package.json` runs `next typegen && tsc --noEmit`; CI runs that script | Native TypeScript 7 already adopted |
| Compatibility compiler | `typecheck:compat` runs `tsc6 --noEmit`; stable type ordering defaults to false in TS6 | Compare with `--stableTypeOrdering` after generating the same route types |
| Next production checker | `experimental.useTypeScriptCli: false`; installed Next 16.3.4 recognizes `tsc6` in its package resolver | Keep API checker; enabling the option with current aliases runs TS6 CLI, not TS7 |
| Docker | `pnpm build` only | API checker runs; no separate native gate |
| Typed routes | Enabled, but `components/app-link.tsx` accepts arbitrary strings and casts to `Route` | Follow-up: typed internal-link contract with an explicit unrestricted URL boundary |
| Editor | Next plugin requested in tsconfig; no workspace TypeScript SDK selection | Verify plugin support before adopting native language server |
| Worker scaling | No `--checkers` configuration or project-reference builds | Tune only after isolated measurements; no project-specific speedup claimed |

Next resolves the package named `typescript`, not whichever package owns the shell's `tsc` shim. The installed resolver returned the compatibility package's `bin/tsc6` during a read-only API call. The earlier guide's assertion that the `tsc6` name prevents CLI integration was stale. [Next CLI contract](https://nextjs.org/docs/app/api-reference/config/next-config-js/useTypeScriptCli)

The main application config uses bundler resolution, relative paths, strict typing, incremental checking, and generated routes. No inspected config uses deprecated `baseUrl`, ES5 targeting, `node10`, legacy module targets, or ignored TS6 deprecations. The official registry's TypeScript `latest` was 7.0.2 during this audit. [Registry metadata](https://registry.npmjs.org/typescript/latest)

Node 24.18.0 and pnpm 11.18.0 align across global Mise, repository Mise, package declaration, CI, and Docker. Runtime versions and TypeScript aliases were not changed in this lane.

## Validation boundary

Read-only executable versions, config parsing, package/API resolution, and before/after native diagnostics completed. Required test-project checking remains deferred because of 358 existing diagnostics. Runtime Vitest verification and final frontend validation are recorded in the parent dependency report.
