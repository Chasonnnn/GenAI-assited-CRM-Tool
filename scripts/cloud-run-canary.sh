#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
SERVICE="${2:-}"
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-}"
CANDIDATE_REVISION="${CANDIDATE_REVISION:-}"
STABLE_REVISION="${STABLE_REVISION:-}"
CANDIDATE_PERCENT="${CANDIDATE_PERCENT:-10}"

usage() {
    cat <<'USAGE'
Usage:
  PROJECT_ID=... REGION=... CANDIDATE_REVISION=... scripts/cloud-run-canary.sh start SERVICE
  PROJECT_ID=... REGION=... CANDIDATE_REVISION=... scripts/cloud-run-canary.sh promote SERVICE
  PROJECT_ID=... REGION=... STABLE_REVISION=... scripts/cloud-run-canary.sh rollback SERVICE

Optional for start: CANDIDATE_PERCENT=10 (1-49; defaults to 10).
The helper changes traffic only. It never deploys images or runs migrations.
USAGE
}

fail() {
    echo "$1" >&2
    exit 2
}

[[ -n "${ACTION}" && -n "${SERVICE}" ]] || { usage; exit 2; }
[[ -n "${PROJECT_ID}" ]] || fail "PROJECT_ID is required"
[[ -n "${REGION}" ]] || fail "REGION is required"
command -v gcloud >/dev/null 2>&1 || fail "gcloud is required"
command -v jq >/dev/null 2>&1 || fail "jq is required"

service_json() {
    gcloud run services describe "${SERVICE}" \
        --project "${PROJECT_ID}" \
        --region "${REGION}" \
        --format json
}

assert_revision_for_service() {
    local revision=$1
    local actual_service
    actual_service="$(
        gcloud run revisions describe "${revision}" \
            --project "${PROJECT_ID}" \
            --region "${REGION}" \
            --format json \
            | jq -r '.metadata.labels["serving.knative.dev/service"] // empty'
    )"
    [[ "${actual_service}" == "${SERVICE}" ]] || \
        fail "Revision ${revision} does not belong to service ${SERVICE}"
}

case "${ACTION}" in
    start)
        [[ -n "${CANDIDATE_REVISION}" ]] || fail "CANDIDATE_REVISION is required for start"
        [[ "${CANDIDATE_PERCENT}" =~ ^[0-9]+$ ]] || fail "CANDIDATE_PERCENT must be an integer"
        ((CANDIDATE_PERCENT >= 1 && CANDIDATE_PERCENT <= 49)) || \
            fail "CANDIDATE_PERCENT must be between 1 and 49"
        assert_revision_for_service "${CANDIDATE_REVISION}"
        STABLE_REVISION="$(
            service_json \
                | jq -r --arg candidate "${CANDIDATE_REVISION}" \
                    '[.status.traffic[] | select(.revisionName != $candidate and (.percent // 0) > 0)] | max_by(.percent) | .revisionName // empty'
        )"
        [[ -n "${STABLE_REVISION}" ]] || fail "No stable traffic-bearing revision was found"
        gcloud run services update-traffic "${SERVICE}" \
            --project "${PROJECT_ID}" \
            --region "${REGION}" \
            --to-revisions "${CANDIDATE_REVISION}=${CANDIDATE_PERCENT},${STABLE_REVISION}=$((100 - CANDIDATE_PERCENT))"
        echo "Canary started: candidate=${CANDIDATE_REVISION} stable=${STABLE_REVISION} candidate_percent=${CANDIDATE_PERCENT}"
        ;;
    promote)
        [[ -n "${CANDIDATE_REVISION}" ]] || fail "CANDIDATE_REVISION is required for promote"
        assert_revision_for_service "${CANDIDATE_REVISION}"
        gcloud run services update-traffic "${SERVICE}" \
            --project "${PROJECT_ID}" \
            --region "${REGION}" \
            --to-revisions "${CANDIDATE_REVISION}=100"
        echo "Canary promoted: revision=${CANDIDATE_REVISION}"
        ;;
    rollback)
        [[ -n "${STABLE_REVISION}" ]] || fail "STABLE_REVISION is required for rollback"
        assert_revision_for_service "${STABLE_REVISION}"
        gcloud run services update-traffic "${SERVICE}" \
            --project "${PROJECT_ID}" \
            --region "${REGION}" \
            --to-revisions "${STABLE_REVISION}=100"
        echo "Traffic rolled back: revision=${STABLE_REVISION}"
        ;;
    *)
        usage
        exit 2
        ;;
esac
