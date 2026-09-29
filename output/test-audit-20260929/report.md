# Test audit — 2026-09-29

Audit baseline: `3c9dfd107492e37a16ec41fef1940cfa6c95a955` on `main`.

One confirmed test gap needs repair. Four bounded cleanup candidates have named retained coverage. Production and test files remain unchanged; no tests were deleted. This is a focused audit, not an exhaustive removal campaign.

## Skill installation

- Installed `test-audit` at `/Users/chason/.codex/skills/test-audit` using the Codex skill installer.
- Source: [OpenClaw test-audit](https://github.com/openclaw/openclaw/tree/c4461b537ce3df1ed8d313a454a70b98ce8a5230/.agents/skills/test-audit), pinned revision `c4461b537ce3df1ed8d313a454a70b98ce8a5230`.
- Installed files: `SKILL.md` and `CAMPAIGN.md`; upstream contents were not modified.
- `SKILL.md` SHA-256: `01c421239797a8950fe1287f293d2e05f127e69ac457d1b9cdf9b296ac77eacd`.
- Applied audit mode with parallel backend, frontend, and contract/CI discovery. OpenClaw-specific commands were replaced by this repository's `AGENTS.md` commands. No code-edit, release, or PR workflow was invoked.

## Current test surface

| Measure | Observed at baseline |
| --- | ---: |
| Backend `test_*.py` files | 509 |
| Backend statically declared `test_*` functions | 3,839 |
| Frontend `.test.*` / `.spec.*` files | 365 |

Function declarations are not collected cases: parametrization and native subtests expand them. This audit did not collect or run the entire suite. Prior audit counts and coverage measurements were not reused as current results.

## Repair first: worker completion-deferral test can pass incorrectly

**Location:** [`test_worker_loop_leaves_job_running_when_handler_defers_completion`](../../apps/api/tests/test_worker_job_dispatch_and_handlers.py#L1677), lines 1677–1725.

The test intends to protect a worker contract: a handler returning `False` delegates completion and must leave the job running. It patches `job_service.mark_job_completed`, but the production loop now invokes `complete_claimed_job` at [`worker.py:1174`](../../apps/api/app/worker.py#L1174). Its fabricated `SimpleNamespace` job has no persisted row.

**Demonstrated failure to detect a regression:** a temporary pytest plugin replaced only `if should_mark_completed:` with `if True:` in the in-memory `worker_loop` function. A recording wrapper counted calls to the real completion function. The existing test still passed, and the instrumented run recorded **one completion attempt**. No tracked source file was changed.

The completion update finds no database row and raises `JobClaimLost`; failure handling also finds no row, and the outer loop catches that exception. The fabricated object's status stays `running`, and the counter on the obsolete helper stays zero. Both final assertions pass for the wrong reason.

| Evidence field | Finding |
| --- | --- |
| Production owner/callers | `worker.worker_loop`, started by `worker.main`; calls `process_job`, then claim-aware job completion/failure services. |
| Stronger retained proof | Existing claim-fencing tests protect stale claims, but do not replace the distinct handler-deferral contract. Retain and repair this test. |
| History | `5aa4af6a` introduced the remote-scan deferral test; `a51a8832` moved completion to claim-aware updates. |
| Recommended repair | Persist a running job with its claim, exercise the loop with a deferring handler, reload the row, and assert no completion/failure transition. Prove the corrected test fails under the same mutation and passes on unmodified production code. |
| Deletion unlocked | None. This is a valuable contract with an ineffective test. |
| Risk | Test coverage gap confirmed; no production deferral bug demonstrated. |
| Focused validation | `apps/api/run_tests.sh tests/test_worker_job_dispatch_and_handlers.py::test_worker_loop_leaves_job_running_when_handler_defers_completion`, followed by the worker/claim sibling tests and the mutation witness. |

## Cleanup candidates

### 1. Remove the interview date-parser wrapper and duplicated helper assertion

**Tests:** [`interview-appointment-presentation.test.ts:30`](../../apps/web/tests/interview-appointment-presentation.test.ts#L30), `converts a browser-local date-time to a timezone-aware ISO instant`; helper assertion in [`interview-appointment-manager.test.tsx:318`](../../apps/web/tests/interview-appointment-manager.test.tsx#L318), inside `uses the viewer timezone for both the summary and editor, not the client timezone`.

| Evidence field | Finding |
| --- | --- |
| Actual detected failure | The presentation case rejects empty input and malformed ISO shape, but permits any hour across two dates. The manager's helper assertion detects only a null result for a synthetic date; it does not assert editor submission. |
| Production owner/callers | [`InterviewAppointmentManager.tsx:91–93`](../../apps/web/components/surrogates/InterviewAppointmentManager.tsx#L91) exports a delegation wrapper over `lib/scheduling-time`. Only those two tests import the wrapper externally. Internal submit/readiness paths call it at lines 221 and 271. Other appointment/stage components already import the shared helper directly. |
| Stronger retained proof | [`scheduling-time.test.ts:20`](../../apps/web/tests/scheduling-time.test.ts#L20), `rejects invalid normalized dates before an override is submitted`, checks exact valid conversion, empty input, invalid date normalization, invalid clock time and missing time. Retain the manager's real rendered timezone assertions and its past-date/custom-reschedule tests at lines 277 and 294. |
| History | `f27d4d329` introduced the component-owned parser; `81f6a21a3` extracted the canonical helper and regression while leaving the wrapper. |
| Deletion unlocked | Three-line production wrapper and its alias; one presentation case, one standalone helper assertion, obsolete imports and synthetic local/pad setup. Keep all real UI assertions. |
| Risk | Low. Import the shared helper directly; do not change parsing behavior or the manager's UI flow. |
| Focused validation | `cd apps/web && mise exec -- pnpm test tests/scheduling-time.test.ts tests/interview-appointment-presentation.test.ts tests/interview-appointment-manager.test.tsx`; after edits, typecheck and focused ESLint. |

The exact presentation-case exclusion replay passed **64 tests with 1 skipped**, versus **65 passed** before exclusion. The partial assertion and wrapper were not edited; this replay does not validate a completed refactor.

### 2. Remove a duplicate worker dispatch smoke test

**Test:** [`test_worker_process_job_dispatch`](../../apps/api/tests/test_worker_job_dispatch_and_handlers.py#L561), lines 561–572.

| Evidence field | Finding |
| --- | --- |
| Actual detected failure | Failure to await exactly one handler with the supplied job. Replacing the resolver with the same stub for every job type means it cannot detect broken campaign registration. |
| Production owner/callers | `worker.process_job:597–602`, called by `worker_loop:1169`; real handler selection belongs to `jobs.registry.resolve_job_handler`. |
| Stronger retained proof | [`test_process_job_uses_registry`](../../apps/api/tests/test_worker_registry.py#L270) checks resolver arguments. [`test_worker_executes_organization_readiness_check`](../../apps/api/tests/test_resend_readiness_orchestration.py#L165) and [`test_worker_executes_platform_readiness_check`](../../apps/api/tests/test_resend_readiness_orchestration.py#L436) preserve the real registry/handler and check exactly one service invocation with the correct database/scope and a `True` completion decision. They do not prove a persisted job-completion transition. |
| History | Added in `285ea7f5`, after the registry test from `366ce29b`; real dispatch proofs arrived in `6b9c510d`. |
| Deletion unlocked | One 12-line test. `_job` remains in use; no production/support deletion. |
| Risk | Low; the candidate supplies no campaign-specific proof. |
| Focused validation | `apps/api/run_tests.sh tests/test_worker_registry.py tests/test_worker_job_dispatch_and_handlers.py tests/test_resend_readiness_orchestration.py::test_worker_executes_organization_readiness_check tests/test_resend_readiness_orchestration.py::test_worker_executes_platform_readiness_check`. |

### 3. Remove a strictly subsumed FastAPI signature guard

**Test:** [`test_route_depends_params_are_typed_and_not_dict_session`](../../apps/api/tests/test_fastapi_conventions_signatures.py#L71), lines 71–96.

| Evidence field | Finding |
| --- | --- |
| Actual detected failure | A scanned decorated route argument has default `Depends(...)` with no annotation or literal `dict`. It does not inspect types inside `Annotated[...]` or identify session dependencies specifically. |
| Production owner/callers | Registered HTTP routers under `app/routers`; `app/main.py` mounts them. Test-local AST helpers have no production callers. |
| Stronger retained proof | Same file, [`test_route_params_use_annotated_for_fastapi_param_calls:50–68`](../../apps/api/tests/test_fastapi_conventions_signatures.py#L50). Both tests use identical files, function selection, argument/default pairing and call-name logic. `Depends` is in `PARAM_CALLS`; both missing and literal `dict` annotations fail the retained `Annotated` predicate. Every actual rejection is therefore included in the retained guard. |
| History | Both guards entered together in `8073aaec`; the narrower guard adds diagnostic wording but no distinct accepted/rejected input. |
| Deletion unlocked | One 26-line test; shared helpers remain necessary. No production/support deletion. |
| Risk | Low for the actual predicate. Existing gaps in argument/default pairing and inner-type checking remain separate issues. |
| Focused validation | `apps/api/run_tests.sh tests/test_fastapi_conventions_signatures.py tests/test_fastapi_conventions_response_contracts.py tests/test_fastapi_openapi_contract.py`. |

### 4. Remove a subsumed scan-image string-presence test

**Test:** [`test_cloudbuild_updates_attachment_scan_job_image`](../../apps/api/tests/test_terraform_scan_job_config.py#L100), lines 100–104.

| Evidence field | Finding |
| --- | --- |
| Actual detected failure | Absence anywhere in Cloud Build configuration of the scan-job substitution/update command or worker-image argument. It never binds the image argument to the scan-job update. |
| Production owner/callers | [`cloudbuild/api.yaml:173–203`](../../cloudbuild/api.yaml#L173), loaded by the Terraform API build trigger on version tags. |
| Stronger retained proof | Same file: `test_cloudbuild_updates_compatible_scan_runner_before_claim_producers:107–114` requires the identical scan update token and adds ordering; `test_cloudbuild_preserves_worker_configuration_and_repairs_monitoring_identity:166–181` requires the same image token inside the worker update; `test_cloudbuild_resolves_and_deploys_one_digest_image_set:117–139` adds immutable-image guarantees. These entail every existing assertion. |
| History | `5aa4af6a` added the scan update check. `7753d011` weakened it to global strings while adding the stronger ordering guard. `9f5f62c6` added digest-set protection. |
| Deletion unlocked | One five-line test; `_read` and all operational contracts remain. No production/support deletion. |
| Risk | Low. Neither the old check nor its removal proves that the scan update itself receives the image. Do not overstate that contract. |
| Focused validation | `apps/api/run_tests.sh tests/test_terraform_scan_job_config.py tests/test_release_ci.py`; release tests execute deployment shell against recording `gcloud` stubs, not the real provider. |

Exact-node exclusions for candidates 2–4 passed **92 tests with 3 deselected**, including retained worker, response/OpenAPI and executable release proofs. No deletion or coverage-equivalence claim follows from this focused replay alone.

## Retained and deferred findings

- Keep the direct `validate_model` success test for now. Its assertions overlap the list-validator test's current internal call, but they name separate single-item and list contracts. Removing four lines offers little benefit and makes the direct contract rely on list implementation structure.
- Keep source-based architecture, generated-contract, migration, tenant-isolation, CSRF, retry, idempotency, packaging and release guards when they enforce an independent rule. Successful endpoint/build tests do not replace these contracts.
- Keep Base UI import guards, query retry behavior, appointment end-boundary behavior and independent contrast checks.
- Next adoption documentation assertions are brittle, but their history explicitly retains safety/configuration gates. They require further contract review, not automatic deletion.
- Eight FastAPI gate files run in both the parallel-safe backend matrix and the dedicated `Backend FastAPI Gates` job. This is a CI routing candidate. Preserve required-check semantics and aggregate coverage before removing duplicate execution; no runtime savings were measured here.

## Verification

| Run | Result |
| --- | --- |
| Backend candidate/owner baseline | 74 passed in 3.44 s |
| Frontend scheduling/interview baseline | 65 passed in 2.74 s |
| Worker wrong-completion mutation | Existing test still passed; one real completion attempt recorded |
| Expanded backend exact-case exclusion replay | 92 passed, 3 deselected in 5.06 s |
| Frontend exact-case exclusion replay | 64 passed, 1 skipped in 2.55 s |

The backend runs cover 95 distinct unmodified test cases across the baseline and expanded replay; the frontend runs cover 65. Repeated cases and the intentionally surviving mutation are not additional passing coverage. Full suites, full coverage comparison, and production QA were not run for this audit.

The backend baseline selected these files under `apps/api/tests`: `test_ai_response_validation.py`, `test_worker_registry.py`, `test_worker_job_dispatch_and_handlers.py`, `test_fastapi_conventions_signatures.py`, `test_terraform_scan_job_config.py`, plus the two exact readiness node IDs listed in candidate 2. The expanded replay added `test_fastapi_conventions_response_contracts.py`, `test_fastapi_openapi_contract.py` and `test_release_ci.py`, with these runner arguments:

```text
--deselect tests/test_worker_job_dispatch_and_handlers.py::test_worker_process_job_dispatch
--deselect tests/test_fastapi_conventions_signatures.py::test_route_depends_params_are_typed_and_not_dict_session
--deselect tests/test_terraform_scan_job_config.py::test_cloudbuild_updates_attachment_scan_job_image
```

The frontend baseline used the three files in candidate 1. The replay added `-t '^(?!.*converts a browser-local date-time to a timezone-aware ISO instant)'`. Mutation runs selected only the worker-deferral test, loaded the temporary plugin with `-p audit_deferral_mutation`, and enabled output with `-s`.

Backend runs used `apps/api/run_tests.sh` with temporary Docker-backed PostgreSQL client shims against the existing local PostgreSQL 18.1 container. Each invocation created, migrated and dropped a unique `crm_test_*` database. No app server or general worker was started. Cleanup verified zero remaining `crm_test_*` databases; the task-owned mutation plugin, shims, bytecode and logs were removed. Existing local containers were left running.

Current coverage gates were verified from source:

| Gate | Floor |
| --- | --- |
| Backend combined coverage | 75.85% |
| Backend lines / branches in merged CI | 79.96% / 63.03% |
| Frontend lines / statements / branches / functions | 62.07% / 60.04% / 57.05% / 52.11% |

Per-shard thresholds are disabled intentionally; aggregate jobs require successful producer jobs and enforce the merged floors. The backend aggregator also rejects empty measurement totals. Backend changed-line coverage at 90% is non-blocking. These are configured thresholds, not newly measured coverage.

## Proposed order

1. Repair the worker deferral test and prove the same mutation is rejected.
2. Remove the interview wrapper and duplicate helper assertions as one small change.
3. Remove the three subsumed backend tests with retained owner tests and coverage comparison.
4. Evaluate duplicate CI execution separately with measured runtime and required-check review.

Production LOC changed: **0**. Test/support LOC changed: **0**. Documentation only. No branch, push, PR, merge, deployment or production activation.
