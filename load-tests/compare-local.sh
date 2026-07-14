#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_REF="${1:-origin/main}"
CANDIDATE_REF="${2:-HEAD}"
RESULTS_DIR="${PERF_RESULTS_DIR:-${ROOT_DIR}/apps/api/performance/artifacts/load-latest}"
PERF_DB_PORT="${PERF_DB_PORT:-55432}"
PERF_DB_CONTAINER="crm_perf_db_${PPID}"
COMPOSE_PROJECT="crm-perf-${PPID}"
DEV_SECRET="local-performance-secret"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/crm-query-performance.XXXXXX")"
BASE_DIR="${TMP_DIR}/base"
CANDIDATE_DIR="${TMP_DIR}/candidate"
BASE_API_PID=""
CANDIDATE_API_PID=""

compose() {
    PERF_DB_PORT="${PERF_DB_PORT}" PERF_DB_CONTAINER="${PERF_DB_CONTAINER}" \
        docker compose \
        --project-name "${COMPOSE_PROJECT}" \
        --file "${ROOT_DIR}/docker-compose.yml" \
        --file "${ROOT_DIR}/docker-compose.performance.yml" \
        "$@"
}

cleanup() {
    local status=$?
    trap - EXIT INT TERM
    if [[ -n "${BASE_API_PID}" ]]; then kill "${BASE_API_PID}" 2>/dev/null || true; fi
    if [[ -n "${CANDIDATE_API_PID}" ]]; then kill "${CANDIDATE_API_PID}" 2>/dev/null || true; fi
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    git -C "${ROOT_DIR}" worktree remove --force "${BASE_DIR}" >/dev/null 2>&1 || true
    git -C "${ROOT_DIR}" worktree remove --force "${CANDIDATE_DIR}" >/dev/null 2>&1 || true
    rm -rf "${TMP_DIR}"
    exit "${status}"
}
trap cleanup EXIT INT TERM

for command in docker git uv curl k6; do
    if ! command -v "${command}" >/dev/null 2>&1; then
        echo "Missing required command: ${command}" >&2
        exit 2
    fi
done

mkdir -p "${RESULTS_DIR}"
git -C "${ROOT_DIR}" worktree add --detach "${BASE_DIR}" "${BASE_REF}" >/dev/null
git -C "${ROOT_DIR}" worktree add --detach "${CANDIDATE_DIR}" "${CANDIDATE_REF}" >/dev/null

compose up --detach --wait db
for database in perf_base perf_candidate; do
    compose exec -T db createdb --username postgres "${database}"
    compose exec -T db psql --username postgres --dbname "${database}" \
        --set ON_ERROR_STOP=1 --command "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;" >/dev/null
done

database_url() {
    local database=$1
    printf 'postgresql+psycopg://postgres:postgres@127.0.0.1:%s/%s' "${PERF_DB_PORT}" "${database}"
}

prepare_checkout() {
    local checkout=$1
    local database=$2
    (
        cd "${checkout}/apps/api"
        uv sync --extra test --frozen
        DATABASE_URL="$(database_url "${database}")" ENV=dev \
            uv run -m alembic upgrade head
    )
}

prepare_checkout "${BASE_DIR}" perf_base
prepare_checkout "${CANDIDATE_DIR}" perf_candidate

seed_checkout() {
    local checkout=$1
    local database=$2
    local profile_supported=$3
    (
        cd "${checkout}/apps/api"
        if [[ "${profile_supported}" == "1" ]]; then
            DATABASE_URL="$(database_url "${database}")" ENV=dev SEED_PROFILE=production \
                SEED_REDACT_SUMMARY=1 uv run python -m scripts.seed_mock_data
        else
            DATABASE_URL="$(database_url "${database}")" ENV=dev \
                SEED_RANDOM_SEED=20260713 SEED_SURROGATES=5000 \
                SEED_INTENDED_PARENTS=500 SEED_MATCH_COUNT=1000 \
                SEED_REDACT_SUMMARY=1 uv run python -m scripts.seed_mock_data
        fi
    ) >"${RESULTS_DIR}/${database}-seed.log" 2>&1
}

PROFILE_SUPPORTED=0
if [[ -f "${BASE_DIR}/apps/api/scripts/performance/profiles.py" \
      && -f "${CANDIDATE_DIR}/apps/api/scripts/performance/profiles.py" ]]; then
    PROFILE_SUPPORTED=1
fi
seed_checkout "${BASE_DIR}" perf_base "${PROFILE_SUPPORTED}"
seed_checkout "${CANDIDATE_DIR}" perf_candidate "${PROFILE_SUPPORTED}"

start_api() {
    local checkout=$1
    local database=$2
    local port=$3
    local log_file=$4
    (
        cd "${checkout}/apps/api"
        ENV=dev DATABASE_URL="$(database_url "${database}")" DEV_SECRET="${DEV_SECRET}" \
            JWT_SECRET="local-performance-jwt-secret-at-least-32-characters" \
            API_BASE_URL="http://127.0.0.1:${port}" FRONTEND_URL="http://127.0.0.1:3000" \
            CORS_ORIGINS="http://127.0.0.1:3000" \
            uv run -- uvicorn app.main:app --host 127.0.0.1 --port "${port}"
    ) >"${log_file}" 2>&1 &
    echo $!
}

BASE_API_PID="$(start_api "${BASE_DIR}" perf_base 18080 "${RESULTS_DIR}/base-api.log")"
CANDIDATE_API_PID="$(start_api "${CANDIDATE_DIR}" perf_candidate 18081 "${RESULTS_DIR}/candidate-api.log")"

wait_for_api() {
    local port=$1
    for _ in $(seq 1 90); do
        if curl --silent --show-error --fail "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    echo "API on port ${port} did not become healthy" >&2
    return 1
}
wait_for_api 18080
wait_for_api 18081

developer_id() {
    local database=$1
    compose exec -T db psql --username postgres --dbname "${database}" --tuples-only --no-align \
        --command "SELECT u.id FROM users u JOIN memberships m ON m.user_id = u.id WHERE m.role = 'developer' AND m.is_active IS TRUE ORDER BY u.created_at LIMIT 1;" \
        | tr -d '[:space:]'
}

login_cookie() {
    local port=$1
    local user_id=$2
    local headers_file=$3
    curl --silent --show-error --dump-header "${headers_file}" --output /dev/null \
        --request POST --header "X-Dev-Secret: ${DEV_SECRET}" \
        "http://127.0.0.1:${port}/dev/login-as/${user_id}"
    awk 'BEGIN { IGNORECASE=1 } /^Set-Cookie:/ { sub(/^Set-Cookie:[[:space:]]*/, ""); split($0, parts, ";"); cookies[++count]=parts[1] } END { for (i=1; i<=count; i++) printf "%s%s", (i>1 ? "; " : ""), cookies[i] }' \
        "${headers_file}"
}

BASE_COOKIE="$(login_cookie 18080 "$(developer_id perf_base)" "${TMP_DIR}/base-headers")"
CANDIDATE_COOKIE="$(login_cookie 18081 "$(developer_id perf_candidate)" "${TMP_DIR}/candidate-headers")"

run_load() {
    local side=$1
    local database=$2
    local port=$3
    local cookie=$4
    compose exec -T db psql --username postgres --dbname "${database}" --tuples-only --no-align \
        --command "SELECT pg_stat_statements_reset();" >/dev/null
    BASE_URL="http://127.0.0.1:${port}" AUTH_COOKIE="${cookie}" \
        K6_SUMMARY_TREND_STATS="min,med,avg,p(90),p(95),p(99),max" \
        k6 run --summary-export "${RESULTS_DIR}/${side}-summary.json" \
        "${checkout_suite:-${ROOT_DIR}/load-tests/k6-core-flows.js}"
    compose exec -T db psql --username postgres --dbname "${database}" --tuples-only --no-align \
        --command "SELECT json_build_object('calls', COALESCE(SUM(calls), 0), 'rows_returned_or_affected', COALESCE(SUM(rows), 0), 'logical_blocks', COALESCE(SUM(shared_blks_hit + shared_blks_read), 0), 'temp_blocks', COALESCE(SUM(temp_blks_read + temp_blks_written), 0), 'wal_records', COALESCE(SUM(wal_records), 0), 'wal_bytes', COALESCE(SUM(wal_bytes), 0)) FROM pg_stat_statements WHERE query NOT ILIKE '%pg_stat_statements%';" \
        >"${RESULTS_DIR}/${side}-db.json"
}

run_load base perf_base 18080 "${BASE_COOKIE}"
run_load candidate perf_candidate 18081 "${CANDIDATE_COOKIE}"

echo "Load comparison artifacts written to ${RESULTS_DIR}"
echo "Wall-clock metrics are advisory only; no latency threshold is evaluated."
