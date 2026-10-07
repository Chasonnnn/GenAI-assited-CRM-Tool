#!/usr/bin/env bash
# Block until a PR's checks finish; exit non-zero on the first failure.
# Usage: scripts/wait-ci.sh <pr-number-or-branch> [extra gh pr checks args]
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo 'Usage: scripts/wait-ci.sh <pr-number-or-branch> [gh pr checks args]' >&2
    exit 2
fi

exec gh pr checks "$@" --watch --fail-fast
