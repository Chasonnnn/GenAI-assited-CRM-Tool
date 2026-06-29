# Surrogacy Force Improvement Plan - June 2026

Current as of 2026-06-29.

This document replaces the older multi-agent audit export. That export was useful
for discovery, but it included deleted `demos/` links and findings that have
since been fixed. Treat this file as the current implementation-oriented plan.

## Status Update

### Completed

- **Ticket Threading regression fix:** Gmail-thread fallback stitching is covered
  by regression tests, the helper-name collision has been removed, and the fix
  was verified through the backend and frontend gates.
- **Pipeline Semantics parity:** backend `StageSemantics` is now the canonical
  implementation for default surrogate stages. Frontend fallback semantics are
  generated into `apps/web/lib/constants/stages.generated.ts`, and tests now
  guard backend canonical values, generated-file freshness, frontend fallback
  behavior, server override behavior, and custom-stage fallback behavior.
- **Public Intake parity coverage:** hosted intake and embedded intake now have
  regression coverage for the production-sensitive split between multipart
  hosted submissions and JSON/session-based, fileless iframe submissions.
  Coverage includes duplicate/idempotency behavior, workflow-pending outcomes,
  workflow-created lead metadata, consent/attribution persistence, privacy-safe
  tracking side effects, embed readiness, file-field policy, parent-message
  privacy, and hosted multipart file-key alignment.
- **Demo artifact cleanup:** deleted demo assets are no longer referenced as
  runnable artifacts in this plan.

### Removed From The Live Finding List

- The duplicate `_find_ticket_by_gmail_thread` ticketing bug is no longer listed
  as a live production defect.
- The Pipeline Semantics split-runtime drift is no longer listed as pending
  groundwork. The remaining pipeline work should be normal feature evolution,
  not a semantics-parity cleanup.
- The initial Public Intake parity-test gap is no longer listed as unstarted.
  Deeper Public Intake module extraction remains a separate high-risk project.
- Static `demos/` links and mockup-only routing are removed. Future UX proposals
  should link to tracked specs, screenshots, or implementation PRs instead.

## Current Priority Sequence

| Rank | Topic | Production risk | Recommended next move |
| --- | --- | --- | --- |
| 1 | Public Intake | High | Use the new parity layer to fix concrete defects first; only extract a deeper module behind the existing route adapters after parity tests stay green. |
| 2 | Embedded Lead Forms | High | File-field blocking is now covered for iframe embeds; validate sandbox popup behavior and any remaining applicant-loss paths with public-route tests. |
| 3 | Contextual AI Assistant | Medium | Preserve task and intended-parent context end to end, and hide approval controls from users lacking approval permission. |
| 4 | Automation Reliability | Medium-high | Make scheduled workflow sweeps tolerant, surface workflow trigger failures, and stop silent success paths. |
| 5 | Tasks And Appointments | Medium | Fix silent recurring-task cap behavior and make appointment completion/no-show lifecycle real. |
| 6 | Shared Inbox Activation | Medium-high | Keep the ticketing backend fixed, then build pilot-readiness controls before broad role ungating. |
| 7 | Enterprise Compliance | High | Add SSO/SCIM planning, PHI read logging backstop, attachment retention, purge scheduling, and worker lease/retry hardening. |

## Recommended Workstreams

### 1. Public Intake Parity

Public Intake handles unauthenticated traffic, PII, consent, attribution,
published-version routing, duplicate protection, file handling, and workflow
side effects. It should be improved before broad internal UX activation because
it is the highest-risk public surface.

Completed first milestone:
- Added tests for hosted intake and embed submission success paths.
- Covered duplicate applicant behavior, idempotency replay, attribution storage,
  consent storage, workflow-pending responses, workflow-created lead metadata,
  and Meta/CRM dataset job creation without leaking sensitive health-history
  answers.
- Added explicit file-field behavior tests for the intended split: hosted intake
  accepts multipart uploads, while embedded intake remains iframe-only and
  fileless.
- Kept route shapes stable while adding coverage.

Known follow-up:
- Workflow-created hosted leads preserve link campaign/event metadata. Plain
  workflow-pending hosted submissions still should not grow ad-hoc request-level
  attribution storage without a separate schema decision.
- Public Intake module extraction is still high-risk. The next production move
  should be driven by concrete defects found through the parity suite, not by a
  broad reshuffle of unauthenticated submission code.

Do not start with a broad extraction. If implementation needs a deeper module,
create it behind the existing route/service adapter after parity coverage exists.

### 2. Embedded Lead Forms

The older audit called out embedded file-field forms as a silent failure risk.
This remains worth validating directly because it can lose applicants before a
staff member sees a record.

First milestone:
- Reproduce current file-field embed behavior with a test.
- Preserve the intended fileless embed policy by blocking client submission and
  treating privacy-safe embed settings with file fields as not ready.
- Add `allow-popups` only where needed for public policy links and verify the
  sandbox remains conservative.

### 3. Contextual AI Assistant

Task and intended-parent pages should not signal contextual AI if the drawer will
fall back to global mode. Approval buttons should be permission-aware so users do
not hit predictable server-side denials.

First milestone:
- Add frontend tests for task context persistence across drawer open/close.
- Add intended-parent context support only if backend contract support is added
  in the same change.
- Gate approval affordances by the same permission used by the backend.

### 4. Automation Reliability

Silent workflow failures are high-risk because staff believe follow-up is being
handled. The most valuable improvements are small: tolerance windows, visible
failure state, and truthful execution summaries.

First milestone:
- Add a tolerance window for scheduled workflow sweeps.
- Escalate workflow-trigger failures above debug-only logging.
- Fix misleading skip reasons and zero-count summaries.
- Add tests for scheduled, skipped, failed, and retried executions.

### 5. Tasks And Appointments

Recurring-task caps and appointment terminal states are operational workflows,
not edge cases. They should fail visibly and update lifecycle state honestly.

First milestone:
- Convert the recurring-task cap from a silent close into a blocking validation
  error with tests.
- Add appointment completion and no-show transitions, then make Upcoming/Past
  filters depend on lifecycle and time.

### 6. Shared Inbox Activation

Ticket Threading is now fixed at the regression layer, but broad inbox ungating
is still a product and operations rollout, not a one-line permission change.

Pilot-readiness checklist:
- Mailbox OAuth/admin UI for connect, pause, resume, sync, and backfill.
- Visible link candidates for surrogate and intended-parent records.
- Sanitized message bodies and attachment handling.
- Saved views for unassigned, assigned to me, unlinked, stale, and breaching SLA.
- Business-hours SLA policy and queue ownership rules.
- Collision-safe reply composer with send identity selection.

Only after those controls are in place should the UI gate move from developer
role checks to ticket permissions for intake specialists and case managers.

### 7. Enterprise Compliance

The platform has strong foundations: org scoping, encrypted PHI fields, audit
logging, MFA, and secret handling. The remaining enterprise work is mostly about
coverage and enforcement.

First milestone:
- Plan SSO/SCIM as a separate project.
- Add PHI read logging as middleware or another backstop rather than relying on
  every route to remember it.
- Schedule retention/purge jobs in production and extend retention to
  attachments and storage blobs.
- Add job leases, heartbeat/reaper behavior, and exponential backoff with jitter.

## Guardrails

- Treat old audit counts as historical, not current truth.
- Do not reference removed demo artifacts.
- Keep production-critical changes behind parity tests first.
- Prefer generated contracts when behavior spans backend Python and frontend
  TypeScript.
- Split commits by logical scope: code/test behavior, then documentation/status
  updates.
