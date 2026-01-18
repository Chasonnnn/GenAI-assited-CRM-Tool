#!/usr/bin/env bash
set -euo pipefail

required=(
  JWT_SECRET
  DEV_SECRET
  INTERNAL_SECRET
  META_ENCRYPTION_KEY
  FERNET_KEY
  DATA_ENCRYPTION_KEY
  PII_HASH_KEY
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  ZOOM_CLIENT_ID
  ZOOM_CLIENT_SECRET
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
)

missing=()
for key in "${required[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    missing+=("$key")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "Missing required env vars: ${missing[*]}" >&2
  exit 1
fi

python3 - <<'PY'
import json
import os

keys = [
    "JWT_SECRET",
    "DEV_SECRET",
    "INTERNAL_SECRET",
    "META_ENCRYPTION_KEY",
    "FERNET_KEY",
    "DATA_ENCRYPTION_KEY",
    "PII_HASH_KEY",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "ZOOM_CLIENT_ID",
    "ZOOM_CLIENT_SECRET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
]
print(json.dumps({k: os.environ[k] for k in keys}))
PY
