# Post-Deployment Checklist

- If you add new build artifacts or tooling, update `.dockerignore` so they don’t bloat context.
- If you change build steps (new scripts or dependencies), verify the “copy deps first, install, then copy code” pattern still holds.
- Periodically bump pinned base images (monthly/quarterly) and run the docker hygiene tests.
- Keep the `/health` route stable so probes don’t break.
- To force a fresh build (no cached layers), bump `_CACHE_BUST` in the Cloud Build trigger (e.g., set it to a timestamp) for api/web builds.
