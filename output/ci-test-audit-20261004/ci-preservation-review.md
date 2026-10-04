# Independent CI preservation review

Result: no blocking findings in the reviewed changes. Read-only code review and file-inventory analysis; no test suite, application, container, or remote CI run was started by this reviewer.

Review base: `bef1a04161f9d5f78fffe9cc15a0db8143a9995f`.

Reviewed working-file SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `.github/workflows/ci.yml` | `51d3494d5ac9b335982030c2c3f35a442840867b3c2360d82007f8eec05fb5cc` |
| `apps/api/tests/test_release_ci.py` | `0f3a8f9d4ff32d9d722e971eb24957cd8308510f53bad9e5295d92b2385c4868` |
| `apps/web/tests/next-16-3-adoption.test.ts` | `c7d2fd99ef1e4f00a97f4205aa132e1b9c1b13c929b2075e1cbec8e6c966888c` |
| `output/ci-test-audit-20261003.local/crosscut-ledger.md` | `313c00a571468de6e37de0014b3b2e96c622e2eecd07de9dbba7ff2756f3442e` |

## Test partition and serial isolation

- Current backend inventory: 541 `test_*.py` files. The unchanged migration/outbox exclusions select 45 serial files; all 45 are at the root of `tests`, where the serial command reaches them. The remaining 496 files partition into 166, 165, and 165 distinct files using offsets 0, 1, and 2 with stride 3. Their union equals the complete safe-file inventory and no file appears twice.
- Every backend matrix entry receives its own PostgreSQL service. The serial command retains its own matrix condition and no xdist arguments. Parallel groups retain four workers, `loadscope`, and both migration/outbox exclusions. Migration-model verification still runs once in `parallel-1`.
- Current frontend inventory: 382 test files. Inspection of installed Vitest's `BaseSequencer` confirms path-hash sorting followed by disjoint contiguous shard ranges. Four shards cover 96, 96, 95, and 95 files, with no change to the discovery pattern, test environment, or worker isolation.
- Vitest's installed `BlobReporter` includes shard index and count in each default output filename. Four artifacts therefore merge without report-file collisions. Artifact names include the shard index; missing report uploads still fail their producing job.
- The revised backend configuration test executes the actual workflow partitioner over safe, nested, serial, and non-test fixture paths. This protects the partition contract more directly than the removed stride-string assertion. The reviewer inspected this test but did not execute it.

## Coverage and failure propagation

- `frontend-coverage` depends on the entire frontend shard matrix. Its default success condition means a failed, skipped, or cancelled shard prevents a successful coverage job.
- Required `Frontend Tests` retains its exact check name, has `if: always()`, and requires both `frontend-build` and `frontend-coverage`. Its shell succeeds only when both dependency result strings equal `success`. Failure, cancellation, and skipped coverage therefore cannot produce a green required gate. The revised test enumerates all 16 result combinations with Bash fail-fast behavior; this review did not execute those combinations.
- Moving coverage merging before the build dependency permits it to overlap the build. It does not remove the build prerequisite from the final required gate. Workflow cancellation may prevent completion, but cannot turn the required result into success.
- Frontend V8 coverage scope and all four thresholds remain unchanged: lines 62.07, statements 60.04, branches 57.05, functions 52.11. Per-shard zero thresholds remain confined to shard commands; merged coverage still runs without threshold overrides.
- Backend combine/report/XML/JSON commands, configured combined floor 75.85, explicit line floor 79.96, and branch floor 63.03 are unchanged. Matrix-specific coverage files and artifact merge patterns include the new parallel group automatically.
- No workflow or job permission declaration changes. Required Backend Tests, Frontend Tests, and Production Artifacts names remain. Security scans, production image builds, lint, schema checks, and launch gates are unchanged.

## Three documentation-test removals

Reviewed the complete original and remaining adoption tests, the adoption guide, Next configuration, package scripts, relevant dependency guard, CI build/typecheck commands, original adoption commit `2406ca917b51743f23c78c2ff61a489792af35a0`, and the cross-cutting ledger.

- D1, `records the tenant-safety migration boundary before the feature can be promoted`: only asserted Markdown phrases and the historical blocker count. Retained configuration execution still proves experimental features remain off by default and require explicit switches. The deleted callback never exercised tenant isolation or promotion readiness.
- D2, `documents the TypeScript 7 split-toolchain boundary`: only asserted a Markdown heading, quoted versions, and command/configuration phrases. Actual compiler configuration, dependency guard, application/test type checks, and production build remain. The guide already contains stale typecheck/version statements that this callback did not detect.
- D3, `documents the production bundler boundary`: only asserted explanation text. The current executable build command remains `next build --webpack`, and CI still executes the real production build. The unchanged guide retains the reason for the fallback.

All three removals match the ledger. Each removes wording-preservation assertions rather than an executable production contract. The retained experimental-default, generated-route-validator, build-cache, dependency, and build checks remain. No replacement tests or production seams are needed for these deletions.

## Limits

This review establishes configuration preservation and the current file partition, not passing tests, equivalent measured coverage, or achieved CI speed. The parent validation must execute the affected tests and merged coverage paths and distinguish projected timing from a successful candidate CI run. The remote branch up-to-date rule and merge-queue settings are outside this diff.
