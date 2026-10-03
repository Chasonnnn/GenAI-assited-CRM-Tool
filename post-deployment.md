# Post-Deployment Checklist

- If you add new build artifacts or tooling, update `.dockerignore` so they don’t bloat context.
- If you change build steps (new scripts or dependencies), verify the “copy deps first, install, then copy code” pattern still holds.
- Periodically bump pinned base images (monthly/quarterly) and run the docker hygiene tests.
- Keep the `/health` route stable so probes don’t break.
- To force a fresh build (no cached layers), bump `_CACHE_BUST` in the Cloud Build trigger (e.g., set it to a timestamp) for api/web builds.

## Module routing rollout

After all API and worker instances use module routing, run the organization-scoped inventory from `apps/api` with the release's UTC timestamp:

```sh
mise exec -- uv run python scripts/repair_form_routing.py --organization-id ORG_UUID --released-at 2026-10-03T18:00:00Z
```

Use the actual release timestamp. After separate production authorization, repeat with `--apply`. The command strips retired workflow actions, preserves execution history and pending action indices, and routes unresolved shared submissions in `workflow_pending` without a completed routing job since that timestamp. It uses the form's current settings. It does not replay Application Submitted workflows. Run it for each organization; reruns skip completed repairs. Review the reported counts and sanitized workflow IDs. The default command makes no writes.
