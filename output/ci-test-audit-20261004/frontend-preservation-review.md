# Frontend preservation review

Independent review of the six component-test files changed by the frontend audit lane against baseline `bef1a04161f9d5f78fffe9cc15a0db8143a9995f`. The review excludes the three documentation tests removed by this reviewer and excludes parent-owned CI changes.

No preservation findings. The patch removes 13 collected declarations across six files while retaining the distinct assertions identified in the ledger. Two keeper names change to describe their combined state transitions. No production or test-support files change in this batch.

## Review evidence

Read the frontend ledger, complete six-file Git diff, every removed callback and keeper, relevant fixtures/helpers, and production owner paths. An installed-TypeScript AST comparison of baseline/current declaration names independently confirms reductions of 2 match-detail, 2 match-list, 4 form-builder, 2 workflow-editor, 2 rich-text, and 1 email-template case. The comparison is static inspection, not a test run.

| Ledger item | Preservation decision |
| --- | --- |
| M1 — duplicate whole-match task creation | Pass. The keeper executes the same Tasks/Add Task flow and asserts the complete `task_type`, `match_id`, and `work_source` payload. Titles differ only in ordinary nonempty text. `AddTaskDialog` trims/validates the title without branching on either value; match-detail `handleAddTask` adds the same match and target fields. |
| M2 — visible default task target | Pass. The checked Match radio assertion now runs immediately after opening the real dialog, before the title edit and submit. Correct payload alone would not establish this UI state; the explicit assertion is retained. |
| M3 — page URL parsing | Pass. The retained committed-filters scenario checks parsed page 3 with status/query. `readMatchListUrlState` obtains page independently through `parsePageParam`, and `filters.page` is passed unconditionally to `useMatches`. The removed page-2 response fixture does not alter the parsing path or guard a separate branch. |
| M4 — filtered no-count header | Pass. The default rendering keeper asserts absence of `page-header-count`. The current page renders one unconditional `PageHeader` with fixed title/actions and no count prop. Filter state affects toolbar/results, not header count. No separate current production branch is lost. |
| F1 — published and unchanged | Pass. Both Published and disabled Publish assertions precede the title change in the keeper. The same reordered-object schema fixture remains, preserving `hasSameContent` behavior in the real controller and publication label/disabled state in `FormBuilderHeader`. |
| F2 — saved unpublished changes | Pass. All three initial assertions remain before the publish click: Unpublished changes present, Published absent, Publish enabled. The existing callback/refetch/final Published and disabled assertions remain. Initial-state checking does not depend on the later mocked publish result. |
| F3 — settings dropdown labels | Pass. Both positive visible labels and both raw-value negative assertions are carried after the same initial Settings navigation. The keeper does not mutate form purpose or template selection before these checks. The real `AutomationFormSettingsPanel` label mapping remains the exercised owner. |
| F4 — insertion selects the new field | Pass. Name title is checked after Name insertion; Email title and Delete Email field are checked after Email insertion and before the explicit Select Email field action. That order preserves the regression in `useFormBuilderDocument.handleInsertField` and the inspector's selected-field binding. The later explicit selection cannot mask a broken insertion selection. |
| W1 — initial workflow state and action selection | Pass. All seven initial checks remain before Add Note. The existing action-type, selected-action, and unselected-trigger checks follow it. Both original scenarios used identical `renderNewWorkflow` setup. Toolbar/canvas/build-palette production paths remain exercised. |
| W2 — responsive save toolbar | Pass. Full-width/container membership and both save-button width assertions run before workflow edits. The actual toolbar classes are still asserted; the draft save mutation assertion remains. Consolidation does not upgrade this jsdom class check into viewport-layout proof. |
| R1 — enabled emoji control | Pass. The insertion keeper retains Insert Emoji and now also explicitly checks Bold in enabled mode before opening the picker. The separate disabled-default test remains. |
| R2 — frequent/native initial picker and Recent switch | Pass. Picker presence and the complete frequent/native prop assertion occur before clicking Recent. `mockEmojiPickerProps.mockClear()` still runs before each test, so another case cannot supply the initial-mode evidence. The Recent check remains after the switch, matching the production popover's initial frequent state and Recent callback. |
| E1 — contextual org-template action label | Pass. The existing Studio-edit keeper selects Organization and resolves the exact accessible button name `Actions for Org Template` before clicking Edit. `TemplateCardMenuTrigger` derives that name from the template; a missing/wrong accessible label fails the keeper before routing assertions. |

## Remaining limits

- No new test-only production seam, self-derived expected value, or weaker mock was introduced by this patch.
- Existing rich-text tests establish the component's adapter calls through a mocked editor/picker; they do not prove the third-party editor engine. This limitation is unchanged.
- Existing responsive assertions check classes in jsdom. Actual viewport rendering remains outside this batch's existing proof.
- No tests, mutation experiments, coverage runs, source edits, or commits were performed by this reviewer. The parent must finish full candidate validation and baseline/candidate coverage comparison before claiming the coverage budget or performance target.
- No lost contract required restoration, so no gap-restoration mutation was required by this review.
