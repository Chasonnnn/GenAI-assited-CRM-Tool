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
      full-audience aggregation hashes the org's bounded suppression list in Python and
      counts in SQL on the indexed `email_hash` column (one aggregate query + one
      limited sample query; no full-audience row materialization, no `Query.count()`).
      Suppressed sample rows are now excluded in SQL, so the sample reaches `limit`
      whenever enough eligible recipients exist.
- [x] fix: Zapier test-lead response retains `donor_id` (`routers/zapier.py`); web
      `useZapierTestLead` now also invalidates donor list/detail caches on donor
      conversion (type already declared `donor_id`)
- [ ] fix: donor Meta source mapping is unambiguous — remove `source` from donor mapping
      fields; flag stored donor mappings targeting `source` as repair-required; conversion
      keeps canonical `"Meta"`; no backfill of existing record sources
- [ ] feat: `WorkflowTemplate.subject_type` column + migration + backfill
      (donor triggers → NULL/repair-required, never guessed; form/intake/match/appointment
      triggers → legacy subject mapping; others → surrogate)
- [ ] feat: template save/use/publish preserve exact subject; `use_template` routes through
      `workflow_service.create_workflow`; donor permission checks in templates router;
      ambiguous legacy donor-intent templates error as repair-required, never silently
      enabled
- [ ] feat: platform template publish/version snapshots and admin config export/import carry
      `subject_type`
- [ ] chore: web template contract sync (`subject_type` in template types/UI)

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
- [ ] Operations: permission-based donor navigation and correspondence access (replace
      developer-role gates in sidebar and `record_correspondence` router); mount existing
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
