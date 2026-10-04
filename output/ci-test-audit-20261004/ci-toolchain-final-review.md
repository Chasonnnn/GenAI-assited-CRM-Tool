# Independent final CI and toolchain review

Result: no blocking findings. This refresh read the final live dependency files and workflow, installed package metadata/source, validation artifacts, and `toolchain-audit.md`. No test, install, or benchmark was started, and no source/configuration file was changed by this reviewer.

Review base: `900936809027a36594aed2a478141b592e65c6b5`. The hashes below describe final live files after the benchmark restored the selected toolchain and pnpm deduplicated MSW's optional cookie dependency.

| Reviewed file | SHA-256 |
| --- | --- |
| `.github/workflows/ci.yml` | `51d3494d5ac9b335982030c2c3f35a442840867b3c2360d82007f8eec05fb5cc` |
| `apps/web/package.json` | `ef92178a691b60e51da94e6c901ea52541f7565e1025a53d7f26388ddc03d791` |
| `apps/web/pnpm-lock.yaml` | `570b298009c7b49f3b8fb908f209246e982706c7658db49e64543d97184c5b42` |
| `apps/web/pnpm-workspace.yaml` | `19c187dfe8b55111cb6996e1c31e696370a9bd4fb1466adfaf5424202d1fd269` |

## CI gate preservation

- The final workflow contains three parallel backend groups plus the isolated serial group, four frontend shards, an independent frontend coverage job, and the final required `Frontend Tests` gate. The proposed GitHub Actions Vitest cache is absent.
- The backend selector covers the 496 safe files exactly once with offsets 0, 1, and 2 at stride 3. The 45 migration/outbox files remain on their separate PostgreSQL-backed serial job. Migration-model verification remains in `parallel-1`.
- Installed Vitest 5.0.3 preserves deterministic, disjoint shard membership over the current file inventory. Every shard executes the tests and produces fresh blob reports. The coverage job downloads and merges those reports without individual-shard threshold overrides.
- A failed, skipped, or cancelled shard prevents a successful coverage job. Required `Frontend Tests` retains `if: always()` and succeeds only when both the build and merged coverage dependencies report success. The extra report parallelism does not remove the build prerequisite.
- Coverage thresholds and source scope, isolated fork workers, job permission inheritance, security scans, launch gates, and production image checks remain unchanged. The pre-existing local `fsModuleCache` setting is unchanged. Vitest continues disabling Node bytecode caching in V8 coverage workers.

Installed source reviewed: Vitest 5.0.3 `dist/chunks/index.DpLw24bj.js`, including V8 coverage worker environment, report behavior, and `BaseSequencer`.

## Dependency and supply-chain scope

- The only changed direct declarations and application-lock importers are `vitest` 5.0.3, matching `@vitest/coverage-v8` 5.0.3, and `jsdom` 30.1.1. Production dependency importers, Vite 8.1.0, both TypeScript packages, and plugin-react remain unchanged.
- Both YAML documents in the pnpm 12 lockfile were compared. The package-manager document is identical. Application lock settings, overrides, and package-extension checksum are identical. All existing same-version package metadata is identical.
- The final application graph adds 20 package-version records and removes 24. Every added package is reachable from the three changed direct dependencies, and every added package record retains an integrity digest.
- Shared transitive effects: pnpm's existing `autoDedupe: true` resolves `lru-cache` 11.5.1 to 11.5.3 for jsdom's graph and the existing Babel helper/path-scurry consumers. Optional MSW 2.14.6 now shares jsdom's `tough-cookie` 6.0.2 instead of retaining 6.0.1. Installed MSW declares `tough-cookie: ^6.0.1`, so this patch deduplication satisfies its existing requirement. These are the only same-version consumer snapshot changes; no unrelated direct upgrade was introduced.
- Workspace policy is byte-identical: the release-age floor, no-downgrade trust policy, override versions, peer allowances, and dependency-build allowlist are preserved. The workflow retains frozen installs.
- Installed candidate metadata confirms coverage's exact Vitest 5.0.3 peer requirement. Vitest accepts the pinned Node 24 line and Vite 8; jsdom 30.1.1 requires Node 24.15.0 or newer within Node 24, satisfied by repository/CI/Docker Node 24.18.0. Its optional canvas peer is not introduced by this change. No runtime upgrade or compatibility bypass is needed.

## Existing validation evidence inspected

- `toolchain-check.log`: native application and test type checks, ESLint, and Vitest 5.0.3 complete; 382 files and 3,017 tests pass.
- Four shard logs: 96/96/95/95 files and 802/691/762/762 passing tests, totaling the same 382 files and 3,017 tests.
- Baseline and final coverage summaries have identical denominators. Displayed percentages change from 68.68 to 68.67 lines and 59.58 to 59.57 functions; statements remain 66.62 and branches 63.52. Raw covered counts decrease by one line, one statement, and one function, with unchanged covered branches. All remain above existing thresholds.

The recorded full check and shard results above precede the final optional-MSW deduplication. No live candidate CI result is established, so total PR CI improvement remains projected until measured remotely.

Parent validation addendum: the final live lockfile passed application and test type checks, ESLint, all 382 files / 3,017 tests, the production build, and a separate full V8 coverage run. That final coverage run exactly matched baseline totals for all four frontend metrics and had no per-file losses. These commands were executed by the parent after the independent read-only review; the reviewer did not rerun them.
