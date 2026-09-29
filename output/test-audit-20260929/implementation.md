# Test audit implementation — 2026-09-29

Baseline: `ebb4c767e932c3f35ccaf6f2de15a087b1b4d03f`. Validated implementation: `62686881a73b5d76fd41cca4b02addee16b03693` on `main`. The [discovery report](report.md) records the removal criteria and retained tests.

## Changes

| Commit | Change |
| --- | --- |
| `733fe097` | Repair worker deferral coverage using a persisted running job and claim; remove the duplicate dispatch smoke test. |
| `c9a8cd8e` | Remove the narrower FastAPI dependency guard and global scan-image string check; retain the stronger guards and executable release tests. |
| `62686881` | Import the shared date parser directly; remove its delegating wrapper and duplicate helper assertions while retaining rendered timezone and rescheduling checks. |

Four redundant test cases were removed. One worker regression test was repaired. Production code changed by **−4 lines** and tests by **−38 lines**, including the stronger regression setup. The direct AI model-validation test and CI routing remain unchanged.

The repaired worker test reloads its database row and checks status, claim token, claim time, completion time, error and attempt count. Completion and failure services are real. Only claiming, the handler, heartbeat and unrelated schedulers are controlled by the test.

## Validation

| Check | Frozen baseline | Implementation |
| --- | ---: | ---: |
| Focused backend selection with coverage | 95 passed, 13.88 s | 92 passed, 13.63 s |
| Focused frontend selection with coverage | 65 passed, 4.61 s | 64 passed, 4.76 s |
| Incorrect-completion mutation | Old test survived in the discovery audit | Repaired test failed on `completed != running` |
| Frontend typecheck and focused ESLint | — | Passed |
| Ruff check and format check, three changed Python files | — | Passed |
| Git whitespace check | — | Passed |

The mutation replaced `if should_mark_completed:` with `if True:` only in the in-memory `worker_loop` function. Its expected failure proves that the repaired test detects an incorrect persisted completion. The normal backend run then passed against unchanged production worker code.

Backend coverage JSON contained the same 520 production files. Every file had identical executed-line sets, executed-branch sets and summary metrics. Covered lines remained **21,627 / 77,219**, and covered branches remained **463 / 24,924**.

Frontend coverage summaries were identical for all 747 unchanged production files. Only the edited component changed:

| InterviewAppointmentManager metric | Before | After | Uncovered before / after |
| --- | ---: | ---: | ---: |
| Lines | 133 / 142 | 132 / 141 | 9 / 9 |
| Statements | 156 / 179 | 155 / 178 | 23 / 23 |
| Functions | 37 / 42 | 36 / 41 | 5 / 5 |
| Branches | 291 / 334 | 291 / 334 | 43 / 43 |

The removed wrapper accounts for one covered line, statement and function. Aggregate frontend coverage changed by the same counts; uncovered totals did not increase. This comparison uses frontend summary counts, not exact location matching across shifted source lines.

These are focused selections measured over the configured production file universe. Coverage thresholds were set to zero for these comparison runs. They do not establish full-suite coverage or CI gate success. Timings are single observations, not evidence of a performance improvement.

Backend selection, run through `apps/api/run_tests.sh` in a new migrated disposable database for each invocation:

```text
tests/test_ai_response_validation.py
tests/test_worker_registry.py
tests/test_worker_job_dispatch_and_handlers.py
tests/test_fastapi_conventions_signatures.py
tests/test_terraform_scan_job_config.py
tests/test_resend_readiness_orchestration.py::test_worker_executes_organization_readiness_check
tests/test_resend_readiness_orchestration.py::test_worker_executes_platform_readiness_check
tests/test_fastapi_conventions_response_contracts.py
tests/test_fastapi_openapi_contract.py
tests/test_release_ci.py
--cov=app --cov-branch --cov-fail-under=0
```

Frontend selection, run from `apps/web` with `mise exec -- pnpm test`:

```text
tests/scheduling-time.test.ts
tests/interview-appointment-presentation.test.ts
tests/interview-appointment-manager.test.tsx
--coverage
--coverage.thresholds.lines=0 --coverage.thresholds.statements=0
--coverage.thresholds.branches=0 --coverage.thresholds.functions=0
```

The repository-pinned runtimes and dependency lockfiles were retained. Separate baseline and candidate coverage files prevented result mixing. No source or test edits occurred during either runner invocation.

## Independent review

OpenClaw `autoreview`, pinned to `c4461b537ce3df1ed8d313a454a70b98ce8a5230`, reviewed the local patch with GPT-6.1 Sol at high reasoning effort. Result: **scoped-clean; no actionable P0–P2 findings**. The reviewer assessed the patch and supplied validation evidence; it did not execute project tests and reported that unchanged fixtures and guards were unavailable for independent inspection.

## Cleanup and delivery

All disposable `crm_test_*` databases were removed. Temporary mutation code, PostgreSQL client shims, coverage files, logs and the temporary review installation were removed after recording this evidence. No app server or general worker was started. Pre-existing local containers remain running.

Changes were committed locally. Full suites, production QA, push, PR, merge and deployment were outside this implementation pass.
