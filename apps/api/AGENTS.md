# Backend guidance

Read the repository-root `AGENTS.md` first. This file adds only API-specific context.

## Boundaries and ownership

- Derive tenant scope from authenticated membership. Public token flows must derive scope from the validated token or its bound resource, never from a client-supplied organization id.
- Use the centralized dependencies in `app/core` and existing router patterns for membership, roles, and CSRF. Add denied and cross-organization tests for new protected operations.
- Keep routers focused on transport and dependency wiring. Put use-case logic in services.
- Make transaction ownership explicit. A use case that writes domain state plus audit/activity records must commit or roll back atomically; do not split transaction control across layers without a documented reason.
- Preserve timezone-aware UTC and existing Pydantic v2 / SQLAlchemy 2.0 idioms. Match neighboring production code rather than copying generic examples.
- Never log raw PII, message bodies, provider credentials, or tokens. Keep provider failures sanitized at the API boundary.

## Migrations and generated contracts

- Use Alembic revision ids and filenames in `YYYYMMDD_HHMM_<slug>` form.
- Inspect the generated migration before running it. Cover upgrade behavior and schema invariants in tests.
- Follow `../../docs/migration-runbook.md` for recovery, consolidation, or baseline work. Do not perform a baseline reset as part of an ordinary schema change.
- When backend stage or surrogate contracts change, run the existing generators and include the synchronized frontend outputs in the same logical change.

## Verification

Set up with `uv sync --extra test`. Run focused tests while iterating and `uv run -m pytest -v` for cross-cutting API changes. Run Ruff for changed Python surfaces and include explicit negative tests for tenancy, authorization, CSRF, idempotency, and retry behavior when relevant.

Do not start Postgres, workers, or the API server unless the verification step needs them. Track and stop only the processes started for the task.
