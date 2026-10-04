# CI and test audit — 2026-10-04

Hosted CI median time fell from **6m01s to 4m30s (25.2%)** across two baseline and two final runs. The audit removes **28 of 8,682 collected cases (0.32%)**. The requested 20% test reduction would require 1,737 removals and remains unmet. Maximum measured coverage loss is **0.003883 percentage points**, within the 2-point limit per metric per suite.

[PR #789](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/789) was merged outside this session at 2026-10-04 05:25:08 UTC, as `87523300699322736fe1d82fc5eca6cb4ddb2a45`. This session pushed the reviewed changes and opened the PR; it did not perform the merge or a deployment.

## Test reduction and scope

| Suite | Before | After | Removed |
| --- | ---: | ---: | ---: |
| Backend | 5,610 | 5,598 | 12 |
| Frontend | 3,072 | 3,056 | 16 |
| Combined | 8,682 | 8,654 | 28 |

The backend's 503 subtests are unchanged and reported separately. Counts use collected cases, including parameter rows. No production or shared test-support code was removed.

The batch removes duplicate match lifecycle smoke tests, AI registry/validation checks already exercised by execution tests, repeated component initial renders, and three Markdown wording assertions. Required assertions were carried into named retained tests before deletion. Independent preservation reviews found no gaps.

Mechanical discovery covered both test directories; complete owner, caller, history, and retained-test review covered selected candidates. This is not a complete classification of all 8,682 cases. The reviewed evidence supports 28 removals, not 1,737. Distinct consent, tenant, permission, malformed-input, migration, concurrency, retry, accessibility, and lifecycle cases remain. The invoked test-audit skill requires: “do not convert uncertain candidates into cleanup to increase deletion counts.”

[Backend ledger](backend-ledger.md), [frontend ledger](frontend-ledger.md), [cross-cutting ledger](crosscut-ledger.md), [backend preservation review](backend-preservation-review.md), [frontend preservation review](frontend-preservation-review.md).

## Final coverage

Baseline application/test source is main `d881caa07`; candidate code is `dbbc70a35`. The merged commit has the identical tree. The backend baseline checkout was `e6d86954a`, whose API source/tests are identical to `d881caa07`. The frontend baseline added exactly the two intervening sidebar files and verified all covered source hashes against the candidate. This refreshed comparison follows the concurrent upstream pipeline and sidebar merges.

| Suite / metric | Baseline | Candidate | Change, percentage points |
| --- | ---: | ---: | ---: |
| Backend lines | 81.73114% | 81.72738% | -0.00376 |
| Backend branches | 66.05964% | 66.05576% | -0.00388 |
| Backend combined | 77.90359% | 77.89980% | -0.00379 |
| Frontend lines | 68.85847% | 68.85847% | +0.00000 |
| Frontend statements | 66.81080% | 66.81080% | +0.00000 |
| Frontend branches | 63.75394% | 63.75394% | +0.00000 |
| Frontend functions | 59.74930% | 59.74930% | +0.00000 |

Coverage scope and denominators are identical. Backend measures 547 files, 79,693 lines, and 25,754 branches. The measured loss is three lines and one branch: scan-job iteration in `form_submission_service.py` and websocket exception logging in `notification_service.py`. Frontend metrics, per-file counts, and covered locations are identical across all 799 measured source files.

[Exact current results](results.json), [backend comparison](refreshed-backend.json), [frontend comparison](refreshed-frontend.json). The original earlier-revision results remain in [original-results.json](original-results.json); their counts and source universe are historical, not the final baseline.

## CI implementation

- Backend: four parallel groups instead of two, with four workers per group. All 497 safe files run exactly once; 47 migration, outbox, and OPS CLI files run in the isolated serial group.
- Frontend: four shards instead of two. Fresh blob reports merge with existing coverage thresholds. Coverage merging can overlap the build; required `Frontend Tests` still requires both to succeed.
- Coverage reporting: remove one redundant text-report analysis pass. Retained XML and JSON commands each enforce the configured combined floor, followed by separate line/branch checks. The XML artifact and changed-line reporting remain.

Required check names, security scans, launch gates, production image checks, coverage floors, source scope, and test isolation remain intact. The partition test executes the actual selector; the frontend gate test executes all 16 dependency-result combinations. Passing results are never substituted from an earlier commit.

The first hosted candidate exposed a scheduling imbalance; the final fourth backend group reduces it. A concurrent merge run also exposed the OPS CLI global-row-count assertion racing with committed Jobs from another worker. Moving the intact OPS CLI suite into the serial group preserves its all-organization no-execution assertion. The failing test was retained. [Isolation review](ops-cli-serial-review.md), [coverage-report review](coverage-report-review.md).

## Hosted timing

| Run | Source | Total |
| --- | --- | ---: |
| [Baseline PR](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/actions/runs/37178647847) | `c4b69b8e7` | 5m41s |
| [Baseline main](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/actions/runs/37179205963) | `d881caa07` | 6m21s |
| [Final PR](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/actions/runs/37179543041) | `dbbc70a35` | 4m37s |
| [Final main](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/actions/runs/37179825258) | `875233006` | 4m23s |

Each pair has identical application/test/workflow source within that pair. Timing starts at workflow creation and ends at the last job completion, including runner queue time. Both pairs contain one PR and one main push; main omits the nonblocking changed-line report. Every final job passed. The observed median improvement is 25.2%, exceeding the 20% target. Four observational runs do not establish a guaranteed speedup under every runner load. Extra shard jobs increase runner demand. Human review and merge availability are outside this metric. [Raw timing summary](hosted-ci.json).

Main still requires branches to be up to date, so later merges can require CI reruns. Protection settings were not changed. GitHub documents merge queues for organization-owned repositories; this repository is personal-owned. [GitHub requirements](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).

## Tooling

Vitest and its coverage provider move from 5.0.1 to 5.0.3; jsdom from 29.1.1 to 30.1.1. TS7 was already current at stable 7.0.2; the TS6 API compatibility package remains. Runtime pins, release-age policy, trust policy, overrides, and dependency build allowlists are unchanged.

The original controlled 588-test sample improved local median time by 15.38% with cold transform caches and 13.57% with warm caches across three repetitions. These sample timings are separate from the hosted result. The proposed GitHub transform cache was dropped because warm-cache benefit was not demonstrated. Removing redundant backend text reporting reduced local reporting median from 14.17 to 10.15 seconds, with identical totals; XML and JSON each returned exit code 2 under a deliberately failing configured floor. [Toolchain evidence](toolchain.md), [test benchmark](toolchain-benchmark.json), [reporting benchmark](coverage-report-benchmark.json).

## Verification and cleanup

Full paired backend and frontend suites passed with no failures or skips. Candidate application/test type checks and lint passed. Hosted production builds, Docker artifacts, all test shards, merged coverage, and security gates passed. The focused OPS CLI and CI configuration run passed 27 tests; changed Python files passed Ruff and formatting checks.

Both backend runs emitted the same pre-existing SQLite connection ResourceWarning in `test_donor_approval_seed_is_idempotent_and_preserves_existing_stage_ids`. Full local suite timings were affected by concurrent host work and are not performance evidence. The skill's OpenClaw-specific scripts and autoreview were unavailable; repository checks and independent preservation reviews were used instead.

Pruning removes 306 net test lines; stronger existing CI guards add 56, for a net test reduction of 250 lines. Workflow changes add seven net lines. Production and shared test-support LOC changes are zero; dependency manifests and generated lockfiles are separate.

All audit databases, the detached baseline checkout, temporary symlink, and task-specific benchmark/uv caches were removed. No application server was started. The pre-existing `crm_db` service remains running. Raw logs remain in ignored `output/ci-test-audit-20261003.local/`; compact final evidence is recorded here.

Remaining test-count work requires further owner-by-owner audit. Named follow-ups include the pre-existing nested, uncollected `test_validate_update_status_action_normalizes` and query-invalidation assertion concerns in the ledgers. Uncollected declarations are not test-count reductions.
