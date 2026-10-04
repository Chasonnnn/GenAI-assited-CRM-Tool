# Automated validation

Revision `65bca746e7e90b0da768e31dc06691c589eb07fb`; 2026-10-04. No production source or tests changed during validation.

| Check | Result |
| --- | --- |
| `cd apps/web && mise exec -- pnpm run check` | Passed |
| Next route type generation and TypeScript source check | Passed |
| TypeScript test check | Passed |
| ESLint | Passed |
| Vitest | 385 files, 3,038 tests passed |
| `apps/api/run_tests.sh` full serial suite | 5,601 passed, 1 failed, 503 subtests passed; 370.08 seconds |
| Scheduling preparation failure alone | 1 passed |
| Calendar service, migration, preparation subset | 20 passed |
| Concurrency test followed by preparation target | 1 passed, 1 failed; reproduced the same failure |

The backend failure is a test-fixture cleanup leak: a committed concurrency fixture disables cascading deletes and leaves an external calendar projection. The next test's unscoped `.one()` sees two rows. [Reproduction and proposed repair](test-analysis.md).

Each backend invocation used the repository runner, which creates and migrates a unique disposable database and drops it on exit. Temporary local `createdb`/`dropdb` adapters were needed because those command-line binaries were absent. The adapters accept only the runner's `crm_test_<pid>_<random>` names and connect to local PostgreSQL. The shared QA database was not used by the tests.

Dependencies were installed from the existing frozen pnpm lockfile. Repository-pinned Mise runtimes were used. No dependency or lockfile change was retained.
