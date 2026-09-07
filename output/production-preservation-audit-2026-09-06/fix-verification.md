# Preservation fixes

The audited defects are fixed in the working tree. Production release still requires the baseline, data-copy, and cutover checks in [the rollout procedure](/Users/chason/GenAI-assited-CRM-Tool/docs/match-integration-rollout.md). No production resource was accessed, no deployment was performed, and no changes were committed.

| Finding | Correction | Verification |
|---|---|---|
| Historical match work disappears | Show unassigned participant history with record attribution; exclude explicitly different-case work and omit record history under attempt filters. | API isolation, pagination, permission, and rendered attribution tests. |
| Closure-only downgrade loss | Guard every populated closure field before removing columns. | Each closure field has a downgrade-refusal regression. |
| Concurrent downgrade loss | Lock every affected table before checking history; retain locks through DDL. | Two-connection regressions cover all three downgrade guards. |
| Donor legal holds miss match history | Resolve holds through case parties and held case work, using shared aliases. | Full purge and cross-organization regressions; direct IP alias hold blocks hard deletion. |
| Purge races or cascades away dependent history | Preserve dependent history; lock candidate records and recheck eligibility before deletion. | Concurrent attempt insertion survives a waiting purge. |
| Hold creation races destructive operations | Hold creation/release, purge, and hard deletion share a transaction advisory lock per organization. Hold changes and audit commit atomically. | Concurrent hold-versus-purge and hold-versus-delete tests; audit failure rolls back hold changes. |
| Unknown legacy closure age | Retain closed cases with unknown closure dates. | Old and recently updated NULL-closure fixtures remain preserved. |
| Hard-delete constraint failures | Return 409 for retained case history or legal holds; recheck archived state under lock. | IP/surrogate deletion and negative cases. |
| Existing commitment conflicts | Read-only release preflight plus a locked migration check; abort without reclassifying or deleting cases. | Conflict regression preserves both cases and the original schema revision. |
| Standalone migration timeout gap | Each migration sets its own timeout budgets in both directions. | Starting from intermediate revisions is covered. |
| Mixed-version writes/readiness | New features default off; checked expansion preflight, explicit rollout mode, temporary old-code readiness compatibility, and restoration on successful deployment/retry. | Gate tests preserve ordinary surrogate operations and existing expanded reads; deployment configuration tests pass. |
| Appointment ownership/access mismatch | Preserve authorized legacy owner lifecycle; new associations retain record, tenant, activation, and open-case checks. | Owner/admin, nonowner/cross-org, archived read/write, and appointment linkage tests. |

## Final validation

- **2,934 non-migration API tests passed** in 115.39 seconds: [output](./fix-results/api.txt).
- **67 migration tests passed** in 19.35 seconds: [output](./fix-results/migrations.txt).
- **1,503 frontend tests passed**, plus typecheck and ESLint: [output](./fix-results/frontend.txt).
- Ruff passed across backend application, tests, and changed migrations. Diff whitespace checks passed.
- Checked release migration preflight and an idempotent upgrade passed against a disposable database at the expanded revision.
- Cloud Build YAML parsed and its Bash steps passed syntax validation. Cloud Build itself was not executed.
- React Doctor's focused review reported existing warnings; its remote score was unavailable. No live browser session was run in this fix pass; rendered UI states were verified by component tests.

## Remaining deployment gates

1. Verify the deployed code and database revisions. An older or unknown database baseline is deliberately rejected by the checked release command.
2. Rehearse this exact source revision against a representative sanitized production copy, including backup recovery, preserved fields/links, history visibility, roles, query latency, and lock duration under load.
3. Use the explicit expansion release path. Keep new writes disabled until compatible APIs/workers are ready and old execution is drained. Activate workers, then APIs, then release the frontend.
4. Retain the expanded schema during rollback. Use a compatible application revision or a forward fix; do not restore an old backup over newer writes.

The original audit report, probe source, and probe results describe the pre-fix revision. Current regression tests and the results above supersede those failure reproductions for verification.

## Cleanup

Only disposable PostgreSQL databases were used. No API/frontend servers, workers, browser sessions, or external provider delivery were started for this fix pass.

The disposable container and both test databases were removed after verification. No service is intentionally left running.
