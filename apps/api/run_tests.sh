#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Always use disposable local data, never DATABASE_URL or libpq service settings
# inherited from a developer's environment. Matches the local Docker/orb cluster.
unset PGSERVICE PGSERVICEFILE PGHOSTADDR PGOPTIONS
export PGHOST=127.0.0.1 PGPORT="${TEST_DATABASE_PORT:-5432}"
export PGUSER=postgres PGPASSWORD=postgres PGCONNECT_TIMEOUT=5
if [[ ! "$PGPORT" =~ ^[0-9]+$ ]]; then
    echo 'TEST_DATABASE_PORT must be a local PostgreSQL port.' >&2
    exit 2
fi

mise exec -- uv sync --frozen --extra test --no-install-project

database="crm_test_$(date +%s)_$$"
createdb --no-password --maintenance-db=postgres "$database"
trap 'dropdb --no-password --maintenance-db=postgres --if-exists --force "$database"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
export DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:$PGPORT/$database"
export ENV=test TESTING=1

printf 'Testing in disposable database %s\n' "$database"
mise exec -- uv run -m alembic upgrade head
mise exec -- uv run -m pytest -v "$@"
