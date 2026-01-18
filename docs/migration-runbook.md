# Staging Migration Runbook

This runbook defines the staging migration procedure and the idempotency check for `alembic upgrade head`.

## Preconditions
- Staging database backup completed.
- Staging environment variables configured (same as production).
- Maintenance window announced if needed.

## Procedure
1. Confirm current revision and head:
   ```bash
   cd apps/api
   .venv/bin/python -m alembic current
   .venv/bin/python -m alembic heads
   ```
2. Run the migration:
   ```bash
   .venv/bin/python -m alembic upgrade head
   ```
3. Idempotency check (required):
   ```bash
   .venv/bin/python -m alembic upgrade head
   .venv/bin/python -m alembic current
   ```
   - Expect no new migrations applied.
   - `alembic current` should match `alembic heads`.
4. Run smoke checks:
   - Health endpoint
   - Core list endpoints (surrogates, intended parents)
5. Record the run in the log below.

## Rollback
- Prefer restoring from the staging backup.
- Avoid `alembic downgrade` unless explicitly planned for that migration.

## Migration Run Log
| Date (UTC) | Environment | From Revision | To Revision | Result | Verified By | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |
