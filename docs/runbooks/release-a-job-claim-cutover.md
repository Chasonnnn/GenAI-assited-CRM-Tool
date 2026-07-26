# Release A job-claim cutover

This checklist deploys the additive job-claim release without sending email,
purging organizations, or replaying legacy work. Stop on any failed gate.

## Hold contract

Cloud Build deploys the new worker with:

- `WORKER_CUTOVER_HOLD=true`
- `EMAIL_DELIVERY_DISPATCH_ENABLED=false`

The explicit cutover hold stops the worker loop before it opens a database
session, runs fallback schedulers or cleanup, or claims a job. Cloud Build does
not change `WORKER_JOB_TYPES`, so an existing allowlist remains intact. The
email-delivery flag is forward-compatible defense-in-depth. No automatic resume
occurs in `cloudbuild/api.yaml`.

Before the cutover, record the worker's current image digest and the exact
presence/value of `WORKER_JOB_TYPES` and `EMAIL_DELIVERY_DISPATCH_ENABLED`.
Confirm `WORKER_CUTOVER_HOLD` is absent before deployment. Resume must remove
`WORKER_CUTOVER_HOLD`, restore the captured email-delivery value, and leave the
captured job-type allowlist unchanged.

## Preflight

- [ ] Freeze one clean commit SHA. Confirm CI and the production-clone migration
      rehearsal are green for that exact SHA.
- [ ] Confirm production has not applied revision `20260725_1800` from an
      earlier draft. If it has, stop and create a corrective forward migration.
- [ ] Record the current API, worker, migration-job, and scan-job image digests.
- [ ] Pause `crm-worker-scale-up` and `crm-worker-scale-down`. Do not scale down
      an active legacy worker.
- [ ] Confirm the old worker is already idle/minimum-zero and has emitted no new
      `Processing job` log for the agreed maximum-handler observation window.
      The known historical `running` rows do not prove current activity.
- [ ] Run `gcloud run jobs executions list --job crm-attachment-scan --region
      us-central1` and verify zero active `crm-attachment-scan` executions. Wait
      at least the configured 600-second execution timeout after the last legacy
      execution before reclaiming a tokenless scan row.
- [ ] Capture sanitized baseline counts for job status/type, email delivery
      state, organization deletion state, and template IDs/hashes.
- [ ] Confirm the backup/PITR timestamp and rollback owner.

## Deploy held

- [ ] Run the API Cloud Build for the frozen SHA. It must use the SHA-tagged API
      and worker images for migration, scan job, worker, API, and ClamAV job.
- [ ] Confirm migration `20260725_1800` added only nullable `claim_token` and
      `claimed_at` columns.
- [ ] Confirm the scan job uses the new backward-compatible image before API
      traffic reaches the new revision.
- [ ] Confirm the worker revision has both hold values above, preserves the
      captured `WORKER_JOB_TYPES` value, and is healthy. Verify no new database
      sessions, schedulers, cleanup, claims, sends, or organization-delete
      handlers.
- [ ] Confirm the API is healthy while the worker remains held.

## Reconcile legacy claims

Use one fixed timezone-aware cutoff and evaluation time for preview and apply:

```bash
cd apps/api
uv run -m app.cli reconcile-legacy-job-claims \
  --stale-before "${RELEASE_A_STALE_BEFORE}" \
  --evaluated-at "${RELEASE_A_EVALUATED_AT}"
```

- [ ] Review aggregate job-type/reason counts. Resolve every ambiguous workflow
      email and organization deletion; do not replay or purge either.
- [ ] Record the exact count and fingerprint from the approved dry run.
- [ ] Apply only that reviewed plan:

```bash
uv run -m app.cli reconcile-legacy-job-claims \
  --stale-before "${RELEASE_A_STALE_BEFORE}" \
  --evaluated-at "${RELEASE_A_EVALUATED_AT}" \
  --apply \
  --expected-count "${RELEASE_A_EXPECTED_COUNT}" \
  --expected-fingerprint "${RELEASE_A_EXPECTED_FINGERPRINT}" \
  --review-reason "${RELEASE_A_REVIEW_REASON}"
```

- [ ] Repeat the dry run and require count `0`.
- [ ] Require baseline email, organization, and template evidence to be
      unchanged except for the reviewed job dispositions and audit records.

## Explicit resume

- [ ] Keep both scaler schedules paused.
- [ ] Remove `WORKER_CUTOVER_HOLD` and restore the captured pre-cutover values
      for `EMAIL_DELIVERY_DISPATCH_ENABLED`. Verify `WORKER_JOB_TYPES` still
      matches its captured value. If the email-delivery flag was previously
      absent:

```bash
gcloud run services update crm-worker \
  --region us-central1 \
  --remove-env-vars WORKER_CUTOVER_HOLD,EMAIL_DELIVERY_DISPATCH_ENABLED
```

- [ ] Verify the new revision uses the frozen worker digest, then watch the first
      claims and delivery attempts. Stop on an unexpected legacy replay, send
      burst, organization deletion, or claim that remains running.
- [ ] Resume the scaler schedules only after the observation gate passes.

## Rollback

Keep the worker held. Roll the API back to its recorded revision if necessary,
but retain the additive schema and the backward-compatible scan runner. A worker
rollback must use the recorded image digest while preserving the hold values.
Never downgrade the migration, automatically replay jobs, restore the database
after a provider side effect, or resume claims as part of rollback.
