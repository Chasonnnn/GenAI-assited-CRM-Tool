#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_WEB:?IMAGE_WEB is required}"
: "${NEXT_PUBLIC_API_BASE_URL:?NEXT_PUBLIC_API_BASE_URL is required}"
: "${NEXT_DEPLOYMENT_ID:?NEXT_DEPLOYMENT_ID is required}"

# Keep the dependency layers and .next/cache: the small runner image has neither.
cache_bust="${CACHE_BUST:-0}"
[[ "$cache_bust" =~ ^[A-Za-z0-9_.-]{1,100}$ ]] || { echo "Invalid CACHE_BUST" >&2; exit 1; }
cache_image="${IMAGE_WEB%:*}:build-cache-${cache_bust}"
cache_seed="node:24.18.0-bookworm-slim"
build_args=(
  --build-arg BUILDKIT_INLINE_CACHE=1
  --build-arg "CACHE_BUST=$cache_bust"
  --build-arg "NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL"
  --build-arg "NEXT_DEPLOYMENT_ID=$NEXT_DEPLOYMENT_ID"
  -f apps/web/Dockerfile
)
if docker pull "$cache_image"; then
  # Both builds must read the same seed even after the builder tag is replaced.
  cache_seed=$(docker image inspect "$cache_image" --format '{{index .RepoDigests 0}}')
  [[ "$cache_seed" == *@sha256:* ]] || { echo "Invalid builder cache digest" >&2; exit 1; }
  build_args+=(--cache-from "$cache_image")
else
  echo "Builder cache unavailable; continuing with a cold build." >&2
fi

build_args+=(--build-arg "NEXT_CACHE_IMAGE=$cache_seed")
docker build "${build_args[@]}" --target builder -t "$cache_image" .
docker build "${build_args[@]}" --cache-from "$cache_image" --target runner -t "$IMAGE_WEB" .

# A cache outage must not discard a successfully built release image.
if ! docker push "$cache_image"; then
  echo "Builder cache upload failed; the next build may run cold." >&2
fi
