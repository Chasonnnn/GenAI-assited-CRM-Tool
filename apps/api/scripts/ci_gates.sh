#!/usr/bin/env bash
# Backend gates that need no database: FastAPI conventions, one Alembic head, Ruff.
# CI runs this script; .githooks/pre-push runs it before each push.
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v mise >/dev/null 2>&1; then
    uv_run=(mise exec -- uv run)
else
    uv_run=(uv run)
fi

PYTHONPATH=. "${uv_run[@]}" -m pytest -v --tb=short \
    tests/test_fastapi_conventions_signatures.py \
    tests/test_fastapi_conventions_ellipsis.py \
    tests/test_fastapi_conventions_response_contracts.py \
    tests/test_fastapi_conventions_router_mounts.py \
    tests/test_fastapi_conventions_async_sync.py \
    tests/test_fastapi_openapi_contract.py \
    tests/test_router_model_imports.py \
    tests/test_router_service_boundaries.py

# `alembic heads` reads settings but does not connect to the database.
heads="$(DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@127.0.0.1:5432/unused}" \
    ENV="${ENV:-test}" "${uv_run[@]}" -m alembic heads)"
head_count="$(grep -c '(head)' <<<"$heads" || true)"
if [[ "$head_count" != 1 ]]; then
    printf 'Expected exactly one Alembic head, found %s:\n%s\n' "$head_count" "$heads" >&2
    exit 1
fi

"${uv_run[@]}" ruff check .
"${uv_run[@]}" ruff format --check .
