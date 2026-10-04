# Frontend test audit evidence

Discovery at `bef1a04161f9d5f78fffe9cc15a0db8143a9995f` was completed before editing. The parent then authorized the 13 reductions after its refreshed Vitest baseline finished. All 13 were applied to the six test files below. No production/configuration edits or test runs were started by this lane.

The refreshed baseline at `bef1a0416` contained 3,033 passing frontend cases. The six component candidate files contained 220 cases.

13 case reductions are supported: 5 duplicate deletions and 8 consolidations that retain every removed assertion in an existing scenario before its first relevant state transition. The consolidations remove repeated page mounting, not contracts. No production or shared test-support deletion is unlocked. This is not evidence for a 20% frontend or combined-suite reduction.

All candidates run in normal Vitest discovery through `apps/web/package.json`; Updated CI runs four coverage shards and merges coverage in `.github/workflows/ci.yml`. No candidate is an excluded or failing test. Each focused command below runs from `apps/web` with `mise exec -- pnpm test <file>`. Full frontend coverage, type checks, and lint passed after the edits. Do not edit while Vitest runs in this checkout.

## Matches

Owners read: `app/(app)/intended-parents/matches/[id]/page.client.tsx`, including dialog wiring and `handleAddTask`; complete `components/matches/AddTaskDialog.tsx`; list URL parsing, filters, and header in `app/(app)/intended-parents/matches/page.client.tsx`; route entry `page.tsx`. Both test files were read in full, including mocks and sibling scenarios. Non-test callers are the match detail/list routes. `AddTaskDialog` submits its reducer's `target` (initially `match`) through the detail page, whose handler adds `match_id` and `work_source` to `useCreateTask`.

### M1 — D

- Location/name: `tests/match-detail.test.tsx:473`, `creates case tasks on the whole match`.
- Actual failure detected: opening Tasks → Add Task and submitting a title fails to call task mutation with `task_type: other`, `match_id: match1`, and `work_source: match`.
- Stronger keeper: `creates a match-scoped task from the overview tasks tab` at line 396 executes the same controls under the same default mocks and asserts the same full payload. The titles differ only as arbitrary strings; no title-specific production branch exists.
- History/reason: older keeper came from `4d9af330e` (`feat: add match-scoped task controls on match detail`); repeated scenario came from `221b45d03` (`feat: add donor cases and attempts to matching workspace`) and was narrowed to the current whole-match flow in `30f2d265c6`. Neither currently exercises a donor, attempt, alternate target, or calendar entry point.
- Unlocked deletion: only the repeated case; no production/support seam.
- Risk/validation: low; retain the keeper's exact payload assertion. `mise exec -- pnpm test tests/match-detail.test.tsx`.

### M2 — C

- Location/name: `tests/match-detail.test.tsx:388`, `defaults the add task dialog to match target`.
- Actual failure detected: the visible Match (both sides) radio is not initially selected.
- Keeper/carry: in `creates a match-scoped task from the overview tasks tab`, immediately after opening Add Task and before editing the title, carry `expect(screen.getByRole('radio', { name: /match \(both sides\)/i })).toBeChecked()`. Payload assertions alone do not prove the visible default; keep this assertion.
- History/reason: `4d9af330e` introduced the whole-match default; `a80c003ab3` adapted the accessible radio lookup. Both cases share the same complete setup and initial dialog state.
- Non-test callers/unlocked deletion: shared match route/dialog chain above; only repeated mount/open setup removed.
- Risk/validation: low after carrying the visible default; same focused command as M1.

### M3 — D

- Location/name: `tests/matches-page.test.tsx:321`, `uses page from URL params`.
- Actual failure detected: `?page=2` is not parsed and passed into `useMatches`.
- Stronger keeper: `derives committed filters from URL params` at line 336 asserts page 3 alongside status and query, and asserts the visible search value. `readMatchListUrlState` always parses page with `parsePageParam`, independently of status, query, and API response; these inputs traverse the same page path.
- History/reason: initial pagination test `f69a2f7e6a`; URL-derived-filter regression `4608b1793` (`fix: Derive intended parent filters from URL`) became the broader owner. Retain debounce/reset, unknown status, and filtered-empty scenarios because they guard different paths.
- Non-test callers/unlocked deletion: match list route; one repeated case, no support/source seam.
- Risk/validation: low. `mise exec -- pnpm test tests/matches-page.test.tsx`.

### M4 — D

- Location/name: `tests/matches-page.test.tsx:162`, `shows no header count when a filter is active`.
- Actual failure detected: a `page-header-count` slot is rendered with accepted-status filtering.
- Stronger keeper: `renders the default match list, summary, and filters` at line 124 already asserts that this slot is absent. Production passes a fixed `title="Matches"` and actions to `PageHeader`, with no count prop and no filter-dependent header branch. Query/filter behavior has separate retained cases.
- History/reason: the earlier count behavior was adjusted by `30f2d265c6`; the two tests now repeat the same unconditional no-count rendering invariant.
- Non-test callers/unlocked deletion: match list route; repeated case only.
- Risk/validation: low; if a future filtered count is deliberately introduced its behavior needs a new explicit owner. Same focused command as M3.

## Form builder

Owners read: route `app/(app)/automation/forms/[id]/page.client.tsx`; complete `AutomationFormBuilderScreen`, `FormBuilderHeader`, and `form-publication-status.ts`; hydration/publication/publish handlers in `use-automation-form-builder-page.ts`; `useFormBuilderDocument` insertion/selection; field inspector label/value binding; purpose/template controls in `AutomationFormSettingsPanel`. Normal callers are the automation form builder route; the document and workspace are also used by platform template builders. Installed TanStack `hashKey` source sorts object keys, confirming that the reordered-schema fixture is an independent content-equality guard, not a string-order assertion.

### F1 — C

- Location/name: `tests/form-builder-page.test.tsx:1387`, `keeps Publish disabled for a published form with nothing new to publish`.
- Actual failure detected: an unchanged, already-published form—including identical content with reordered object keys—shows the wrong badge or enables Publish.
- Keeper/carry: prepend both initial assertions (`Published` present, Publish disabled) immediately after `renderForm(buildPublishedForm())` in `enables Publish for an unsaved edit to a published form` at line 1402. That keeper already starts with the identical reordered-schema fixture before changing Title.
- History/reason: all publish-state cases were introduced together by `5d6c255fc` (`fix: let saved form edits be republished (#758)`). The initial and changed states belong in one transition scenario; the content-equality behavior remains explicitly asserted.
- Non-test callers/unlocked deletion: builder route/controller/header above; one repeated whole-builder render, no production/support seam.
- Risk/validation: low only if assertions run before the Title edit. `mise exec -- pnpm test tests/form-builder-page.test.tsx tests/form-builder-header.test.tsx`.

### F2 — C

- Location/name: `tests/form-builder-page.test.tsx:1394`, `enables Publish when the saved draft differs from the live form`.
- Actual failure detected: saved schema differences fail to display Unpublished changes, keep displaying Published, or disable Publish.
- Keeper/carry: `returns to Published after publishing saved changes` at line 1430 constructs exactly the same changed public-title fixture. Before `fireEvent.click(publishButton())`, carry all three assertions: Unpublished changes present, Published absent, and Publish enabled. Keep its publish callback, dialog closure, mutation id, final Published badge, and disabled Publish assertions.
- History/reason: `5d6c255fc`; initial saved-draft state is already the first state of the republish lifecycle keeper.
- Non-test callers/unlocked deletion: same as F1; one repeated whole-builder render.
- Risk/validation: low after carrying all initial assertions; same focused command as F1.

### F3 — C

- Location/name: `tests/form-builder-page.test.tsx:593`, `renders human-readable labels for automation settings dropdown triggers`.
- Actual failure detected: Form Purpose or default application email template leaks `surrogate_application`/`none` instead of the displayed labels.
- Keeper/carry: `uses design-system tab controls for workspace sections and a dedicated settings tab` at line 371 already renders the same new-form fixture and opens Settings. Append both trigger positive-label and raw-key-negative assertions after it opens Settings.
- History/reason: `623718e70` (`fix: humanize automation form settings dropdowns`) introduced the regression. Its assertions are retained, including both sibling selects, as required by repository policy.
- Non-test callers/unlocked deletion: automation route renders `AutomationFormSettingsPanel`; one repeated mount and Settings navigation, no source/support seam.
- Risk/validation: low; do not discard label negatives. Same focused command as F1.

### F4 — C

- Location/name: `tests/form-builder-page.test.tsx:1231`, `shows the newly selected field in the settings drawer`.
- Actual failure detected: selecting Name then Email leaves the inspector title or contextual Delete action attached to the prior field.
- Keeper/carry: `renders human-readable labels for inspector dropdown triggers` at line 1119 already clicks Add Name then Add Email under the same fixture. Carry the Name title assertion immediately after adding Name; carry the Email title and `Delete Email field` assertions immediately after adding Email, **before** the keeper's explicit `Select Email field` click. That ordering preserves the insertion-selects-new-field regression.
- History/reason: selection regression from `9f4155eb4` (`fix: Clean form builder settings tab sync`), updated for the drawer by `166344f092` (`feat(web): lay out the form builder as rail, document canvas, and settings drawer`).
- Non-test callers/unlocked deletion: `useFormBuilderDocument.handleInsertField` builds/inserts the field then calls `selectField(newField.id)`; builder workspace/inspector consumes that selection. One repeated two-field builder setup removed; no production/support seam.
- Risk/validation: low with the exact assertion order above; otherwise explicit selection can conceal the regression. Same focused command as F1.

## Workflow editor

Owners read: route client, toolbar in `workflow-editor-screen.tsx`, complete `workflow-build-panel.tsx`, and relevant `workflow-canvas.tsx` selection/trigger rendering. Normal caller is the full-page workflow creation/edit route; toolbar and canvas consume the shared workflow controller. Candidate and keeper cases plus their complete imports/mocks/helpers/default fixture were read.

### W1 — C

- Location/name: `tests/workflow-editor-page.test.tsx:278`, `renders the trigger and exit nodes with the trigger panel and build palette`.
- Actual failure detected: a new editor has wrong trigger selection, trigger summary, exit node, trigger-kind choices, Add filter control, Add Note palette entry, or Draft status.
- Keeper/carry: prepend all seven initial assertions to `adds a typed action from the build palette and selects it` at line 299, immediately after its identical `renderNewWorkflow()` and before clicking Add Note. Keep the post-click action type/selected action/unselected trigger assertions. This becomes one explicit initial→selected-action transition.
- History/reason: full-page editor `89a372a92` and trigger/exit refinement `22f929551e`. Every initial UI contract remains asserted; only duplicate page render disappears.
- Non-test callers/unlocked deletion: workflow route/controller→screen/build panel/canvas; no source/support seam, one duplicate render removed.
- Risk/validation: low after carrying all assertions. `mise exec -- pnpm test tests/workflow-editor-page.test.tsx tests/workflow-editor-history.test.ts`.

### W2 — C

- Location/name: `tests/workflow-editor-page.test.tsx:290`, `gives the header actions their own full-width row on phones`.
- Actual failure detected: mobile toolbar actions cease wrapping into their own full-width row or the two save actions cease sharing width.
- Keeper/carry: prepend the complete actions-parent containment and four class assertions to `saves a draft with the workflow disabled` at line 373, after its identical new-editor render and before edits. Keep the draft mutation assertion. Responsive classes remain independently asserted on the real toolbar; this is not deletion merely for being a style test.
- History/reason: `5279a21b0` (`fix(web): show the trigger's record type on new workflows and fit the editor header on phones`).
- Non-test callers/unlocked deletion: same workflow route/toolbar; one render only, no source/support seam.
- Risk/validation: low; existing jsdom proof still checks responsive class contract, not real viewport layout. Same focused command as W1.

## Rich text

Complete candidate/keeper suite, `rich-text-editor.tsx`, and `rich-text-editor-emoji-popover.tsx` were read. Production `EntityNotes` uses `RichTextEditor` with emoji enabled. The toolbar forwards emoji selection into the real component's `editor.chain().focus().insertContent(emoji).run()`. The TipTap instance and emoji picker are existing mocks, so these are adapter contracts, not full rich-text-engine proof. Installed emoji picker types declare `FREQUENT = "frequent"`, `RECENT = "recent"`, and the `suggestedEmojisMode` prop.

### R1 — D

- Location/name: `tests/rich-text-editor.test.tsx:92`, `shows an emoji insert control when enabled`.
- Actual failure detected: the enabled editor lacks Bold or Insert Emoji controls.
- Stronger keepers: `inserts selected emoji into the editor` at line 114 explicitly waits for Insert Emoji, opens it, and asserts the inserted emoji. `labels undo and redo and hides the default emoji control` at line 102 retains the Bold lookup; enabled mode uses the same toolbar Bold control with an additional emoji branch. If preserving the enabled-mode Bold check exactly is preferred, carry it into the insertion case at no additional render cost.
- History/reason: `3501d945a` introduced the picker and all these tests together.
- Non-test callers/unlocked deletion: EntityNotes→RichTextEditor→toolbar/popover; duplicate mount only, no seam.
- Risk/validation: low; keep enabled insertion and disabled-default tests. `mise exec -- pnpm test tests/rich-text-editor.test.tsx tests/entity-notes.test.tsx`.

### R2 — C

- Location/name: `tests/rich-text-editor.test.tsx:127`, `renders the full emoji picker with frequent suggestions by default`.
- Actual failure detected: opened picker is absent or receives non-frequent/non-native defaults.
- Keeper/carry: in `can switch suggested mode to recent` at line 145, immediately after opening Insert Emoji and **before** clicking Recent, carry the picker presence assertion and the complete frequent/native mock-prop assertion. Then keep the existing Recent assertion. Both cases use identical props and setup.
- History/reason: same picker feature commit `3501d945a`; initial default and user-switched mode form one lifecycle.
- Non-test callers/unlocked deletion: same as R1; one repeated mount/open only, no seam.
- Risk/validation: low; carry the default assertion before the switch. Same focused command as R1.

## Email template menu

### E1 — D

- Location/name: `tests/email-templates-page.test.tsx:613`, `labels organization template action menus with template context`.
- Actual failure detected: the organization template lacks a button whose accessible name is Actions for Org Template.
- Stronger keeper: `routes organization template editing to the Studio` at line 763 renders the identical fixtures, selects Organization, locates that exact accessible name, clicks it, chooses Edit, and checks canonical Studio routing. `shows send test email action and opens dialog` at line 379 also uses that exact button name.
- Owner/non-test callers: `components/email/TemplateCard.tsx` (read in full), `TemplateCardMenuTrigger`, and org-template rendering/action dispatch in the email templates route. `TemplateDraftCard` also consumes the menu trigger, but draft-specific tests stay.
- History/reason: accessible contextual label from `f55c8b7b2` (`fix: improve icon-only control accessibility`); newer Studio-routing test exercises that same required accessible name on the real menu.
- Unlocked deletion: repeated page mount only; no source/support seam.
- Risk/validation: low. `mise exec -- pnpm test tests/email-templates-page.test.tsx`.

## Retained false positives

- The 13 form-builder autosave-page cases exercise in-flight edits, create completion after close/hide, same-tick Save races, publish serialization, failed-save retry rules, route changes, and stale results. Similar final mutation counts are not duplicate lifecycle proof. No case was proposed for deletion.
- Mutation-invalidation cases often mock `useMutation` and manually invoke `onSuccess`, but most have no stronger retained real-cache/page owner. Similar invalidation keys across different mutations do not establish equivalence. Several aggregate cases do not reset spies between hooks; these warrant future assertion repair, not deletion to meet a count.
- The matched source/AST pattern in `use-mobile.test.tsx` is a false positive: initial `matchMedia=true` with `innerWidth=1024` detects reliance on innerWidth; the change-event test starts false and cannot catch an initially hard-coded false snapshot.
- Tabs fragment/array enumeration, wrapper rendering, and conditional second-tab removal exercise separate child-inspection/control paths despite repeated tab-count assertions.
- Matching consent, permission, statuses, stage-key-renaming, malformed-input, and foreign entity cases remain. Equal line coverage or identical final UI messages do not replace their different triggers.
- `AutomationPageHeader` runtime tests in `page-header-adoption.test.tsx` and `automation-page-header.test.tsx` differ: allowed history plus templates-tab omission versus denied history and create callback. Both retained.
- Both `form-builder-header.test.tsx` cases remain: pending-save readiness explanation and published-form reason suppression are distinct precedence rules. A published-row-only rename stays distinct from schema publication changes.
- The two workflow server-error cases differ by `ApiError(422)` versus a plain `Error`, and by edit-driven clearing. No deletion recommended without explicitly preserving both error paths.
- Email org versus personal send actions, published-template draft versus new draft discard, title link versus menu Edit, and empty-state versus populated header creation are distinct entry points. No removal solely for identical resulting URLs/payloads.

## Validation state

Discovery used repository reads, source/type inspection, baseline JSON inspection, an in-memory TypeScript AST subset sweep, `git blame`, and `git show`. Every proposed case and named keeper was inspected, along with its owner and relevant history. All explicit carry steps were applied. The enabled-mode Bold assertion was also carried into emoji insertion; the combined workflow initial/action and emoji frequent/recent keepers were renamed to describe their transitions.

Applied case reductions: match detail 2, match list 2, form builder 4, workflow editor 2, rich text 2, email templates 1. Test LOC: 25 added, 122 removed, net -97. Production/tooling/shared-support LOC: 0. `git diff --check` passed after edits. The cross-cutting lane was asked to perform an independent preservation review. No test run, coverage replay, commit, push, PR, or merge was performed by this lane; the parent owns full validation and final coverage comparison.

## Executed validation

The frozen baseline at `bef1a0416` contained 3,033 passing frontend cases. All 3,017 retained cases passed after the combined 16-case reduction on the original Vitest 5.0.1/jsdom 29.1.1 toolchain. Statements, lines, branches, and functions were unchanged, including every per-file coverage count. Independent preservation review found no gaps. Later tooling and shard validation is reported separately.
