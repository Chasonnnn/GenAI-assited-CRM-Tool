# Dependency modernization audit — 2026-09-07

Baseline: `bb9630f4`. Scope: 61 direct frontend dependencies and 76 backend runtime/test dependencies. Registry queries found 38 frontend updates and 65 backend updates, with no PyPI lookup failures. The [registry snapshot](registry-snapshot.json) records the original versions. These are candidates, not 103 approved upgrades. Transitive dependencies and vulnerabilities were not exhaustively audited.

## Adopted

| Change | Benefit and adoption | Validation |
| --- | --- | --- |
| Vitest 4.1.9 → 5.0.0 | Persistent transformed-module cache; explicit isolated fork workers; `pnpm run test:doctor`; default mock-history clearing and stricter async assertions retained | 266 files / 1,507 tests pass; native and compatibility compiler checks; ESLint |
| Node typings 26.0.1 → 24.13.3 | Align available APIs with Node 24.18.0 in Mise, CI, and Docker | TypeScript 7 and TypeScript 6 checks pass |
| DOMPurify 3.4.12 → 3.4.14 | Upstream sanitizer fixes; existing explicit HTML allowlists retained | 56 focused tests; full frontend check |
| Remove five FullCalendar 6.1.21 packages | No application or test imports; only manifest and Next import-optimization entries referenced them. Removed those entries too | Full frontend check; production build result below |

Vitest requires Node >=22.12 and Vite >=6.4; this repo already uses Node 24.18.0 and Vite 8.1.0. The migration changes mock-history defaults, rejects unawaited async assertions and nested hoisted mocks, and removes deprecated entrypoints. The existing suite passes without suppressing those checks. There are no custom Vitest reporters, benchmark files, browser-mode tests, or inline projects requiring migration. [Migration guide](https://main.vitest.dev/guide/migration/)

DOMPurify 3.4.14 fixes risky-tag allowlist bypass cases and mixed document contexts. Our rich-text and email helpers continue to restrict HTML through their existing options. Passing tests establish application compatibility, not a complete XSS audit. [Release notes](https://github.com/cure53/DOMPurify/releases/tag/3.4.14)

## Vitest performance evidence

Same machine, Node version, application source, and 266-file suite; default worker count. Values are Vitest-reported elapsed duration, not independently measured process wall time.

| Configuration | Duration | Result |
| --- | ---: | --- |
| 4.1.9, original configuration | 22.63 s | 1,507 passed |
| 5.0.0, original configuration | 20.61 s | 1,507 passed |
| 5.0.0, vmThreads + module cache | 2.88 s | All 266 files failed in setup; no tests ran |
| 5.0.0, forks + module cache | 22.26 s | 1,507 passed |
| 5.0.0, forks + warm module cache | 21.86 s | 1,507 passed |

These exploratory samples do not establish a reproducible speedup. Warm-cache validation overlapped with ESLint, and baseline/candidate runs were not randomized or repeated equally. Upstream's published benchmark also shows modest improvements for isolated jsdom/fork workloads. Cache adoption is intended to reduce repeated transformation work, especially for focused local reruns. [Release benchmarks](https://main.vitest.dev/blog/vitest-5), [performance guidance](https://main.vitest.dev/guide/improving-performance)

The vmThreads failure is `TypeError: Cannot redefine property: location` at `apps/web/tests/setup.ts:159`. Keep isolated forks. Changing the shared location mock or using shared globals requires a separate test-environment change with shuffled-order runs and memory measurements. A faster failed run is not a performance result. `test:doctor` is available, but its broader candidate sweep was not run; targeted pool/cache trials were run instead.

## Existing modernization already in use

TypeScript 7 is already adopted through `@typescript/native: npm:typescript@7.0.2`. The `typescript` name aliases `@typescript/typescript6@6.0.2` for compiler-API consumers. Executables report 7.0.2 and 6.0.3 respectively. Keep the split: TypeScript 7.0 has no programmatic compiler API. [Microsoft's side-by-side guidance](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)

Next 16.3 already enables React Compiler and typed routes. Cache Components, partial prefetching, offline retry, and the Rust compiler are gated. The build uses webpack and the TypeScript API checker. Installed version-matched documentation was reviewed at `apps/web/node_modules/next/dist/docs/01-app/03-api-reference/05-config/02-typescript.md`; CLI checking is available but has different diagnostics. Do not turn all features on together: caching alters authenticated rendering, and offline navigation retry does not cover TanStack Query requests.

## Prioritized follow-up candidates

| Priority | Candidate | Useful changes and concrete adoption work | Required gate / current decision |
| --- | --- | --- | --- |
| 1 | Next + bundle analyzer 16.3.0 → 16.3.4 | Patch fixes the TypeScript 6 alias build error; review the existing `useTypeScriptCli: false` workaround against the corrected release | Keep versions paired. Build, route generation, auth redirects, cross-tenant navigation, and current React Compiler behavior. Candidate only; runtime rendering was not upgraded here. [Release](https://github.com/vercel/next.js/releases/tag/v16.3.4) |
| 1 | google-genai 1.61.0 → 2.22.0 | Adds Gemini 3.8 metadata. Review accumulated streaming/retry fixes, client lifecycle, and audio transcription options in `ai_provider.py` and `transcription_service.py` | 2.0's documented break is in Interactions; current code uses GenerateContent. Still validate all three provider modes, WIF refresh, streaming cancellation, usage accounting, and transcription before adoption. No provider API calls performed. [2.0](https://github.com/googleapis/python-genai/releases/tag/v2.0.0), [2.22](https://github.com/googleapis/python-genai/releases/tag/v2.22.0), [changelog](https://github.com/googleapis/python-genai/blob/main/CHANGELOG.md) |
| 2 | Pydantic 2.12.5 → 2.13.5 with its exact required core | Validation/serialization improvements and changed serialization behavior. Inspect schema outputs and ORM conversion; do not independently select latest pydantic-core | Resolve the coupled pins in a disposable environment; full API, OpenAPI contract, export and secret-redaction tests. Keep polymorphic serialization opt-in until field exposure is checked. [Changelog](https://pydantic.dev/docs/validation/latest/get-started/changelog/) |
| 2 | FastAPI 0.136.3 → 0.141.1 with compatible Starlette/AnyIO | Review SSE/JSONL fixes against chat streaming. `app.frontend()` is not useful for this separately deployed Next app | Full API suite, middleware/auth/CSRF negatives, disconnect cleanup and stream headers. Do not replace custom transport just to use the new API. [Release notes](https://fastapi.tiangolo.com/release-notes/) |
| 2 | Base UI 1.6.0 → 1.8.0 | Trigger mounting/focus fixes and Combobox collection support are relevant to customized controls | Read intervening 1.7 notes, then exercise Select labels, portals, dialogs, forms and keyboard focus in a browser. Preserve wrapper semantics. [1.8 release](https://github.com/mui/base-ui/releases/tag/v1.8.0) |
| 3 | Vite 8.1.0 → 8.2.2; React plugin 6.0.3 → 6.1.1 | Potential test-transform improvements; no demonstrated need after the Vitest trial | Review both release histories and the explicit Vite override before changing; repeat controlled timing and frozen installs. Registry inventory only for these targets. |
| 3 | Tiptap 3.27.1 → 3.31.3; TanStack Query 5.101.2 → 5.102.8 | Candidate editor/cache fixes | Review releases first. Upgrade Tiptap extensions together; verify HTML roundtrips and editor focus. Query changes need mutation invalidation, optimistic rollback, hydration and org-switch tests. No feature-benefit claim established yet. |

FullCalendar 7 has native React rendering, a theme system, new package entrypoints, and substantial CSS/API changes. None benefit this application while there are no imports. Removal avoids an unnecessary major migration. [v7 migration guide](https://fullcalendar.io/docs/upgrading-from-v6)

Other majors in the inventory include jsdom 30, jest-dom 7, markdown-it 15, react-dropzone 20, Redis 8, OpenAI 3, ReportLab 5, and protobuf 7. They remain unvalidated candidates. Upgrade test-environment packages separately from Vitest so failures remain attributable. Backend observability packages must move as a compatible SDK/instrumentation group; their beta-labelled instrumentation versions are normal upstream packaging, not a reason to select them independently.

Runtime versions remain aligned with the approved global Mise baseline. Existing pnpm minimum-release-age, trust policy, build-script restrictions, overrides, and frozen-lockfile CI remain in force. No runtime upgrade or policy bypass was needed.

## Reusable modernization skill requirements

The reusable skill should produce a decision ledger rather than a blanket update command. This audit supplies a first-project example; no global skill was installed.

1. Read repository instructions, runtime baseline, manifests, lockfiles, overrides, CI, containers, and actual installed executables. Record source commit, dirty files, and authorization boundaries.
2. Query registries with timestamps. Separate declared, locked, installed, and candidate versions; distinguish stable tags from prereleases. Check peer/engine ranges and coupled packages.
3. For each shortlisted candidate, read official release and migration notes across the entire version gap. Map each relevant new feature, default change, removal, and performance claim to local consumers.
4. Assign one outcome: adopt automatically, enable deliberately, replace old code, defer with a concrete gate, or remove an unused dependency. New features without a use case need no adoption work.
5. Lock a baseline before changing one dependency group. Keep tests, hardware, worker counts, cache state, and runtime fixed for performance comparisons. Use repeated alternating runs and report median and spread before claiming gains.
6. Run focused behavior tests, full affected suites, builds and platform checks proportional to the change. Preserve isolation and assertions; do not weaken tests to obtain a faster result. Treat setup failures as setup failures.
7. Record exact versions, local code/config changes, evidence, untested surfaces, and rollback. Commit each validated logical group according to repository policy. Deployment and external effects require their own authorization.
8. Test the eventual skill on another project and on failure cases: incompatible compiler API, stale cached docs, package with no consumers, changed default, dirty checkout, blocked network, and a benchmark that is faster only because tests stopped running.

## Validation status

- Vitest migration: full suite, native/compatibility type checks and ESLint passed.
- Node type alignment: native/compatibility type checks passed.
- DOMPurify: 56 focused tests passed; final full frontend check passed with 1,507 tests.
- Production build: passed on Next 16.3.0 with webpack, including route generation. The initial sandboxed build failed fetching Google Fonts; a network-enabled retry passed.
- Frozen offline frontend installation: passed.
- No backend dependencies changed; no backend migration, live provider call, authenticated browser QA, CI run, push or deployment performed.
