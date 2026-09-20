# Donor Compatibility Implementation Workplan

Working checklist for the approved donor compatibility plan. The approved audit report
(coverage, system evidence, boundaries, workplan, activation gates) lives at
`output/donor-compatibility-audit/index.html`. This file tracks implementation progress;
checked items name their commits. Implementation is in progress; final live QA is a
separate follow-up phase.

## Baseline

- Audit evidence baseline: `a3574363`. Implementation base: `c6095f2d` (current `origin/main`).
- Drift re-verified after fast-forward: `WorkflowTemplate` gained `external_key`/`current_version`
  (ops-cli), platform template writes moved to `platform_template_write_service.py`, surrogate
  stage `reschedule_needed` added. No donor-surface behavior changes.

## Authorization boundaries (do not cross in this PR)

- No production deployment, production migrations, external sends, or live provider calls.
- Donor external (Meta/Zapier) reporting stays **off**; build controls and tests without sending.
- All AI-authored external content requires human review.
- Tenant scope derives from authenticated membership or a validated token/resource only.

## W0 — Repair defects and preserve donor subject contracts

- [x] fix: email campaign preview reports full-audience eligible/suppressed counts
      (email branch of `campaign_service.preview_recipients`; sampled page must not cap
      `eligible_count`). Implementation note: entity emails are encrypted at rest, so the
      full-audience aggregation hashes the org's suppression list in Python and passes it
      as one typed PostgreSQL `VARCHAR(64)[]` bind to indexed `email_hash = ANY(...)`
      predicates (one aggregate query + one limited sample query; no full-audience row
      materialization, no `Query.count()`). A 65,536-suppression regression covers the
      driver parameter limit and tenant isolation.
      Suppressed sample rows are now excluded in SQL, so the sample reaches `limit`
      whenever enough eligible recipients exist.
- [x] fix: Zapier test-lead response retains `donor_id` (`routers/zapier.py`); web
      `useZapierTestLead` now also invalidates donor list/detail caches on donor
      conversion (type already declared `donor_id`)
- [x] fix: donor Meta source mapping is unambiguous — removed `source` from
      `DONOR_META_MAPPING_FIELDS`; save now rejects donor mappings targeting it;
      preview returns `unsupported_mapped_fields` and the mapping page shows a
      destructive "Mapping repair required" alert; conversion keeps canonical
      `"Meta"`; stored legacy mappings are surfaced, never rewritten or backfilled
- [x] feat: `WorkflowTemplate.subject_type` column + migration + backfill
      (donor triggers → NULL/repair-required, never guessed; form/intake/match/appointment
      triggers → legacy subject mapping; others → surrogate)
- [x] feat: template save/use/publish preserve exact subject; `use_template` routes through
      `workflow_service.create_workflow`; donor permission checks in templates router;
      ambiguous legacy donor-intent templates error as repair-required, never silently
      enabled
- [x] feat: platform template publish/version snapshots and admin config export/import carry
      `subject_type` (publish validates donor triggers require an explicit donor subject)
- [x] fix (reviewed; hosted validation pending): template list/get/create/use/delete
      and from-workflow enforce the effective donor subject plus personal-workflow visibility;
      Zapier donor test leads require donor view/edit before mutation; platform publish reuses
      canonical donor condition/action validation and serializes `subject_type`; migration
      independently backfills stored and draft subjects and removes the draft key on downgrade
- [x] chore: web template contract sync (`subject_type` in template types; no UI redesign)

## W1 — Recoverable intake/conversion occurrences (after W0 subject contracts)

- [ ] Transactional donor-created dispatch jobs for Meta conversion, hosted promotion, and the
      new CSV importer (enqueued `commit=False` inside the mutation transaction; org-scoped
      occurrence idempotency keys). Ordinary donor CRUD workflow timing stays synchronous.
- [ ] Engine occurrence dedupe for donor triggers; per-action receipts committed atomically with
      early-committing actions; workflow-email admission idempotency key.
- [ ] Conversion occurrences recorded in `donor_service.apply_status_change` for applied
      transitions including approvals; pending requests emit nothing; undo emits nothing;
      once-per-bucket outbound dedupe preserved.
- [ ] Stale-claim classification per new job type (quarantine by default until safe-replay proof),
      quarantine monitoring note + runbook. Surrogate behavior unchanged.

## W2 — Five independently owned foundations (parallel after contracts)

- [ ] Imports: additive `DonorImport`/`DonorImportRow`; subtype-fixed batches; upload → map →
      validate → approve (existing org-settings gate) → queued execution → per-row atomic
      outcomes/retry; create-only with duplicate skip/ambiguity review; encrypted upload storage
      with expiry/cleanup; `ImportTemplate` entity discriminator (existing templates backfill
      surrogate); donor-scoped mapping learning; dedicated donor-import permission. No SSNs,
      restore IDs, history, or inferred consent in operational CSV.
- [ ] Contact privacy: donor-contact association separate from consent; per-message validated
      record context is the authoritative read filter (bodies, media, counts, unread, previews
      filtered before pagination); shared-phone donor viewer cannot read surrogate content
      (same-contact same-route negative test); STOP stays contact-global; phone edits do not
      transfer consent or retarget queued sends.
- [x] Operations navigation: expose Donors through `view_donors`; retain the Tickets
      developer gate and cover denied/non-developer users.
- [ ] Operations: permission-based correspondence access (replace the developer-role
      gate in `record_correspondence`); mount existing
      donor-ready appointments/matches cards on donor detail; no broad Tickets grant; no visual
      redesign.
- [ ] AI: donor-aware workflow generation through the canonical validator/registry (saved
      disabled); bounded donor-record chat with donor summary cache OFF; permission rechecks for
      context/history/stream; no SSNs/unneeded health/partner/shared-phone content.
- [ ] Tracking plumbing: `internal_only` never emits externally (explicit breaking correction +
      admin reconfiguration notes); consume or retire queued `TrackingEventLog` modes with no
      backlog replay; one hosted/embed policy resolver; server-authoritative consent at creation
      and dispatch; deterministic event IDs; exact-pipeline mapping keys.
- [ ] Profile package: versioned, privileged, read/verify-only export preserving stored fields,
      explicit clears, form answer/schema/mapping snapshots, provenance, photo/history manifest.
      Basic CSV remains explicitly partial (no SSNs). Full restoration is separately scoped.

## W3 — Donor messaging and reviewed actions (after W2 privacy + W1 + W0 templates)

- [ ] Donor SMS workflow actions via existing org-owned sender/delivery engine (published
      template versions, purpose-specific consent, delivery fencing).
- [ ] Donor promotional campaigns: exact subtype/stage audience; preview is an estimate;
      snapshot approved filters/template/settings; resolve audience at execution; freeze
      recipient/context/content at delivery materialization and across retries; recheck
      STOP/archive/consent before admission; per-contact dedupe; ambiguous shared-phone
      personalization skipped for review.
- [ ] Reviewed donor email compose/reply: atomic ticket + donor record link.
- [ ] Reviewed AI donor actions: note/task/assignment/stage/email with approval-time and
      execution-time revalidation.

## W4 — New shared SMS extensions (separately budgeted; not W3 prerequisites)

- [ ] Appointment SMS confirm/remind/cancel/reschedule with occurrence versioning, stale-reminder
      invalidation, and provider-ambiguity fencing.
- [ ] AI SMS drafting with mandatory human review.

## W5 — Destination authorization and rollout (external approval required)

- [ ] Donor Meta reporting default off. Documented admissible event purpose/criteria/payload
      per destination; donor context can itself imply reproductive health — renaming, hashing,
      or consent does not override Meta restrictions. Non-Meta Zapier destinations need their own
      disclosure review.
- [ ] One server route (direct Meta OR Zapier) per event/destination; stop-admission controls;
      sanitized monitoring; consumers deployed before producers; rollback never replays accepted
      sends.

## Acceptance test matrix (applies across waves)

Subtype isolation (egg/sperm cannot cross silently) · tenant/role/CSRF negatives ·
shared-contact privacy (bodies, media, counts, unread, previews) · crash/retry
(post-commit failure, duplicate delivery, stale leases, partial action loops, ambiguous
provider outcomes) · approval/consent changes (review revoked, donor archived, number changed,
STOP, template updated) · data preservation (explicit clears, form fallback, snapshots,
retention/holds) · tracking contract (no external internal-only calls, stable IDs, one route,
no request/undo stage events) · operational states (loading/error/empty/populated, import
retry, permission denied).

## Verification log

| date | commit | commands | result |
|------|--------|----------|--------|
| 2026-09-20 | (this commit) email preview full-audience counts | `uv run -m pytest tests/test_campaigns.py -q` (33 passed), `uv run -m pytest tests/test_donor_campaigns.py -q` (9 passed), `ruff check` clean | pass |
| 2026-09-20 | (this commit) Zapier test-lead donor_id | `uv run -m pytest tests/test_zapier_webhooks.py -q` (21 passed; new donor regression failed before fix with KeyError donor_id), `pnpm run typecheck` clean, `vitest run tests/integrations-page.test.tsx` (44 passed) | pass |
| 2026-09-20 | (this commit) donor Meta source mapping repair | `uv run -m pytest tests/test_meta_donor_routing.py tests/test_meta_donor_form_permissions.py tests/test_meta_form_mapping.py tests/test_meta_lead_kind_snapshot.py tests/test_meta_forms_delete.py tests/test_meta_forms_performance_status.py -q` (37 passed), `ruff check` clean, `pnpm run typecheck` clean, `vitest run tests/meta-form-mapping-page.test.tsx` (8 passed) | pass |
| 2026-09-20 | (this commit) WorkflowTemplate.subject_type contract | `uv run alembic upgrade head` (20260920_0100 applied), `uv run -m pytest tests/test_workflows.py tests/test_donor_workflows.py tests/test_workflow_template_use_scope.py tests/test_workflow_template_subject_type.py tests/test_template_seeder_workflows.py tests/test_shared_donor_template_workflows.py -q` (85 passed), `uv run -m pytest tests/test_rbac_policies.py tests/test_org_scope_backstop.py tests/test_intelligent_suggestions.py -q` (44 passed), `ruff check` clean | pass |
| 2026-09-20 | (this commit) platform publish + export/import subject_type | `uv run -m pytest tests/test_platform_template_studio.py tests/test_ops_cli_integration.py tests/test_ops_cli_templates.py tests/test_admin_exports.py tests/test_admin_imports.py tests/test_platform_router_template_studio_and_alerts.py -q` (68 passed), `ruff check` clean, `pnpm run typecheck` clean, `vitest run tests/templates-page.test.tsx tests/ops-templates-studio-page.test.tsx tests/platform-workflow-template-draft.test.tsx` (19 passed) | pass |
| 2026-09-20 | W0 CI and authorization repair; commits below | Focused template and Zapier permission regressions (17 passed); CI-equivalent parallel-safe backend suite with FastAPI convention/contract gates included (3,085 passed); serial email-outbox and migration suite (91 passed); `alembic check` reports no new operations; Ruff and `git diff --check` clean | local integrated checks pass; four unchanged Linux-orb setup parametrizations were excluded because macOS lacks `dpkg`; hosted CI has not been rerun |

## W0 correction commits

- `f5b9047e` fix: preserve workflow sweep organization identifiers
- `26adc541` test: correct donor intake subject overrides
- `70c69cb6` fix: enforce donor template and integration access
- `bbab4fb0` fix: validate and preserve platform workflow subjects
- `fdd2ec9f` fix: preserve workflow template drafts across migration
- `7c667b55` fix: avoid campaign suppression parameter limits

Publication was authorized on 2026-09-20. Hosted checks and live QA remain
separate from local validation.

## Urgent donor launch checkpoint — 2026-09-20

- [x] Recoverable donor form dispatch and isolated donor stage reporting, published
      in `2b8bdc41` and `b573da0a`; all 14 hosted checks passed at `b573da0a`.
- [x] Four-tab Zapier dialog: Incoming leads, Form routing, Stage reporting, Activity.
      Separate donor/surrogate enablement; egg/sperm mappings use live pipeline and
      stage IDs. Unavailable donor settings/pipelines preserve stored configuration.
- [x] Browser QA: saved donor settings and mappings persist; route editing and
      field extraction work; donor navigation is visible to an authorized
      non-developer; tabs and footer remain usable at 320 px.
- [x] Local HTTP Zapier intake creates separate egg/sperm donors; replay is
      idempotent and does not create surrogate records. No real provider call.
- [x] Frontend type checking, lint, and 1,578 tests passed; final helper extraction
      also passed 51 integration-page tests, type checking, and scoped lint.
- [ ] Merge/release and verify production API, web, worker, scanner, and migration.
      Current production is 0.91.65, migration `20260914_1200_donor_profile`.
- [ ] Authenticate to EWI and configure its shared donor questionnaire and one
      match/create workflow. Verify real form/link IDs and avoid duplicate routing.
- [ ] Bind real egg/sperm Meta forms and Zapier destination/stage mappings; validate
      provider acceptance before activation. Website work is owned separately.
- [ ] Handle donor Zapier mapping dependencies when donor pipeline stages are
      removed; the existing stale-mapping guard currently requires stage recovery.

Production form configuration, cloud deployment, and Meta/Zapier activation are
not established by local QA. Broader W1–W5 checkboxes above remain authoritative.
