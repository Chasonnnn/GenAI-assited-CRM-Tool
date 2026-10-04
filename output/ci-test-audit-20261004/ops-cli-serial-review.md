# OPS CLI isolation and fourth backend shard review

Result: approve the proposed routing changes. No blocking finding. Read-only review at `9e09e4b28e55c7894c232ac382ce1521bff14a46`; no tests or installs run and no source files edited.

## Failure evidence

- Hosted run `37178731080` failed `test_bundle_publish_roundtrip_and_no_execution` at `test_ops_cli_integration.py:198`. The assertion compares database-wide counts of `AutomationWorkflow`, `EmailTemplate`, `Form`, and `Job` before and after platform template publication. The log records the failing Boolean, not individual table counts.
- From 05:06:26.908 to 05:06:27.732 UTC, that test ran on `gw1` while `test_ai_email_permissions_v2.py::test_v2_email_delivery_rechecks_current_authority` ran on `gw0`. This is recorded in `concurrent-main-ci-failure.log:2766-2783`.
- The concurrent tests use `queued_email` and `committed_approval` from `test_ai_action_transactions.py:67-186,614-622`. These fixtures intentionally use independent `SessionLocal(bind=db_engine)` transactions. Approval creates a committed `Job`; cleanup deletes its organization and commits, cascading to jobs through `models/jobs.py:77-79`.
- The CLI's `db` fixture wraps its own connection in an outer transaction and savepoints (`tests/conftest.py:74-108`). The engine sets no stronger isolation level (`app/db/session.py:8-39`). Savepoints protect rollback of the fixture's writes; they do not make repeated global reads independent of other committed sessions. The concurrent writer is a concrete interference path, although the log cannot prove which count changed.
- The global no-execution assertions were present in the original CLI commit `db3eaab54` and are unchanged. `platform_template_write_service.py` writes platform template, target, and audit models; the four counted tenant execution models are intentionally outside its write contract. Narrowing the assertion to one organization would weaken the all-organization publication guarantee.

## Proposed routing

Move the entire `test_ops_cli_integration.py` file into the existing serial group, retaining all 13 parameterized test cases and every assertion. Add the filename to the Python partitioner's exclusions, add its explicit parallel pytest `--ignore`, and include it in the serial pytest command. Expand the existing comment to include global side-effect assertions.

Extend the current partition fixture with `tests/test_ops_cli_integration.py`. Extend the existing serial-routing assertion to check both the outbox and CLI filenames, the serial condition, and absence of xdist. No new replacement behavior test is needed.

Static inventory contains 544 test files: 47 serial files, including this CLI file, and 497 safe files. All serial files are at the tests root, so the current explicit filenames and migration glob cover the proposed exclusion set exactly.

## Fourth backend parallel group

Adding `parallel-4` and changing the sorted-file stride to four produces groups of 125, 124, 124, and 124 files. Static enumeration found complete unique coverage of the 497 safe files and no overlap with the serial set. Update the matrix assertion to four parallel groups plus serial; its six safe fixture files exercise all four partitions and still detect duplicates or omissions.

Each group keeps its own PostgreSQL service and four xdist workers. The matrix-result gate, wildcard artifact download, unique coverage filenames, combined coverage floor, and explicit line/branch floors already accommodate the additional group. A failed, cancelled, or skipped group cannot pass the required aggregate check.

The parent reports frozen duration sums of 211.8/185.7/272.9 seconds for three groups and 102.5/200.4/171.2/196.2 seconds for four. Those sums support trying the simpler fourth group; they are not measured hosted wall times. This adds one runner, one database/setup sequence, and four parallel worker processes at peak. Hosted timing must establish the final end-to-end gain and any queue contention.

Reviewed pre-change SHA-256: workflow `26d05acb01fd772ad55796ab30a0641ca7cc164fee769f7538dcc5c5dc225f85`; CLI test `4a1e16904c9bc9d4fe738452b725061a7162e1123cb18c1dcfd67ecce642b992`; CI tests `94270beff1dfa18a853a423dca13a77be1ef753cb27100e39952ffea8a6617f9`.
