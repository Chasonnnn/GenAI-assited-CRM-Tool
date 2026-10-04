# CI and test audit — 2026-10-04

The verified batch removes 28 of 8,607 collected tests (0.33%). The requested 20% reduction would require 1,722 removals and remains unmet. Final backend and frontend coverage has no measured loss. The first hosted candidate passed in 5m45s, 18.44% faster than the three-run baseline median of 7m03s. That misses the 20% target; a subsequent reporting optimization is awaiting hosted verification.

## Test reduction

Baseline: `bef1a04161f9d5f78fffe9cc15a0db8143a9995f`, on the existing `chore/pnpm-12-release-followups` branch. Production source hashes remained unchanged. Counts are collected cases, including parameter rows; the backend's 503 subtests are reported separately and unchanged.

| Suite | Before | After | Removed |
| --- | ---: | ---: | ---: |
| Backend | 5,574 | 5,562 | 12 |
| Frontend | 3,033 | 3,017 | 16 |
| Combined | 8,607 | 8,579 | 28 |

The removals cover duplicate match lifecycle smoke tests, AI action registry/validation checks already exercised by execution tests, repeated initial component renders, and three Markdown wording assertions. Required assertions were carried into the named retained tests before deletion. Independent preservation reviews found no gaps. No production or shared test-support seam became obsolete.

Mechanical scans covered both test directories. Complete owner, caller, history, and retained-test reviews covered selected candidates; this is not a complete classification of all 8,607 cases. The reviewed evidence supports these 28 removals, not 1,722. Equal line coverage does not establish equivalent behavior. Distinct consent, tenant, permission, malformed-input, migration, concurrency, retry, accessibility, and lifecycle cases remain.

The invoked [test-audit skill](/Users/chason/.codex/skills/test-audit/SKILL.md) requires: “do not convert uncertain candidates into cleanup to increase deletion counts.” Further reductions require additional owner-by-owner evidence, not a coverage-only deletion list.

Evidence: [backend ledger](backend-ledger.md), [frontend ledger](frontend-ledger.md), [cross-cutting ledger](crosscut-ledger.md), [backend preservation review](backend-preservation-review.md), [frontend preservation review](frontend-preservation-review.md).

## Coverage

All comparisons use the same production source universe. The permitted drop is 2 percentage points for each metric in each suite.

| Suite / metric | Baseline | Final | Change, percentage points |
| --- | ---: | ---: | ---: |
| Backend lines | 81.65697% | 81.65948% | +0.00251 |
| Backend branches | 65.97698% | 65.98475% | +0.00778 |
| Frontend lines | 68.68268% | 68.68268% | 0 |
| Frontend statements | 66.62917% | 66.62917% | 0 |
| Frontend branches | 63.52641% | 63.52641% | 0 |
| Frontend functions | 59.58433% | 59.58433% | 0 |

Pruning alone preserved every frontend per-file coverage count. The four-shard upgraded-toolchain run also passed all floors, with one fewer covered frontend line, statement, and function: its largest drop was 0.00828 percentage points. The final full-suite run against the finalized lockfile exactly matched baseline frontend totals and had no per-file losses. Backend coverage also had no per-file losses. [Exact results](results.json), [backend coverage](backend-coverage.json), [pruning-only frontend coverage](frontend-pruning-coverage.json), [final frontend coverage](frontend-final-coverage.json).

## CI changes

- Backend: three parallel groups instead of two, retaining four workers per group. All 496 safe files appear exactly once; 45 migration/outbox files remain in the isolated serial group.
- Frontend: four shards instead of two, covering all 382 files. Blob reports merge into fresh combined coverage with the existing thresholds.
- Frontend coverage no longer waits for the production build. Required `Frontend Tests` still fails unless both the build and merged coverage succeed. Failure, cancellation, and skipped dependencies cannot produce a passing gate.

Security scans, launch gates, production image checks, required check names, source scope, coverage floors, and test isolation remain unchanged. The partition test executes the actual selector; the gate test executes all 16 dependency-result combinations. No passing result is reused from an earlier commit.

The first candidate's backend coverage job took 67 seconds, including 41 seconds generating coverage reports. The follow-up removes redundant text reporting: both retained XML and JSON commands enforce the same configured combined floor of 75.85, and the separate line/branch checks still run. The XML artifact and changed-line report remain. Installed Coverage.py source and official [XML](https://coverage.readthedocs.io/en/latest/commands/cmd_xml.html) / [JSON](https://coverage.readthedocs.io/en/latest/commands/cmd_json.html) documentation confirm this behavior. [Independent review](coverage-report-review.md).

Three alternating local report-generation runs reduced median reporting time from 14.17 to 10.15 seconds (28.35%) using identical frozen coverage data. JSON totals were identical. Both remaining commands passed the normal floor and returned exit code 2 when a temporary configuration raised the floor to 100. The 14 CI configuration tests and changed-file Ruff/format checks passed. [Report benchmark and negative controls](coverage-report-benchmark.json).

The three latest successful baseline runs took 370, 423, and 477 seconds from workflow creation to final job completion, including runner queue time. Candidate one took 345 seconds on `0d2943db2`; every job passed. The observed improvement is 18.44% against the baseline median, with substantial runner variability. Extra jobs increase runner demand, and file-count balance does not guarantee equal execution time. Human review and merge availability are outside this timing metric. [Hosted measurements](hosted-ci.json), [first candidate run](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/actions/runs/37178294086).

The repository's main branch requires branches to be up to date. Merging one PR can therefore require the others to rerun CI. GitHub merge queues address that workflow, but GitHub documents them for organization-owned repositories; this repository is personal-owned. Protection settings were not changed. [GitHub merge queue requirements](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).

## Tooling

Vitest and its coverage provider are upgraded from 5.0.1 to 5.0.3; jsdom from 29.1.1 to 30.1.1. TS7 was already on stable 7.0.2. Runtime pins and dependency policies remain unchanged.

Across three repetitions of the same 588 tests, the upgraded dependency group reduced local median time by 15.38% with a cold transform cache and 13.57% with a warm cache. Ranges overlap. These are sample test timings, not full-suite or hosted PR CI timings. The proposed GitHub transform cache was removed because the measurements did not show a warm-cache benefit. [Toolchain decisions, compatibility, and sources](toolchain.md), [benchmark measurements](toolchain-benchmark.json), [final independent review](ci-toolchain-final-review.md).

## Verification and delivery

- Full backend suite: 5,562 cases plus 503 subtests passed on a migrated disposable PostgreSQL database. Baseline passed 5,574 cases plus the same subtests. Backend durations are not a performance comparison because frontend work ran concurrently.
- Final frontend check: application/test type checks, ESLint, and all 382 files / 3,017 tests passed. Full V8 coverage, four-shard execution and blob merge, and the Next.js Webpack production build passed.
- Final CI configuration tests: 14 passed. Changed Python files passed Ruff and formatting checks. Whitespace checks passed.
- Both backend runs emitted the same pre-existing SQLite connection `ResourceWarning` in `test_donor_approval_seed_is_idempotent_and_preserves_existing_stage_ids`; this unrelated warning remains.
- The skill's OpenClaw-specific scripts and `$autoreview` were unavailable. Repository validation and independent preservation reviews were used instead; those unavailable tools were not run.

Test pruning removes 306 net test lines. Stronger existing CI guards add 53 net test lines, for a total net reduction of 253 test lines. Production and shared test-support LOC changes are zero; workflow changes add five net lines. Dependency manifests and generated lockfile changes are separate from these counts.

Changes are published in [PR #789](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/789) on the existing branch. No PR merge, release, or deployment is authorized. The first hosted run passed; the reporting follow-up awaits its own run.

Before publication, main at `e772a87f4` was merged into the branch without conflicts. Its only additional file change was the already-merged Google Tasks concurrency-test fix; no production source or collected-case count changed. All 21 concurrency and CI configuration tests passed after reconciliation. The repository wrapper could not find the local `createdb` client, so validation used an explicitly created, migrated disposable database through the existing container instead; that database was removed afterward.

The two audit databases and temporary transform/fixture/uv caches were removed. No application servers were started. The pre-existing `crm_db` service remains running. Detailed local execution logs remain under `output/ci-test-audit-20261003.local/`; compact evidence is committed in this directory.

Remaining work: measure hosted total PR CI time on the candidate; audit additional test owners before claiming the count target; review the pre-existing nested, uncollected `test_validate_update_status_action_normalizes` and the query-invalidation assertion concerns recorded in the ledgers. An uncollected declaration is not a test-count reduction.
