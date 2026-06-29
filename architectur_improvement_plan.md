# Architecture Improvement Plan

This plan records the production-risk audit and the recommended sequence for
deepening shallow modules. The goal is better locality, leverage, and testability
without turning production traffic into a broad refactor target.

## Completed Milestones

| Topic | Status | Notes |
| --- | --- | --- |
| Ticket Threading | Completed | Gmail-thread fallback stitching is covered by regression tests, and the helper collision has been removed without changing routes, jobs, ticket visibility, or threading precedence. |
| Pipeline Semantics | Completed | Backend default semantics now generate frontend fallback constants, with tests for canonical backend values, generated-file freshness, frontend fallback behavior, server overrides, and custom-stage fallback. |
| Public Intake Parity | Completed | Hosted and embedded intake now have parity coverage around submission success, duplicate/idempotency behavior, workflow outcomes, attribution/consent/tracking side effects, file-field policy, parent-message privacy, and hosted multipart upload alignment. |

## Recommended Sequence

| Rank | Topic | Production risk | Recommendation |
| --- | --- | --- | --- |
| 1 | Public Intake | High | Use the parity suite to fix concrete defects first; deepen only behind existing adapters after public outcomes stay protected. |
| 2 | Form Builder Lifecycle | Medium | Extract common lifecycle logic after autosave and publish contract tests exist. |
| 3 | Query Resource Modules | Low immediate risk, medium migration risk | Defer broad migration unless latency or cache correctness becomes measurable pain. |
| 4 | Ticket Threading Extraction | Medium-high refactor risk | Revisit only after shared-inbox activation needs a deeper module interface. |
| 5 | Pipeline Semantics Evolution | Medium | Treat future stage behavior changes as normal generated-contract changes, not split-runtime edits. |

## Topic Audits

### Ticket Threading

The ticketing implementation had a helper-name collision around Gmail thread
lookup. The narrow production fix has landed: the occurrence-stitch helper keeps
the UUID-returning behavior, the legacy outbound helper has a distinct private
name, and Gmail-thread fallback stitching is covered by regression tests.

Trade-off: a deeper Ticket Threading module could improve locality by putting
thread lookup precedence, stitch reasons, and confidence assignment behind one
small interface. That extraction is still not the next production move because
it would touch mailbox ingestion, legacy surrogate email mirroring, and ticket
linking behavior at once.

Recommendation: keep the regression fix narrow. Revisit module extraction only
if shared-inbox activation needs a stable ticket-threading interface for mailbox
admin, link candidates, reply identity, or SLA behavior.

### Pipeline Semantics

Pipeline semantics previously existed in backend Python and frontend TypeScript.
That split weakened leverage because a stage behavior change had to be made and
verified in more than one place. The frontend fallback now consumes generated
backend-owned default semantics, while explicit server-provided semantics still
override generated defaults.

Trade-off: making pipeline semantics a single generated source would improve
locality and reduce silent UI/backend disagreement. The risk is that changing
frontend fallback semantics can alter production UI behavior before every route
is confirmed to receive server-provided semantics. That risk is now mitigated by
tests for canonical values, generated-file freshness, override behavior, and
custom-stage fallback behavior.

Recommendation: keep backend `StageSemantics` canonical and preserve the
generation guardrail. Future stage changes should update backend defaults and
regenerate frontend constants rather than editing fallback logic by hand.

### Public Intake

Public Intake coordinates validation, published versions, embed sessions,
idempotency, attribution, consent, submission creation, workflow triggers, and
tracking. The current interface is production-proven, but the implementation
reaches across private helper seams in form submission code.

Trade-off: a deeper Public Intake module would improve locality for applicant
submission behavior and make tests exercise the same interface used by routes.
The production risk is high because this path handles public traffic, PII,
consent, duplicate protection, and tracking policy.

Recommendation: do not big-bang this work. Preserve existing route interfaces
and keep the adapter-preserving parity tests green before moving behavior behind
a deeper module. Treat privacy-safe tracking and canonical lead events as
explicit acceptance criteria.

Completed first milestone: hosted intake and iframe embed flows now have
coverage for success paths, unresolved duplicate conflicts, idempotent replay,
workflow-pending outcomes, workflow-created lead metadata, consent and
attribution persistence, privacy-safe tracking and CRM dataset side effects,
embed readiness, file-field policy, parent-message privacy, and hosted multipart
file-key alignment.

Known follow-up: embedded intake remains intentionally fileless. If product
needs iframe uploads later, that should be a separate design with storage,
privacy, CSP, and UX acceptance tests. Plain workflow-pending hosted submissions
also should not gain request-level UTM storage through incidental refactoring;
that is a separate schema decision.

### Form Builder Lifecycle

Automation forms and platform templates both manage draft state, dirty
fingerprints, autosave, versioning, preview, publish, and validation. The
duplicate lifecycle implementation is real, but some differences are intentional:
template saves are queued and versioned, while automation form saves include
mappings, intake links, and share prompts.

Trade-off: a shared lifecycle module could improve leverage for editor behavior
and make autosave easier to reason about. The risk is accidental changes to
published forms, lost mappings, stale-version handling, or save ordering.

Recommendation: add lifecycle contract tests first, then extract only the common
implementation behind explicit automation and template adapters.

### Query Resource Modules

TanStack Query usage is centralized enough to have common retry policy, but
individual hook modules still carry local invalidation recipes. Server route
resource checks currently forward auth/org headers and return route status, not
reusable data.

Trade-off: deeper query resource modules could improve cache locality and reduce
duplicated invalidation logic. The risk is mixing server-rendered data, cookies,
org scoping, auth redirects, and client mutation invalidation in production.

Recommendation: defer broad migration. If this becomes necessary, pilot one
low-risk internal detail route with tests for 401, 403, 404, org headers, and
post-mutation freshness before expanding the pattern.

## Immediate Milestone

Use the Public Intake parity layer before deeper refactors:

1. Keep the hosted and embed parity suite green while fixing concrete defects.
2. Preserve hosted multipart uploads and embedded JSON/session-based fileless
   submissions as separate policies unless product explicitly changes that
   contract.
3. Treat any deeper Public Intake module as an adapter-preserving extraction,
   not a public route redesign.
4. Keep privacy-safe tracking and canonical lead events as acceptance criteria.

## Guardrails

- Treat each topic as a separate release-sized change.
- Prefer parity and contract tests before deepening production-critical modules.
- Do not introduce seams unless at least two adapters or callers make the seam
  real.
- Use the module interface as the test surface; avoid tests that depend on
  internal implementation details unless they are temporary regression guards.
