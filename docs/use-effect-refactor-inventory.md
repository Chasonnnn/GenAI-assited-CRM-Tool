# React useEffect refactor inventory

Status: baseline classification for the no-ad-hoc-useEffect refactor.

Baseline commit: `f9c22b39de8a52ffdca6c1ce773747e1fbe17647`

Scope: production TypeScript under `apps/web/app`, `apps/web/components`, and `apps/web/lib`. Tests, generated output, build artifacts, and dependencies are excluded.

## Baseline

- 144 `useEffect` calls across 75 production files.
- 86 **REPLACE**: ordinary React data flow, direct fetching, route choreography, polling, or ref synchronization that should use a more explicit primitive.
- 46 **CONTAIN**: valid browser or external-system synchronization that currently lives in a page or component and should move behind a narrowly named hook with complete cleanup.
- 12 **RETAIN**: valid external synchronization already isolated in a named hook with dependencies and cleanup.

Line numbers below identify the baseline commit. As slices land, completion evidence is the current source plus tests and validation—not the continued existence of a baseline line number.

## Progress

- 28 **REPLACE** Effects removed and 10 **CONTAIN** call sites consolidated behind one tested mount hook; 107 production `useEffect` calls remain.
- `PublishDialog`: open-session edits now survive equivalent prop rerenders; close/reopen resets through mounting.
- `AppointmentDetailDialog`: draft state is scoped to the open appointment and no longer loops or resets on fresh query objects.
- Ticket detail: reply and ticket-edit drafts are keyed to the ticket ID rather than rehydrated from every query object.
- Mount-only browser synchronization now uses the reviewed `useMountEffect` boundary across auth, offline detection, AI cleanup/focus, dashboard analytics/cleanup, templates URL state, and the floating scrollbar.
- AI, email, and Meta integration forms initialize at loading-to-loaded boundaries instead of rehydrating from every query object.
- Campaign edit drafts hydrate from the explicit open action rather than campaign query identity.
- Social-link, personal-signature, and onboarding-profile drafts now preserve user edits across equivalent query/auth refreshes.
- Invitation and current-user loading now use separate TanStack Query keys, preventing older invitation responses from replacing the active route.
- Email compose state is scoped to recipient/open sessions, and untouched template fields derive from live query data while explicit user edits remain stable.
- The operations dashboard fetch is owned by a stable TanStack Query key, so fresh data survives route remounts without duplicate requests or loading flashes.
- Platform alerts and agencies use filter-keyed queries, isolating out-of-order responses and reusing fresh route data.
- Support-session capabilities refetch after transient failures and derive the effective access mode without hydration Effects.
- Availability drafts derive from refreshed server rules for untouched days while explicit edits remain user-owned.
- Automation defaults authorized admins to org scope before the first query, and email preview HTML derives from the active source without stale cross-preview state.
- Test-email variables derive from the current recipient until a field is explicitly edited, so recipient changes cannot leave untouched samples stale.
- Self-service appointment management and embedded public forms use route-keyed queries and keyed local sessions, preventing older route responses and drafts from replacing the active route.
- Compliance policy fields derive from refreshed server data until the exact field is edited, preserving drafts without freezing untouched policy values.
- Surrogate and intended-parent timelines render the current stage open in initial server HTML and reset their open-stage state directly when the current stage changes.
- Meta form mappings combine refreshed server rules with explicit per-column overrides, preventing background refreshes from discarding unsaved mapping work.
- Each completed slice has a red behavior test, green targeted suite, ESLint, TypeScript, diff validation, and its own conventional commit.

## Verdict rules

- **REPLACE** with render-time derivation, an event or reducer transition, TanStack Query, route/server guards, `useEffectEvent`, conditional rendering, or keyed remounting.
- **CONTAIN** by extracting a narrowly named synchronization hook. The hook must retain exhaustive dependencies and cleanup.
- **RETAIN** only when the Effect synchronizes with a genuine external system and is already contained in a named hook.

## Inventory

| Baseline location | Verdict | Rationale |
|---|---|---|
| `apps/web/app/(app)/ai-assistant/page.tsx:329` | REPLACE | Replace callback/state ref synchronization with useEffectEvent or a render-safe latest-value boundary. |
| `apps/web/app/(app)/ai-assistant/page.tsx:356` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/(app)/ai-assistant/page.tsx:382` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/app/(app)/ai-assistant/page.tsx:404` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/ai-assistant/page.tsx:417` | CONTAIN | Keep the external DOM, editor, subscription, or abort lifecycle but move it behind a narrowly named hook. |
| `apps/web/app/(app)/ai-assistant/page.tsx:426` | CONTAIN | Keep the external DOM, editor, subscription, or abort lifecycle but move it behind a narrowly named hook. |
| `apps/web/app/(app)/automation/campaigns/[id]/page.client.tsx:1208` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/automation/campaigns/[id]/page.client.tsx:1216` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/automation/email-templates/page.tsx:1027` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/automation/email-templates/page.tsx:1075` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/automation/email-templates/page.tsx:1238` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/automation/page.client.tsx:1014` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/automation/page.client.tsx:1025` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/automation/page.client.tsx:1032` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/automation/page.client.tsx:784` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/automation/page.client.tsx:856` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/dashboard/components/dashboard-filter-bar.tsx:38` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/dashboard/components/dashboard-filter-bar.tsx:47` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/(app)/dashboard/context/dashboard-filters.tsx:236` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/dashboard/page.client.tsx:124` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/(app)/dashboard/page.client.tsx:85` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/(app)/intended-parents/matches/page.client.tsx:140` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/(app)/intended-parents/page.client.tsx:567` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/(app)/matches/page.tsx:329` | REPLACE | Use the shared debounced-value hook so timer synchronization is not embedded in the page. |
| `apps/web/app/(app)/settings/audit/page.tsx:736` | REPLACE | Move polling into the owning TanStack Query through a conditional refetchInterval. |
| `apps/web/app/(app)/settings/compliance/page.tsx:521` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/settings/compliance/page.tsx:535` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/settings/integrations/meta/forms/[id]/page.tsx:611` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/settings/integrations/page.tsx:1531` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/settings/integrations/page.tsx:3964` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/settings/integrations/page.tsx:739` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/settings/intelligent-suggestions-section.tsx:729` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/(app)/settings/page.tsx:860` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/settings/pipelines/page.tsx:1564` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/settings/pipelines/page.tsx:1659` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/settings/queues/page.tsx:88` | REPLACE | Move authorization or route redirection to the route/server guard or the explicit auth transition. |
| `apps/web/app/(app)/surrogates/page.client.tsx:594` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/(app)/surrogates/unassigned/page.client.tsx:58` | REPLACE | Move authorization or route redirection to the route/server guard or the explicit auth transition. |
| `apps/web/app/(app)/surrogates/unassigned/page.client.tsx:65` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/(app)/tasks/page.client.tsx:232` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/tasks/page.client.tsx:331` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/(app)/tasks/page.client.tsx:354` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/tasks/page.client.tsx:98` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/app/(app)/tickets/[ticketId]/page.tsx:79` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/(app)/welcome/page.tsx:100` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/app/(app)/welcome/page.tsx:94` | REPLACE | Move authorization or route redirection to the route/server guard or the explicit auth transition. |
| `apps/web/app/auth/duo/callback/page.client.tsx:161` | CONTAIN | Keep the browser/auth callback lifecycle but isolate it in a named Duo callback flow hook with cleanup. |
| `apps/web/app/auth/duo/callback/page.client.tsx:182` | CONTAIN | Keep the browser/auth callback lifecycle but isolate it in a named Duo callback flow hook with cleanup. |
| `apps/web/app/book/self-service/[orgId]/manage/[token]/page.tsx:576` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/embed/forms/[slug]/page.client.tsx:295` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/embed/forms/[slug]/page.client.tsx:308` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/embed/forms/[slug]/page.client.tsx:344` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/intake/[slug]/page.client.tsx:1044` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/intake/[slug]/page.client.tsx:1071` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/intake/[slug]/page.client.tsx:1184` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/invite/[id]/page.client.tsx:40` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/invite/[id]/page.client.tsx:63` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/mfa/page.client.tsx:63` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/mfa/page.client.tsx:78` | REPLACE | Move authorization or route redirection to the route/server guard or the explicit auth transition. |
| `apps/web/app/ops/agencies/[orgId]/page.client.tsx:107` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/ops/agencies/[orgId]/page.client.tsx:175` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/ops/agencies/[orgId]/page.client.tsx:214` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/ops/agencies/page.client.tsx:84` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/ops/alerts/page.client.tsx:139` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/ops/layout.tsx:89` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/ops/page.client.tsx:86` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/app/ops/templates/page.client.tsx:340` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/app/ops/templates/workflows/[id]/page.client.tsx:2146` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/app/ops/templates/workflows/[id]/page.client.tsx:2151` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/ai/AIChatPanel.tsx:503` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/ai/AIChatPanel.tsx:517` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/components/ai/AIChatPanel.tsx:526` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/ai/AIChatPanel.tsx:530` | CONTAIN | Keep the external DOM, editor, subscription, or abort lifecycle but move it behind a narrowly named hook. |
| `apps/web/components/app-shell-client.tsx:43` | REPLACE | Move authorization or route redirection to the route/server guard or the explicit auth transition. |
| `apps/web/components/app-sidebar.tsx:619` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/app-sidebar.tsx:625` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/appointments/AppointmentSettings.tsx:274` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/appointments/AppointmentsList.tsx:258` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/email/EmailAttachmentsPanel.tsx:123` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/components/email/EmailAttachmentsPanel.tsx:95` | REPLACE | Replace callback/state ref synchronization with useEffectEvent or a render-safe latest-value boundary. |
| `apps/web/components/email/EmailComposeDialog.tsx:451` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/email/EmailComposeDialog.tsx:463` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/import/CSVUpload.tsx:607` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/inline-edit-field.tsx:86` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/intended-parents/IntendedParentActivityTimeline.tsx:344` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/notification-bell.tsx:53` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/offline-banner.tsx:49` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/offline-banner.tsx:68` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/ops/agencies/SupportSessionDialog.tsx:161` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/components/ops/templates/PublishDialog.tsx:58` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/rich-text-editor.tsx:112` | CONTAIN | Keep the external DOM, editor, subscription, or abort lifecycle but move it behind a narrowly named hook. |
| `apps/web/components/search-command.tsx:159` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/session-expired-dialog.tsx:32` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/ActivityTimeline.tsx:663` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/surrogates/detail/SurrogateDetailLayout/context.tsx:300` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/components/surrogates/detail/SurrogateDetailLayout/context.tsx:380` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/interviews/CommentCard.tsx:208` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/interviews/CommentCard.tsx:214` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/interviews/CommentCard.tsx:78` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/interviews/InterviewComments/ConnectorLines.tsx:17` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/interviews/InterviewComments/hooks/useCommentPositions.ts:22` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/components/surrogates/interviews/InterviewComments/hooks/useCommentPositions.ts:40` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/components/surrogates/interviews/InterviewComments/hooks/useCommentPositions.ts:50` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/components/surrogates/interviews/InterviewComments/hooks/useCommentPositions.ts:69` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/components/surrogates/interviews/InterviewComments/hooks/useInteractionClasses.ts:42` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/components/surrogates/interviews/InterviewComments/hooks/useInteractionClasses.ts:56` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/components/surrogates/interviews/InterviewComments/TranscriptPane.tsx:30` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/interviews/InterviewTab/context.tsx:351` | REPLACE | Move polling into the owning TanStack Query through a conditional refetchInterval. |
| `apps/web/components/surrogates/interviews/SelectionPopover.tsx:134` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/interviews/SelectionPopover.tsx:146` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/interviews/SelectionPopover.tsx:161` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/interviews/SelectionPopover.tsx:47` | REPLACE | Replace callback/state ref synchronization with useEffectEvent or a render-safe latest-value boundary. |
| `apps/web/components/surrogates/interviews/TranscriptEditor.tsx:189` | CONTAIN | Keep the external DOM, editor, subscription, or abort lifecycle but move it behind a narrowly named hook. |
| `apps/web/components/surrogates/interviews/TranscriptViewer.tsx:223` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/MassEditStageModal.tsx:930` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/surrogates/MassEditStageModal.tsx:942` | REPLACE | Replace internal state synchronization with derivation, an event/reducer transition, or keyed mounting. |
| `apps/web/components/surrogates/SurrogatesFloatingScrollbar.tsx:336` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/SurrogatesFloatingScrollbar.tsx:375` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/surrogates/SurrogatesFloatingScrollbar.tsx:478` | CONTAIN | Keep the external DOM, editor, subscription, or abort lifecycle but move it behind a narrowly named hook. |
| `apps/web/components/ui/calendar.tsx:187` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/components/ui/carousel.tsx:42` | REPLACE | Replace callback/state ref synchronization with useEffectEvent or a render-safe latest-value boundary. |
| `apps/web/components/ui/carousel.tsx:64` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/components/ui/carousel.tsx:69` | CONTAIN | Keep the external DOM, editor, subscription, or abort lifecycle but move it behind a narrowly named hook. |
| `apps/web/lib/auth-context.tsx:108` | REPLACE | Move authorization or route redirection to the route/server guard or the explicit auth transition. |
| `apps/web/lib/auth-context.tsx:80` | REPLACE | Move direct request and loading state into TanStack Query or the route data boundary. |
| `apps/web/lib/context/ai-context.tsx:103` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/context/ai-context.tsx:110` | CONTAIN | External browser or platform synchronization is valid, but should live behind a narrowly named hook with cleanup. |
| `apps/web/lib/context/ai-context.tsx:173` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-automation-form-builder-page.ts:431` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-automation-form-builder-page.ts:438` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-automation-form-builder-page.ts:447` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-automation-form-builder-page.ts:459` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-automation-form-builder-page.ts:474` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-automation-form-builder-page.ts:542` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/lib/forms/use-automation-form-builder-page.ts:819` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-template-form-builder-page.ts:237` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-template-form-builder-page.ts:245` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-template-form-builder-page.ts:271` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-template-form-builder-page.ts:283` | REPLACE | Replace internal state choreography with derivation, an event/reducer transition, or a keyed component boundary. |
| `apps/web/lib/forms/use-template-form-builder-page.ts:348` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/lib/hooks/use-dashboard-socket.ts:49` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/lib/hooks/use-dashboard-socket.ts:62` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/lib/hooks/use-debounced-value.ts:13` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
| `apps/web/lib/hooks/use-notification-socket.ts:107` | RETAIN | Valid external synchronization is already contained in a named hook with cleanup. |
