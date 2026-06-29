# Architecture Improvement Plan

This plan records the production-risk audit and the recommended sequence for
deepening shallow modules. The goal is better locality, leverage, and testability
without turning production traffic into a broad refactor target.

## Recommended Sequence

| Rank | Topic | Production risk | Recommendation |
| --- | --- | --- | --- |
| 1 | Ticket Threading | Medium current bug risk, medium-high refactor risk | Fix the Gmail-thread regression narrowly first. Defer module extraction. |
| 2 | Pipeline Semantics | Medium | Add parity tests or generated semantics before changing runtime behavior. |
| 3 | Public Intake | High | Deepen only behind existing adapters after parity tests protect public outcomes. |
| 4 | Form Builder Lifecycle | Medium | Extract common lifecycle logic after autosave and publish contract tests exist. |
| 5 | Query Resource Modules | Low immediate risk, medium migration risk | Defer broad migration unless latency or cache correctness becomes measurable pain. |

## Topic Audits

### Ticket Threading

The current ticketing implementation has a helper-name collision around Gmail
thread lookup. One helper is used by `process_occurrence_stitch` and should
return a ticket id. Another legacy outbound helper returns a ticket object. The
shared name makes the stitch path fragile.

Trade-off: a deeper Ticket Threading module could improve locality by putting
thread lookup precedence, stitch reasons, and confidence assignment behind one
small interface. That extraction is not the first move in production because it
would touch mailbox ingestion, legacy surrogate email mirroring, and ticket
linking behavior at once.

Recommendation: first land the narrow regression fix with a test for Gmail-thread
fallback stitching. Keep ticket visibility, routes, jobs, and threading
precedence unchanged. Revisit module extraction only after the bug is covered.

### Pipeline Semantics

Pipeline semantics exist in backend Python and frontend TypeScript. The current
shape gives callers a convenient interface, but the implementation is split
across two runtimes and can drift. This weakens leverage because a stage behavior
change has to be made and verified in more than one place.

Trade-off: making pipeline semantics a single generated source would improve
locality and reduce silent UI/backend disagreement. The risk is that changing
frontend fallback semantics can alter production UI behavior before every route
is confirmed to receive server-provided semantics.

Recommendation: add cross-runtime parity tests or generated frontend semantics
first. Only remove or shrink the frontend fallback after payload coverage is
verified.

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
and create adapter-preserving parity tests before moving behavior behind a
deeper module. Treat privacy-safe tracking and canonical lead events as explicit
acceptance criteria.

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

Start with Ticket Threading as a production bug/regression fix:

1. Add a regression test for `process_occurrence_stitch` that exercises the
   Gmail-thread fallback path.
2. Preserve the occurrence-stitch helper that returns `UUID | None`.
3. Rename the legacy outbound Gmail-thread helper so the two implementations no
   longer share one private name.
4. Keep all public interfaces, mailbox jobs, routes, ticket visibility, and
   threading precedence unchanged.

## Guardrails

- Treat each topic as a separate release-sized change.
- Prefer parity and contract tests before deepening production-critical modules.
- Do not introduce seams unless at least two adapters or callers make the seam
  real.
- Use the module interface as the test surface; avoid tests that depend on
  internal implementation details unless they are temporary regression guards.
