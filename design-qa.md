# AI Chat Panel Design QA

## Artifacts

- Source visual truth: `.gstack/qa-reports/ai-chat-panel-audit/02-proposed-panel.png`
- Browser-rendered implementation: `.gstack/qa-reports/ai-chat-panel-audit/03-implemented-panel.png`
- Equal-state comparison: `.gstack/qa-reports/ai-chat-panel-audit/04-reference-vs-implementation.png`
- Mobile implementation: `.gstack/qa-reports/ai-chat-panel-audit/05-mobile-panel.png`
- Authentic final empty state: `.gstack/qa-reports/ai-chat-panel-audit/06-authentic-empty-state.png`
- Interactive before/after review: `.gstack/qa-reports/ai-chat-panel-before-after.html?view=after`
- Previous root QA preserved at: `docs/pregnancy-tracker-design-qa-2026-07-15.md`

## Comparison Setup

- Reference viewport: 1280 × 720 CSS pixels
- Implementation viewport: 1280 × 720 CSS pixels
- Source image: 1280 × 720 pixels at 1× density
- Implementation image: 1280 × 720 pixels at 1× density
- Combined comparison: 2560 × 720 pixels, reference on the left and implementation on the right
- Representative state: surrogate context, user request, assistant response, and an email action awaiting human review
- Authentic state: seeded surrogate record with an empty local AI conversation

## Full-View Comparison Evidence

The equal-state comparison covers the complete page and drawer at the same viewport and density. The implementation matches the approved target's 400px right-side drawer, compact header, context badges, message hierarchy, review card, prompt strip, and multiline composer. The source is shown inside a labeled presentation frame; the production implementation correctly occupies the live application viewport without that frame.

## Focused Region Evidence

- Header and context: compact AI identity, ready state, close control, surrogate number, and friendly lifecycle label
- Conversation: distinct user and assistant treatments, compact type, readable Markdown, and live-log semantics
- Proposed action: bounded shadcn card, human-review status, draft disclosure, and separate dismiss and approve controls
- Composer: shadcn input group and textarea, quick prompts, send/stop affordance, keyboard hint, and human-review reminder

These regions were visible together at native resolution, so additional crops were not needed to judge spacing, typography, border treatment, or state hierarchy.

## Responsive and Interaction Evidence

- Desktop drawer: 400 × 720 pixels, non-modal, persistent workspace context
- Mobile drawer: 390 × 844 pixels, full-width modal, no horizontal overflow, composer visible
- Escape and close controls return focus to the floating AI trigger
- Enter sends; Shift+Enter creates a newline
- Streaming can be stopped without allowing an older request to clear a newer request's state
- `Review draft` reveals action details without execution
- Only the second explicit `Approve and send` action executes; `Dismiss` rejects
- Final authentic browser state reported no console warnings or errors

## Comparison History

1. **P2 — Drawer width:** the first production render inherited a 384px responsive maximum from the shared Sheet. The drawer width and maximum were made explicit; the post-fix browser measurement is exactly 400px.
2. **P2 — Message density:** the first implementation used larger message type, causing the user prompt to wrap relative to the target. Panel-local message and rich-text type were tightened; the post-fix comparison matches the reference density.
3. **P2 — Focus return:** programmatic close initially left focus on the document body. A stable launcher marker and Sheet final-focus callback were added; both Escape and the close control now return focus to the AI trigger.
4. **Investigated, not a product defect — Mobile overlay:** a bottom-corner element was traced to TanStack Query and Next.js development tooling at an elevated development-only z-index. Product-only capture confirmed the drawer itself has no overlap.

## Findings

- No actionable P0, P1, or P2 visual or interaction differences remain.
- Accepted P3 difference: the implementation preserves the existing surrogate-only `Parse Schedule` quick prompt as a fourth item in the horizontal prompt scroller, while the proposal displays three prompts.
- No shadcn package or component-library upgrade is needed. Existing customized Base UI-backed primitives support the design; the shared Sheet received only additive overlay controls.
- The complete frontend run reaches the AI chat tests successfully but remains red on three source guards in unrelated concurrent email/integration work: a barrel API import, unused template-version exports, and a missing integration-settings helper split.

## Implementation Checklist

- [x] Uses shared shadcn/Base UI primitives and existing design tokens
- [x] Preserves human review before AI actions
- [x] Covers loading, empty, error, streaming, and proposed-action states
- [x] Uses friendly context labels instead of raw stored values
- [x] Includes desktop and mobile rendered QA
- [x] Includes equal-state, equal-viewport comparison evidence
- [x] Passes focused tests, TypeScript, ESLint, and whitespace validation

final result: passed
