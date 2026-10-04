# Frontend test tooling

Vitest and `@vitest/coverage-v8` move from 5.0.1 to 5.0.3. jsdom moves from 29.1.1 to 30.1.1. TypeScript 7.0.2 is already the stable native checker used by the application and test type checks; the TypeScript 6.0.2 API compatibility package remains for Next.js and ESLint.

Vitest 5.0.3 fixes cached-import revalidation and compatibility with jsdom Blob behavior. jsdom 30.1 improves DOM operations used by React Testing Library; 30.1.1 also fixes focus/blur regressions. [Vitest release](https://github.com/vitest-dev/vitest/releases/tag/v5.0.3), [jsdom 30.1 release](https://github.com/jsdom/jsdom/releases/tag/v30.1.0), [jsdom patch](https://github.com/jsdom/jsdom/releases/tag/v30.1.1).

Node 24.18.0, pnpm 12.9.1, Vite 8.1.0, plugin-react 6.0.3, and both TypeScript packages remain unchanged. Registry releases were checked on 2026-10-04. Vite 8.3.2 has a potentially relevant transform optimization, but transforms occupied only a small share of this suite. Plugin React's newer compiler path is not enabled here. Neither was adopted without a measured benefit. [Vite changelog](https://github.com/vitejs/vite/blob/main/packages/vite/CHANGELOG.md), [Plugin React changelog](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/CHANGELOG.md), [TypeScript 7 release](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/).

## Controlled local benchmark at the original audit revision

The same 20 files and 588 tests ran three times per dependency group, with cold and warm transform caches, four isolated fork workers, V8 coverage, and file-shuffle seed 20261003. Source and test hashes were identical in all 12 executions. Installs were outside the timing window. No other task test/build ran concurrently. Every run passed.

| Transform cache | Baseline median | Candidate median | Reduction |
| --- | ---: | ---: | ---: |
| Cold | 26.92 s | 22.78 s | 15.38% |
| Warm | 30.25 s | 26.14 s | 13.57% |

Timing ranges overlap: baseline cold 25.56–34.61 s, candidate cold 22.47–30.99 s; baseline warm 24.47–33.60 s, candidate warm 24.27–36.01 s. This is a representative local sample, not full-suite or hosted PR CI improvement. Only the transform cache was cold; OS and dependency caches remained warm. The experiment measures the dependency group together, not each package separately. [Measurements and file list](toolchain-benchmark.json).

Warm transform caches did not produce a clear benefit. The proposed GitHub cache step was removed. Existing local `fsModuleCache: true` remains. A disposable fixture confirmed warm hits, changed-source invalidation, renamed-import invalidation, missing-import failure, and recovery. Cache correctness does not establish speed.

## Dependency scope and validation

The release-age floor, trust policy, dependency build allowlist, overrides, and runtime pins are unchanged. The matching Vitest coverage version and jsdom's Node requirement are satisfied. Existing pnpm deduplication also updates shared `lru-cache` from 11.5.1 to 11.5.3 and optional MSW's `tough-cookie` from 6.0.1 to 6.0.2. No unrelated direct dependency changed.

The benchmark and four-shard coverage runs used lock SHA-256 `87ecc7baa37bb3467fde00104099d258b54e11a3d15a56ec18171e1aa49e4459`. The subsequent `pnpm run build` setup deduplicated optional MSW's cookie dependency to the 6.0.2 already required by jsdom; the final lock hash is `570b298009c7b49f3b8fb908f209246e982706c7658db49e64543d97184c5b42`. At the original audit revision, application/test type checks, ESLint, all 3,017 tests, and the production build passed on that dependency graph. After upstream merges, all 3,056 retained frontend tests, type checks, lint, and hosted builds passed; refreshed coverage is recorded in the audit report.

The full four-shard run and blob merge passed all existing coverage floors. Native TS7 checks and the Next.js Webpack production build passed. No compiler compatibility alias, isolation setting, source exclusion, or coverage floor was weakened.
