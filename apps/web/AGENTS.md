# Frontend guidance

Read the repository-root `AGENTS.md` first. For visual work, also read `../../docs/layouts.md`.

## Next.js context

For any Next.js task, search `../../.next-docs` and read the smallest relevant set before coding. Do not rely on remembered framework behavior. If the local docs are missing, regenerate them with the repository-approved codemod. Do not load or copy the full documentation index into agent context.

## Architecture and UI gotchas

- TanStack Query owns server state. Zustand is for UI-only state; do not mirror query data into a store.
- Extend the repository's customized shadcn/Base UI primitives and established layout system. Do not replace the component system in a focused change.
- Preserve the cookie-auth API contract: browser requests use credentials, and mutations include the repository's CSRF header.
- Shared Base UI `SelectValue` may render the stored id, enum, slug, or sentinel. Define one label map/helper and reuse it in the trigger, filter chips, badges, summaries, cells, and empty/default states.
- When one dropdown leaks a raw value, audit sibling filters in the feature area. Add or update tests for the trigger label and every related chip, badge, or summary label.
- Treat `lib/constants/stages.generated.ts` and other generated contracts as outputs. Change their backend source and regenerate them rather than editing them by hand.
- Match surrounding component composition, error presentation, loading states, and responsive behavior. Use a standalone HTML prototype first when user taste or layout direction is the main unknown.

## Verification

Use the existing scripts in `package.json`:

- `pnpm run check` for type checking, lint, and the primary test suite.
- `pnpm run test:all` for cross-cutting or integration-sensitive changes.
- Focused Vitest files while iterating.

For UI changes, verify the actual rendered states that changed, including loading, empty, error, and populated states when applicable. Start the dev server only for active QA, record its PID, and stop it at handoff.
