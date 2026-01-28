# Post-Deployment Checklist

- If you add new build artifacts or tooling, update `.dockerignore` so they don’t bloat context.
- If you change build steps (new scripts or dependencies), verify the “copy deps first, install, then copy code” pattern still holds.
- Periodically bump pinned base images (monthly/quarterly) and run the docker hygiene tests.
- Keep the `/health` route stable so probes don’t break.
