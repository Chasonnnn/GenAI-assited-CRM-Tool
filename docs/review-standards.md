# Review standards

## Severity

- P0: data loss, cross-organization exposure, security hole, broken production path, or failed release. Blocks merge.
- P1: wrong behavior a user or job will hit, a missing invariant test, or a regression. Blocks merge.
- P2: maintainability, naming, or an edge case with low impact. Does not block.
- P3: style or preference. Does not block.

## Reporting

- Report each P0 and P1 finding with a concrete failure scenario.
- List P2 and P3 findings once, in one short list. Do not repeat them in later rounds.
- Do not raise a finding that only restates one of the judgement calls below without a concrete failure.

## Bot reviews

- Read all bot comments in one pass.
- Fix the real P0/P1 bugs in one push.
- Answer the rest with a one-line reason.
- Stop after that push. Do not fix new P2 comments that the push triggers unless the owner asks.

## Judgement calls

### Quality

- Internal product: do not preserve legacy behavior by default.
- Before a breaking API, data, or workflow change, state its impact and the migration or reset plan.
- Match completeness to the requested artifact. Production features include relevant loading, error, validation, and polish.
- Isolate prototypes and label them clearly.
- Preserve existing semantic and keyboard behavior. Broader accessibility work is separate scope unless requested.

### Backend

- FastAPI routers own transport and dependency wiring. Services own use-case logic and transaction boundaries.
- Domain writes and their audit/activity records commit or roll back atomically. Do not split transaction control across layers without a documented reason.
- Keep timezone-aware UTC and the existing Pydantic v2 / SQLAlchemy 2.0 idioms.
- Every router response goes through a declared Pydantic response schema. Never expose ORM objects or fields outside that schema.
- Validate and convert data at each boundary. Do not share mutable state across layers.
- External calls have timeouts and bounded retries. Handle races, cancellation, and idempotency explicitly.
- Never swallow exceptions or hide failures behind unbounded retries.

### Frontend

- TanStack Query owns server state; Zustand owns UI-only state. Do not mirror query data into a store.
- Extend the customized shadcn/Base UI primitives. Do not replace the component system in a focused feature change.
- Shared Base UI `SelectValue` may expose a stored id, enum, slug, or sentinel. Map it through one label helper everywhere it appears: triggers, chips, badges, summaries, cells, and empty/default states.
- When one filter leaks a raw value, audit the sibling filters in the feature area. Test the trigger and the related labels.
- Do not add subtitles, helper text, or descriptive copy under headings, labels, cards, or settings by default. Add supporting copy only when the user asks for it or when it prevents misunderstanding or error. Never restate the heading.
- For visual work, match the component composition, loading/error states, and responsive behavior of neighboring pages.
- Use a standalone HTML prototype when user taste or layout direction is the main unknown.

### General

- Use nearby production code and behavior tests as references. Match local naming, comment density, transaction ownership, errors, and composition.
- Before adding a dependency, check the manifests under `apps/` and the installed library's docs and types. Do not assume a library lacks a feature.
- When code is duplicated on purpose, a comment says why.
- Record non-obvious decisions, compatibility constraints, and temporary workarounds with their reason and removal condition.
- Architecture decisions go in `docs/adr/`. Every TODO links to a tracked issue.
