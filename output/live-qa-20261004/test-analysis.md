# Scheduling test-order failure

## Result

The full-suite failure is reproducible test-state pollution, not a reproduced failure of calendar preparation behavior. No production source or tests were changed.

| Execution | Result |
| --- | --- |
| Root full serial backend suite | 5,601 passed, 1 failed, 503 subtests passed; 370.08 seconds |
| Failing scheduling test alone in fresh database | 1 passed; 2.38 seconds |
| Calendar binding service + scheduling schema migration + entire scheduling preparation file | 20 passed; 2.56 seconds |
| Inbound concurrency test immediately followed by failing preparation test | 1 passed, 1 failed; 2.19 seconds |

## Cause

`tests/test_scheduling_inbound_concurrency.py::test_inbound_move_serializes_before_concurrent_staff_booking` creates committed calendar data visible to two database sessions. It calls `calendar_binding_service.sync_binding`, which persists an `ExternalCalendarEvent` projection.

Its `committed_inbound_race` fixture cleanup at `apps/api/tests/test_scheduling_inbound_concurrency.py:189` sets `session_replication_role = replica`, disabling foreign-key triggers and cascading deletes. The explicit cleanup model list includes `CalendarBinding`, `Organization`, and related fixtures but omits `ExternalCalendarEvent`. The projection survives after its binding and organization are removed.

The subsequent preparation test creates its own valid projection, then executes `db.query(ExternalCalendarEvent).one()` at `apps/api/tests/test_scheduling_prepare.py:193`. The leaked projection plus the test's own projection raises `MultipleResultsFound`. Its initial `CalendarBinding.one()` succeeds because the preceding fixture did delete its calendar binding.

The two-test command below reproduces the same failing test, assertion line, and exception as the full suite. The target passes in isolation, and the 20-test neighbor suite also passes.

## Retained coverage and proposed repair

Both tests protect valuable behavior and should remain:

- Inbound concurrency: a staff booking cannot commit a conflicting slot while inbound calendar reconciliation owns the lock.
- Preparation: operator preparation projects provider cancellation without cancelling the CRM appointment or firing workflows; normal synchronization subsequently applies cancellation and fires one workflow.

Repair the concurrency fixture cleanup to delete every committed row it creates, including `ExternalCalendarEvent`, before its parent rows. Scope the preparation assertion to its binding/event so the assertion describes its own fixture. Scoping alone would hide the orphan cleanup defect and is insufficient.

No repair was applied in this QA task. Re-run the two-test reproduction, then the full serial suite after the cleanup repair.

## Commands executed

All successful runs used `apps/api/run_tests.sh`; each creates, migrates, and drops a unique disposable database. The sandbox-only first attempt could not connect to loopback PostgreSQL, so subsequent commands used approved escalation for local test database access.

```sh
env PATH=/private/tmp/crm-live-qa-pg-bin:$PATH \
  UV_CACHE_DIR=/private/tmp/crm-live-qa-tests-uv-cache \
  apps/api/run_tests.sh \
  tests/test_scheduling_prepare.py::test_preparation_does_not_apply_google_cancellation_or_fire_workflows

env PATH=/private/tmp/crm-live-qa-pg-bin:$PATH \
  UV_CACHE_DIR=/private/tmp/crm-live-qa-tests-uv-cache \
  apps/api/run_tests.sh \
  tests/test_calendar_binding_service.py \
  tests/test_migration_20260922_scheduling_v2_schema.py \
  tests/test_scheduling_prepare.py

env PATH=/private/tmp/crm-live-qa-pg-bin:$PATH \
  UV_CACHE_DIR=/private/tmp/crm-live-qa-tests-uv-cache \
  apps/api/run_tests.sh \
  tests/test_scheduling_inbound_concurrency.py \
  tests/test_scheduling_prepare.py::test_preparation_does_not_apply_google_cancellation_or_fire_workflows
```

Temporary diagnostic logs were `/private/tmp/crm-live-qa-scheduling-isolated.log`, `/private/tmp/crm-live-qa-scheduling-focused.log`, and `/private/tmp/crm-live-qa-scheduling-order.log`. They were removed during cleanup. Raw failure logs included pytest fixture representations and were not copied into the report.
