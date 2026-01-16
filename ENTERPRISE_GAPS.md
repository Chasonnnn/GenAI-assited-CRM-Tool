# ENTERPRISE_GAPS

This roadmap highlights enterprise readiness gaps with concrete, file-based remediation steps. Line ranges are approximate.

## SSO / SCIM readiness

Evidence
- `apps/api/app/routers/auth.py:56-173` only Google OAuth login/callback.
- `apps/web/app/login/page.tsx:19-150` UI is Google SSO + Duo only.
- `apps/api/app/main.py:338-465` router list has no SCIM endpoints.
- `apps/api/app/db/models.py:48-110` Organization lacks SSO configuration fields.
- `apps/api/app/routers/settings.py:34-120` org settings endpoint does not expose SSO config.

Now (0-30 days)
- Add org-level SSO policy fields: update `apps/api/app/db/models.py:48-110` to add `sso_provider` (string enum), `sso_enforced` (bool), `sso_allowed_domains` (array/JSONB), `sso_oidc_issuer` (string), `sso_client_id` (string). Create an Alembic migration adding these columns with safe defaults.
- Expose SSO settings to admins: extend `apps/api/app/routers/settings.py:34-120` request/response models to include the new SSO fields; update the org settings read/write logic to persist them; add input validation (domain list, issuer URL format).
- Enforce SSO policy at login: in `apps/api/app/routers/auth.py:56-173`, load org settings for the user (lookup by membership or invite) and block non-SSO login if `sso_enforced` is true; validate email domain against `sso_allowed_domains` after token verification.

Next (30-90 days)
- Implement SCIM provisioning: create `apps/api/app/routers/scim.py` (new file, ~1-250) with SCIM 2.0 `/Users` and `/Groups` CRUD; add `apps/api/app/services/scim_service.py` (new file, ~1-200) to map SCIM operations to `User`, `Membership`, and `Role`.
- Add SCIM auth and tokens: add `ScimToken` model to `apps/api/app/db/models.py:296-360` (near `AuthIdentity`) with hashed token + org_id; add token validation dependency in `apps/api/app/core/deps.py:200-280` and register the SCIM router in `apps/api/app/main.py:338-465`.

Later (90+ days)
- Multi-IdP support: add `AuthIdentity.provider` expansion (OIDC/SAML) in `apps/api/app/db/models.py:296-316`, extend `apps/api/app/services/google_oauth.py:1-117`, and add `apps/api/app/services/oidc_service.py` (new file, ~1-200); update `apps/web/app/login/page.tsx:19-150` to route users to the configured IdP based on org slug.

## RBAC / ABAC posture

Evidence
- `apps/api/app/core/policies.py:1-80` static permission map only.
- `apps/api/app/core/deps.py:218-268` authorization checks permissions, not attributes.

Now (0-30 days)
- Add attribute-aware checks: introduce `apps/api/app/core/abac.py` (new file, ~1-200) with functions like `can_view_entity(session, entity)` and `can_edit_entity(session, entity)` for owner/team/assignee rules; call these from services after loading entities.
- Add entity-scoped dependency: add `require_entity_permission` in `apps/api/app/core/deps.py:200-280` that loads the entity by ID and invokes ABAC checks; update high-risk routers (surrogates, intended parents, matches, tasks, notes) to use it instead of only `require_permission`.
- Add tests: create `apps/api/tests/test_abac.py` (new file, ~1-200) covering owner vs. non-owner access and team-only access for at least surrogates and tasks.

Next (30-90 days)
- Policy storage: add `PolicyRule`/`PolicyBinding` tables in `apps/api/app/db/models.py` near `RolePermission` (~226-294) to store per-org ABAC rules; update `apps/api/app/services/permission_service.py:33-110` to evaluate policy rules against entity attributes.

Later (90+ days)
- UI policy management: extend `apps/web/app/(app)/settings/team/roles/page.tsx:1-115` to expose ABAC rule sets, and enforce them in frontend guards (`apps/web/lib/auth-context.tsx:1-123`).

## Audit logging

Evidence
- `apps/api/app/services/audit_service.py:80-889` audit logging is explicit and event-driven.
- `apps/api/app/main.py:192-317` middleware does not automatically log read access for sensitive entities.

Now (0-30 days)
- Add read-access audit middleware: implement `audit_access_middleware` in `apps/api/app/main.py:192-317` that logs `phi_access` events for GET requests on sensitive routes (surrogates, intended parents, matches, attachments). Use `audit_service.log_phi_access` with request metadata.
- Add audit context helpers: create `apps/api/app/core/audit_context.py` (new file, ~1-120) to attach `{target_type, target_id}` to `request.state`; update read-heavy services (e.g., `apps/api/app/services/surrogate_service.py:1101-1120` and `apps/api/app/services/ip_service.py:195-201`) to set this context before returning data.

Next (30-90 days)
- Consistent audit exports: extend `apps/api/app/routers/audit.py:166-200` with an export endpoint that issues signed URLs and logs download events via `audit_service.log_data_export`; store exports in a dedicated bucket (config in `apps/api/app/core/config.py:197-204`).

Later (90+ days)
- SIEM forwarding: add a webhook sink in `apps/api/app/services/audit_service.py:80-889` and a queue job in `apps/api/app/services/job_service.py:12-116` to forward audit events to a SIEM endpoint with retry/backoff.

## Retention / deletion

Evidence
- `apps/api/app/services/compliance_service.py:558-872` retention covers only a small set of entities and hard-deletes data.
- `apps/api/app/routers/compliance.py:27-147` policy and purge endpoints lack DSAR/delete-request flow.

Now (0-30 days)
- Expand retention coverage: extend `apps/api/app/services/compliance_service.py:567-827` to include `attachments`, `form_submissions`, `notifications`, and `campaign_logs` in `_build_retention_query`; update `seed_default_retention_policies` to include these entity types.
- Add retention action type: update the `DataRetentionPolicy` model in `apps/api/app/db/models.py:2837-2868` to include `action` enum (`purge` vs `redact`); update `compliance_service.execute_purge` to redact PII where required instead of deleting.

Next (30-90 days)
- DSAR workflow: add `DataDeletionRequest` model to `apps/api/app/db/models.py:2837-2925` and endpoints in `apps/api/app/routers/compliance.py:27-147` to submit, approve, and execute deletion/redaction; wire to `compliance_service` for execution.

Later (90+ days)
- Scheduled retention jobs: add a scheduled job entry in `apps/api/app/routers/internal.py:153-190` and a job handler in `apps/api/app/worker.py:720-770` to run retention nightly with reporting.

## Observability

Evidence
- `apps/api/app/core/structured_logging.py:1-26` limited context fields, no correlation IDs.
- `apps/api/app/core/telemetry.py:37-65` traces only; no log correlation.
- `apps/api/app/main.py:104-137` request ID only passed through if client provided.

Now (0-30 days)
- Request ID generation: add middleware in `apps/api/app/main.py:192-317` to generate a UUID when `X-Request-Id` is missing, store it on `request.state.request_id`, and return it in the response header.
- Correlated logging: update `apps/api/app/core/structured_logging.py:6-26` to include `request_id` and `trace_id` in log context; update `apps/api/app/core/gcp_monitoring.py:40-67` to read `request.state.request_id` when present.

Next (30-90 days)
- Metrics coverage: extend `apps/api/app/services/metrics_service.py:1-90` to record queue depth, job latency, and external API error rates; emit metrics in `apps/api/app/worker.py:720-770`, `apps/api/app/services/gmail_service.py:22-99`, and `apps/api/app/services/zoom_service.py:77-150`.

Later (90+ days)
- Frontend RUM: add a client telemetry helper in `apps/web/lib/telemetry.ts` (new file, ~1-120) and wire page load + API error tracking in `apps/web/app/layout.tsx:1-44`.

## DR / backups

Evidence
- `docker-compose.yml:1-16` defines only a local Postgres volume; no backup/restore automation.
- `docs/backup-restore-runbook.md:1-80` documents manual backup/restore steps but not scheduled automation or verification.

Now (0-30 days)
- Define backup scripts: add `scripts/backup_db.sh` and `scripts/restore_db.sh` (new files, ~1-80 each) to wrap the `pg_dump`/`pg_restore` commands from `docs/backup-restore-runbook.md:20-59`. Update `docs/backup-restore-runbook.md` to reference these scripts and document required env vars and retention in the same file.

Next (30-90 days)
- Automated backups: add a scheduler spec (e.g., `ops/cron/backup.yaml`, new file ~1-120) to run `scripts/backup_db.sh` nightly and ship encrypted backups to object storage; add a verification script `scripts/verify_restore.sh` (new file, ~1-120) that restores to staging and runs `apps/api` smoke tests.

Later (90+ days)
- PITR: enable WAL archiving in production Postgres and document RPO/RTO targets in `docs/ops/pitr.md` (new file, ~1-160) with quarterly restore drills.

## Integration idempotency

Evidence
- `apps/api/app/services/job_service.py:12-38` idempotency key is optional.
- `apps/api/app/routers/webhooks.py:122-135` Meta webhook uses idempotency keys, but other flows do not.
- `apps/api/app/services/email_service.py:324-361` and `apps/api/app/services/workflow_engine.py:982-1017` schedule jobs without idempotency keys.

Now (0-30 days)
- Standardize idempotency keys: update `apps/api/app/services/email_service.py:324-361` to compute and pass `idempotency_key` (e.g., `send_email:{org_id}:{template_id}:{recipient_email}:{schedule_at}`) and store it on `EmailLog` (add column in `apps/api/app/db/models.py:1794-1844` + migration).
- Workflow email dedupe: update `apps/api/app/services/workflow_engine.py:982-1017` to pass `idempotency_key` derived from `event_id` to `job_service.schedule_job`.
- Inbound webhook dedupe: add `WebhookEvent` model in `apps/api/app/db/models.py:1187-1260` with unique `provider_event_id`; check/insert it in `apps/api/app/routers/webhooks.py:95-141` before scheduling jobs.

Next (30-90 days)
- API idempotency: add `Idempotency-Key` support in `apps/api/app/core/deps.py:200-280` and enforce it on public apply/booking endpoints (`apps/api/app/routers/forms_public.py:78-109`, `apps/api/app/routers/booking.py:195-220`) to prevent duplicate submissions.

Later (90+ days)
- Outbox pattern: add `integration_outbox` table in `apps/api/app/db/models.py:1187-1260` and a worker job in `apps/api/app/worker.py:720-775` to publish events to external systems exactly-once.

## Job processing

Evidence
- `apps/api/app/services/job_service.py:41-57` pending jobs are selected without row locks.
- `apps/api/app/worker.py:737-746` worker marks jobs running after selection, risking duplicate picks with multiple workers.

Now (0-30 days)
- Atomic job claiming: replace `get_pending_jobs` with `claim_pending_jobs` in `apps/api/app/services/job_service.py:41-57` that selects rows `FOR UPDATE SKIP LOCKED` and marks them running in the same transaction.
- Lock fields: add `locked_at` and `locked_by` columns to the `Job` model in `apps/api/app/db/models.py:1690-1739`, and set them in `job_service.mark_job_running`.
- Worker update: change `apps/api/app/worker.py:720-746` to call `claim_pending_jobs` and process the returned jobs without race conditions.

Next (30-90 days)
- Backoff strategy: add `next_run_at` and `backoff_seconds` fields to `Job`, update `mark_job_failed` in `apps/api/app/services/job_service.py:103-114` to compute exponential backoff, and update the job polling query to filter by `next_run_at`.

Later (90+ days)
- Dedicated queue system: replace the polling loop in `apps/api/app/worker.py:720-775` with a managed queue (e.g., Postgres-based pg-boss or Redis-backed worker) and update job scheduling APIs in `apps/api/app/services/job_service.py:12-116` and `apps/api/app/db/models.py:1690-1739` accordingly.
