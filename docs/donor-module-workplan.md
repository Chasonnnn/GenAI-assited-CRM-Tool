# Donor Module Workplan

## Product Decisions

| Area | Decision |
|---|---|
| Record model | One organization-owned donor record with immutable `donor_type = egg | sperm`. |
| Navigation | One developer-only `Donors (beta)` module with Egg Donors and Sperm Donors sub-tabs until explicit release approval. |
| Identifier | Organization-local, human-readable donor numbers starting at `D10001`; UUIDs remain internal route and relationship keys. |
| Pipelines | Egg donors and sperm donors have separate configurable pipelines, stages, semantics, automation triggers, reporting filters, and dashboard views. |
| Duplicate identity | An active email address can belong to only one donor across both donor types. Archived records do not block a new active record; restoring rechecks uniqueness. |
| Donor type changes | Donor type is immutable after creation because changing it would invalidate pipeline history, intake provenance, automation context, and reporting. |
| Matching | `Matched` is a deliberate pipeline transition. A new donor-matching relationship model is deferred until its parties and lifecycle are defined. |
| Profile photo | Hosted donor forms require one PNG or JPEG profile photo and store it through the attachment system. Meta lead forms do not provide a compatible file-upload payload, so photo collection remains a hosted-form or post-conversion step. |
| Communication | Donor campaigns support reviewed email delivery. SMS is blocked until donor-specific consent and opt-out requirements are defined. |
| Deletion | Donor erasure is organization-scoped, legal-hold aware, worker-safe, and removes or tombstones related remote Google Tasks and stored files. |

## Pipeline Definitions

### Egg Donor

1. New
2. Contacted
3. Pre-Screening
4. Application Submitted
5. Medical Records Review
6. Psychological Screening
7. Ready to Match
8. Matched
9. Cycle in Progress
10. Retrieval Complete
11. On-Hold
12. Disqualified
13. Closed

### Sperm Donor

1. New
2. Contacted
3. Pre-Screening
4. Application Submitted
5. Semen Analysis
6. Medical & Genetic Screening
7. Available
8. Matched
9. Collection in Progress
10. Donation Complete
11. On-Hold
12. Disqualified
13. Closed

The two stage catalogs are independent. Shared labels do not imply shared stage IDs, configuration, history, or automation behavior.

## Workstreams and Acceptance Criteria

### 1. Domain, Persistence, and Migration

- Add donor type, donor record, and append-only donor stage-history models.
- Encrypt email and phone; retain normalized hashes for exact duplicate detection and lookup.
- Enforce organization-scoped donor-number and active-email uniqueness in PostgreSQL.
- Seed one default egg-donor pipeline and one default sperm-donor pipeline per organization.
- Generate frontend stage metadata from the backend stage source of truth.
- Treat downgrades as destructive: lock donor data and dependencies, block legal holds or active work, and remove donor-owned data without leaving orphan PII.

Acceptance:

- New organizations receive both pipelines with distinct stage IDs.
- Existing organizations receive both pipelines without changing surrogate or intended-parent pipelines.
- A donor can move only to an active stage in the default pipeline for the donor's organization and type.
- Cross-organization stage, owner, donor, history, and relationship IDs are rejected or return not found.

### 2. Donor API and Permissions

- Add list, create, detail, update, archive, restore, stage-change, history, and note endpoints.
- Add `view_donors`, `edit_donors`, `archive_donors`, and `change_donor_status` permissions.
- Require CSRF protection on mutations and authenticated organization membership on every access.
- Log donor record, note, and protected-data access without logging raw PII.
- Preserve donor type and complete stage-history snapshots across edits and pipeline-label changes.

Acceptance:

- Every read and write has a cross-organization negative test.
- Archived donors cannot change stage and restores cannot violate active-email uniqueness.
- Required stage-entry reasons and role-based stage semantics are enforced server-side.

### 3. Donor User Experience

- Add `Donors (beta)` to the main navigation for the developer role only; keep backend donor permissions intact for QA and future rollout.
- Add Egg Donors and Sperm Donors sub-tabs with independent pipeline filters.
- Match existing list, search, pagination, empty, loading, error, permission, and archive patterns.
- Display Donor #, name, contact information, state, education, stage, and creation date.
- Add donor create/edit dialogs and a detail page with profile photo, notes, documents, tasks, and stage history.
- Display human-readable donor numbers anywhere users identify a donor; retain UUIDs only in internal links and API relationships.

Acceptance:

- Switching donor tabs cannot retain an invalid stage filter from the other pipeline.
- Donor type cannot be edited after creation.
- Profile-photo and document access follows donor permissions and organization scope.

### 4. Hosted Intake Forms and Attachments

- Add `egg_donor` and `sperm_donor` as hosted-form lead kinds.
- Support mappings for full name, email, phone, state, education, and profile photo.
- Require full name, email, and exactly one valid profile photo before publishing or accepting a donor intake.
- Preserve published lead-kind, schema, mapping, consent, and tracking snapshots for historical submissions.
- Create a reviewable donor intake lead before promotion to a donor record.
- Reuse attachment scanning, signed access, retention, legal-hold, and durable storage-cleanup behavior.

Acceptance:

- Changing a form's lead kind is blocked after submissions exist.
- Promotion creates the correct donor type and cannot be redirected by later form changes.
- Replayed submissions and promotion attempts remain idempotent.
- Infected or failed profile-photo scans cannot remain attached to a donor.

### 5. Meta Lead Forms

- Add Surrogate, Egg Donor, and Sperm Donor classification to Meta form configuration.
- Snapshot the reviewed classification onto every Meta lead before conversion.
- Restrict donor mappings to donor fields and route conversion to the matching donor pipeline.
- Prevent a form reclassification from redirecting previously received or converted leads.
- Exclude profile-photo mapping because Meta lead payloads do not supply compatible file uploads.

Acceptance:

- Unmapped Meta forms do not silently default stored leads to the wrong module.
- Mapping, preview, reprocessing, conversion, rollback, and duplicate checks are organization-scoped and donor-type safe.
- A converted donor lead exposes the human-readable donor number in operational UI.

### 6. Tasks, Calendar, Google Tasks, and Notifications

- Allow tasks to relate to one donor and render donor links in task lists, approvals, edit dialogs, calendar events, and notifications.
- Validate donor visibility in addition to task permissions before exposing related-record data.
- Support donor workflow-created tasks and appointment/reminder jobs.
- Persist remote Google-task identity and durable deletion tombstones for donor erasure and ownership reassignment.
- Reconcile ambiguous Google create requests before retrying, resolve the concrete default task-list ID, and validate exact active membership before provider calls.
- Block member deprovisioning while remote donor cleanup still requires that member's credentials.

Acceptance:

- Donor task creation, edit, assignment, queue transition, archive behavior, synchronization, retry, and erasure have regression tests.
- A stale worker claim, provider timeout, transaction failure, or inbound synchronization cannot recreate erased donor content or leave an untracked remote copy.

### 7. Workflow Automation

- Add donor-created, donor-updated, donor-assigned, and donor-stage-changed triggers.
- Add donor as a workflow subject and donor/owner as notification-recipient targets.
- Resolve stages dynamically from the selected egg- or sperm-donor pipeline.
- Preserve donor type, pipeline, stage, subject, owner, and organization in execution context.
- Fail closed when the subject is missing, cross-organization, archived, or from the wrong pipeline type.

Acceptance:

- Automation builders expose both donor types independently.
- Every configured stage in each pipeline can participate in stage-based automation.
- Task, email, notification, delay, condition, assignment, and status actions preserve existing approval and human-review contracts.

### 8. Campaigns and Templates

- Add egg-donor and sperm-donor recipient sources, filters, previews, counts, snapshots, and email-template variables.
- Require both campaign and donor permissions for donor audiences.
- Resolve recipient identity from the immutable launch snapshot rather than a mutable later query.
- Block donor SMS campaigns until a donor-specific consent contract exists.

Acceptance:

- Preview and delivery contain only the selected organization and donor type.
- Archived, duplicate, invalid, unsubscribed, and suppressed recipients follow existing email rules.
- A user who loses donor access cannot preview or launch donor campaigns.

### 9. Search, Analytics, Dashboard, and Reporting

- Add donors to global and command search with donor number, name, exact email, and normalized phone matching.
- Add donor summary, stage distribution, and time-series endpoints with required donor type.
- Add Egg Donor and Sperm Donor selectors to dashboard pipeline distribution and reports.
- Add stuck-donor attention items with permission-safe navigation.
- Include organization, donor type, pipeline, owner, archive, date, period, and timezone inputs in query and cache identity.

Acceptance:

- Reports require both report and donor-view permissions; dashboard data requires both dashboard and donor-view permissions.
- Stage distributions return all active stages, including zero-count stages, in configured order.
- Pipeline filters must belong to the organization and selected donor type.

### 10. Portability, Retention, and Compliance

- Add donor CSV export/import with stage, owner, history, and bounded profile-photo round-trip support.
- Keep all-import operations atomic and reject cross-organization/global-ID collisions.
- Add donor and unconverted donor-lead retention policies.
- Respect direct and inherited legal holds on donors, notes, files, submissions, and intake leads.
- Lock donor dependents and active delivery/job leases before destructive purge.
- Schedule retry-safe storage and Google-task deletion in the same transaction as local erasure.

Acceptance:

- Export/import round trips donor type, D-number, encrypted contact data, pipeline stage, ownership, history, and validated profile-photo bytes.
- Failed imports leave neither partial rows nor orphaned stored objects.
- Retention cannot purge held data, leased work, active delivery, or data created concurrently with the purge.

### 11. Documentation and Release

- Update architecture, application, API, migration, and smoke-test documentation.
- Keep `Donors (beta)` and `Tickets (beta)` visibly named in the sidebar and restricted to the developer role until explicit release approval.
- Regenerate and verify the OpenAPI contract and frontend stage constants.
- Run backend lint, the complete API suite, migration-head/current/check, focused migration reversibility tests, frontend check, React health review, and diff whitespace validation.
- Perform live Meta, object-storage, email, and Google integration QA only with configured non-production credentials.
- Keep commit, push, deployment, migration application, and production configuration behind explicit authorization.

## Release Sequence

1. Keep the commits local until explicit authorization to push, merge, migrate, or release.
2. Back up the target database and verify the migration head in a staging environment.
3. Apply migrations and confirm both donor pipelines and stage catalogs for an existing and a newly created organization.
4. Configure donor permissions for each role and confirm hidden-navigation behavior.
5. Publish one egg-donor and one sperm-donor hosted test form; verify photo upload, review, and promotion.
6. Configure one Meta form per donor type; verify classification snapshots and conversion without photo mapping.
7. Exercise donor tasks, workflow triggers, email campaign preview, dashboard, reports, export/import, archive/restore, and retention dry-run.
8. Run cross-organization negative checks in the deployed environment without production PII.
9. Enable production use only after staging evidence is reviewed.

## Completion Gate

The module is complete when both donor pipelines are independently configurable and operational across CRUD, intake, Meta routing, attachments, tasks, automation, campaigns, search, analytics, dashboard, portability, and compliance; every applicable permission and tenant boundary has negative coverage; all local validation gates pass; and any live integration or deployment work is reported separately from local verification.
