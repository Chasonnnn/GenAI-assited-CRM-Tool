#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <project_id> <bucket_name> [location] [kms_key]" >&2
  echo "Example: $0 my-project my-project-tfstate US projects/.../cryptoKeys/..." >&2
  exit 1
fi

project_id="$1"
bucket_name="$2"
location="${3:-US}"
kms_key="${4:-}"

gcloud config set project "$project_id"
create_args=(
  "gs://${bucket_name}"
  "--project" "$project_id"
  "--location" "$location"
  "--uniform-bucket-level-access"
  "--public-access-prevention=enforced"
)

if [[ -n "$kms_key" ]]; then
  create_args+=("--default-encryption-key=$kms_key")
fi

gcloud storage buckets create "${create_args[@]}"

echo "Created bucket: gs://${bucket_name}"
