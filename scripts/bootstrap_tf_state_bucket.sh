#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <project_id> <bucket_name> [location]" >&2
  echo "Example: $0 my-project my-project-tfstate US" >&2
  exit 1
fi

project_id="$1"
bucket_name="$2"
location="${3:-US}"

gcloud config set project "$project_id"
gcloud storage buckets create "gs://${bucket_name}" \
  --project "$project_id" \
  --location "$location" \
  --uniform-bucket-level-access

echo "Created bucket: gs://${bucket_name}"
