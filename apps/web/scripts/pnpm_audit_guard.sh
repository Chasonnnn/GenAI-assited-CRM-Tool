#!/usr/bin/env bash

set -euo pipefail

MAX_ATTEMPTS="${PNPM_AUDIT_MAX_ATTEMPTS:-3}"
RETRY_DELAY_SECONDS="${PNPM_AUDIT_RETRY_DELAY_SECONDS:-15}"
attempt=1
delay="$RETRY_DELAY_SECONDS"

is_transient_error() {
  grep -Eiq \
    "(security/audits.*error \((5[0-9]{2})\)|EAI_AGAIN|ECONNRESET|ETIMEDOUT|ENOTFOUND|ECONNREFUSED|ERR_PNPM_FETCH|socket hang up)"
}

while true; do
  echo "Running pnpm audit --audit-level=high (attempt ${attempt}/${MAX_ATTEMPTS})"

  set +e
  output="$(pnpm audit --audit-level=high 2>&1)"
  status=$?
  set -e

  echo "$output"

  if [[ "$status" -eq 0 ]]; then
    exit 0
  fi

  if echo "$output" | is_transient_error; then
    if [[ "$attempt" -lt "$MAX_ATTEMPTS" ]]; then
      echo "Detected transient npm registry/network error; retrying in ${delay}s..."
      sleep "$delay"
      attempt=$((attempt + 1))
      delay=$((delay * 2))
      continue
    fi
    echo "pnpm audit failed after ${MAX_ATTEMPTS} attempts due to registry/network errors."
  fi

  exit "$status"
done
