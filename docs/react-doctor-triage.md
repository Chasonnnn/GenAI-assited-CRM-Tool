# React Doctor Triage

Baseline command: `cd apps/web && npx react-doctor@latest . --verbose`

## 2026-06-30 Baseline

- Score: `0 / 100 Critical`
- Total diagnostics: `1474`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 319 warnings`, `Performance 174 errors + 44 warnings`, `Accessibility 54 warnings`, `Maintainability 847 warnings`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1b7d4f9a-8098-4ea2-9ac0-f0535feb5aaa`

## Batch 1

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/button-has-type` | `app/(app)/ai-assistant/page.tsx`, `app/(app)/automation/ai-builder/page.client.tsx`, `app/(app)/settings/audit/page.tsx`, `components/app-sidebar.tsx`, `components/surrogates/LatestUpdatesCard.tsx` | Valid: all flagged buttons are non-submit controls and should not inherit submit behavior. | High | Add `type="button"` to each raw button. | Changed-scope React Doctor no longer reports `button-has-type`; `pnpm tsc --noEmit`; `pnpm test --run tests/form-builder-page.test.tsx tests/platform-form-template-page.test.tsx tests/surrogate-interview-accessibility.test.tsx tests/ai-assistant.test.tsx tests/ai-builder-page.test.tsx tests/audit-log-page.test.tsx tests/app-sidebar-permissions.test.tsx` passed. |
| `react-hooks-js/refs` | `lib/forms/use-automation-form-builder-page.ts`, `lib/forms/use-template-form-builder-page.ts` | Valid: both hooks read `lastSavedFingerprintRef.current` during render while deriving `isDirty`, so React Compiler has to skip optimization. | High | Store the saved fingerprint in existing builder reducer state for render-time reads; keep refs out of render. | Changed-scope React Doctor no longer reports `react-hooks-js/refs`; `pnpm tsc --noEmit`; focused tests passed. |
| `react-hooks-js/preserve-manual-memoization` / `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/LatestUpdatesCard.tsx` | Valid: manual `useMemo` for sanitized note HTML has an inferred dependency mismatch and blocks compiler preservation. | High | Remove manual memoization and let React Compiler cache the pure sanitized value. | Changed-scope React Doctor no longer reports `preserve-manual-memoization` for `LatestUpdatesCard`; `pnpm tsc --noEmit`; focused tests passed. |
| `react-hooks-js/todo` | `components/surrogates/LatestUpdatesCard.tsx` | Valid: `try` with a `finally` clause is a known unsupported compiler syntax in the current React Doctor/Compiler diagnostic. | High | Rewrite the async download handler with `try`/`catch` and explicit loading-state reset on both paths. | Changed-scope React Doctor no longer reports `components/surrogates/LatestUpdatesCard.tsx`; `pnpm tsc --noEmit`; focused tests passed. |

Changed-scope command after Batch 1: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `72 / 100 Needs work`
- Total diagnostics in changed files: `55`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1a4c7521-de5c-4385-839d-e3ec8ebf2e6b`

Full command after Batch 1: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `0 / 100 Critical`
- Total diagnostics: `1463`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 313 warnings`, `Performance 170 errors + 44 warnings`, `Accessibility 54 warnings`, `Maintainability 846 warnings`
- Removed globally: `react-doctor/button-has-type`, `react-hooks-js/refs`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1116efac-b44a-41b8-ac74-486b0e73165d`

## Batch 2

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/(app)/ai-assistant/page.tsx`, `app/(app)/automation/ai-builder/page.client.tsx`, `lib/forms/use-automation-form-builder-page.ts`, `lib/forms/use-template-form-builder-page.ts` | Valid: each diagnostic was a `try` statement with a `finally` clause in an event or async handler. The loading/status cleanup was explicit and could be preserved in success and catch paths without behavior changes. | High | Replace the flagged `try`/`finally` handlers with `try`/`catch` and explicit cleanup helpers. | Changed-scope React Doctor no longer reports `react-hooks-js/todo` in changed files; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run tests/ai-assistant.test.tsx tests/ai-builder-page.test.tsx`; earlier full `pnpm test --run` passed. |
| `react-hooks/set-state-in-effect` / `react-doctor/prefer-useReducer` | `app/(app)/ai-assistant/page.tsx`, `app/(app)/automation/ai-builder/page.client.tsx` | Valid: AI Assistant was applying several related chat state updates from mount/session effects; AI Builder used an effect to correct tab state after permissions changed. | High | Group AI Assistant chat state into a reducer-backed state object so session resets update together; derive AI Builder workflow scope from permission state instead of correcting it in an effect. | `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run tests/ai-assistant.test.tsx tests/ai-builder-page.test.tsx` passed. Changed-scope React Doctor no longer reports `react-hooks/set-state-in-effect` in changed files. |
| `react-doctor/exhaustive-deps` | `app/(app)/ai-assistant/page.tsx:396` | Invalid/intentional: the unmount cleanup reads `streamAbortRef.current` because it must abort the latest in-flight stream when the page unmounts. Capturing the initial ref value would capture `null` and fail to abort an active request. | High | Log as non-fix for this batch. Do not suppress yet; revisit only if the stream lifecycle is refactored. | Verified by reading the cleanup and stream assignment path around `handleSend`; changed-scope React Doctor still reports this warning. |

Changed-scope command after Batch 2: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `89 / 100 Great`
- Total diagnostics in changed files: `42`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-16163e5c-386a-4f0e-9456-ba88c0a89ef0`

Full command after Batch 2: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `0 / 100 Critical`
- Total diagnostics: `1445`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 304 warnings`, `Performance 158 errors + 44 warnings`, `Accessibility 54 warnings`, `Maintainability 849 warnings`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-48f82c62-7081-4025-89cd-78e1c453539d`

## Batch 3

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/(app)/settings/admin/page.tsx` | Valid: the admin data handlers used `try` with `finally`, then after the first rewrite React Doctor exposed the related compiler limitation for `throw` statements inside `try`/`catch`. | High | Add characterization coverage for developer access and export cleanup, then move export/import validation and response parsing into module-scope helpers so the component handler has no compiler-blocking syntax. | `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run tests/admin-data-page.test.tsx`; changed-scope React Doctor reports no issues. |
| `react-doctor/async-await-in-loop` | `app/(app)/settings/admin/page.tsx` | Valid concern in shape, but this polling is intentionally sequential because each status request depends on elapsed time and previous job status. | High | Preserve sequential polling with a bounded recursive helper instead of an `await` inside a loop. | Changed-scope React Doctor reports no issues. |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/settings/admin/page.tsx` | Valid: React Compiler is enabled in `next.config.js`, so local `useCallback` wrappers around event handlers are redundant. | High | Remove redundant `useCallback` wrappers while preserving handler behavior. | Changed-scope React Doctor reports no issues. |

Changed-scope command after Batch 3: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 3: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `0 / 100 Critical`
- Total diagnostics: `1431`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 304 warnings`, `Performance 147 errors + 43 warnings`, `Accessibility 54 warnings`, `Maintainability 847 warnings`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-05a399bf-33da-496c-8f45-dddde566dda0`

## Batch 4

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/ops/agencies/[orgId]/page.client.tsx` | Valid: ops agency load/action handlers used `try` statements with `finally` clauses, which blocks React Compiler optimization. | High | Replace each `finally` cleanup with explicit success/catch cleanup helpers while preserving stale-request guards. | `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run tests/react-regressions-source.test.ts tests/ops-support-session-dialog.test.tsx tests/agency-users-tab.test.tsx tests/agency-time-rendering.test.tsx`; changed-scope React Doctor no longer reports errors. |
| `react-hooks-js/set-state-in-effect` | `app/ops/agencies/[orgId]/page.client.tsx` | Valid: initial alert refresh synchronously called a callback that set loading state from an effect. | High | Defer the initial alert load into a microtask and keep manual refresh as an event-driven handler. | Changed-scope React Doctor no longer reports `set-state-in-effect`. |
| `react-doctor/react-compiler-no-manual-memoization` | `app/ops/agencies/[orgId]/page.client.tsx` | Valid: React Compiler is enabled, so the alert-count `useMemo` was redundant. | High | Derive `openAlertCount` directly and update the source regression guard to keep duplicate state out instead of requiring `useMemo`. | Focused source regression tests passed. |

Changed-scope command after Batch 4: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Remaining changed-file warnings: `no-giant-component`, `prefer-useReducer` for `AgencyDetailPage`; both are valid but larger refactors deferred to a separate batch.
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-b5b974f7-e6ca-40ba-a249-5ef2d313f7c6`

Full command after Batch 4: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `0 / 100 Critical`
- Total diagnostics: `1412`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 303 warnings`, `Performance 134 errors + 40 warnings`, `Accessibility 54 warnings`, `Maintainability 845 warnings`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4ede4ff8-d0be-4f21-95f6-29d325ec8a9d`

## Batch 5

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/(app)/automation/forms/page.tsx` | Valid: form-template apply, share-link preparation, copy, and QR download handlers used `try` statements with `finally` cleanup. | High | Replace `finally` cleanup with explicit success/catch cleanup helpers, including early-return cleanup in QR rendering paths. | `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor no longer reports errors. |
| `react-doctor/prefer-module-scope-pure-function` | `app/(app)/automation/forms/page.tsx` | Valid: status label/variant, share-link selection, QR SVG lookup, and blob download helpers do not use component state. | High | Move pure helpers to module scope. | Changed-scope React Doctor no longer reports these helper warnings. |

Changed-scope command after Batch 5: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Remaining changed-file warnings: `no-giant-component`, `prefer-useReducer` for `FormsListPage`; both are larger refactors deferred to a separate batch.
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-b745aab7-dc7f-4cb3-9a91-5824fc3c0b26`

Full command after Batch 5: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `1 / 100 Critical`
- Total diagnostics: `1403`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 303 warnings`, `Performance 130 errors + 40 warnings`, `Accessibility 54 warnings`, `Maintainability 840 warnings`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-baa4c0f5-8649-4d9a-b82d-daaab21d0a9f`

## Batch 6

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/(app)/automation/campaigns/page.tsx` | Valid: campaign delete, cancel, and send-now dialog handlers used `try` statements with `finally` cleanup. | High | Replace `finally` cleanup with explicit success/error cleanup helpers. | `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run tests/react-regressions-source.test.ts tests/campaign-detail-page.test.tsx`; changed-scope React Doctor no longer reports errors. |
| `react-doctor/prefer-module-scope-pure-function` | `app/(app)/automation/campaigns/page.tsx` | Valid: `isRecipientType` and `isScheduleFor` do not use component state. | High | Move both type guards to module scope. | Changed-scope React Doctor no longer reports these helper warnings. |

Changed-scope command after Batch 6: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Remaining changed-file warnings: `no-giant-component`, `prefer-useReducer` for `CampaignsPage`; both are larger refactors deferred to a separate batch.
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4d167d41-1be9-4d5d-8e02-cb2843b13a22`

Full command after Batch 6: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `2 / 100 Critical`
- Total diagnostics: `1398`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 303 warnings`, `Performance 127 errors + 40 warnings`, `Accessibility 54 warnings`, `Maintainability 838 warnings`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-5e8ccba6-72e2-47a5-a1e6-e2640702d3af`

## Batch 7

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/ops/templates/email/[id]/page.client.tsx` | Valid: the email-template save, publish, and send-test handlers used `try` statements with `finally` cleanup, which blocks React Compiler optimization. | High | Replace `finally` cleanup with explicit success/error cleanup helpers. | `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run tests/platform-email-template-page.test.tsx tests/react-regressions-source.test.ts`; changed-scope React Doctor no longer reports errors. |

Changed-scope command after Batch 7: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `91 / 100 Great`
- Total diagnostics in changed files: `28`
- Remaining changed-file warnings: `react-doctor/react-compiler-no-manual-memoization` for `app/ops/templates/email/[id]/page.client.tsx`; valid but broad same-file cleanup deferred to a separate batch.
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-6dbf1f16-4831-4da6-8359-0193bda14d20`

Full command after Batch 7: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `4 / 100 Critical`
- Total diagnostics: `1395`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 303 warnings`, `Performance 124 errors + 40 warnings`, `Accessibility 54 warnings`, `Maintainability 838 warnings`
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-07780cca-db38-431b-8b21-5ed2f3e45689`

## Dependency Refresh

- Action: Moved the frontend package manager to `pnpm@11.9.0`, migrated pnpm policy settings from `package.json` to `pnpm-workspace.yaml`, refreshed direct dependencies to current registry versions, and removed the unused `tailwindcss-animate` dependency.
- Follow-up fixes: Updated code for current `lucide-react` and `react-day-picker` APIs, TypeScript 6 indexed access checks, ESLint 10 `no-useless-assignment`, and Base UI test DOM changes.
- Dependency verification: `corepack pnpm outdated --long` reported no outdated direct dependencies; `corepack pnpm peers check` reported no peer issues.
- Code verification: `corepack pnpm tsc --noEmit`; `corepack pnpm lint`; `corepack pnpm test --run`.
- Full React Doctor after refresh: `4 / 100 Critical`, `1394` diagnostics, `158` errors.
- Diagnostics: `/private/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-19dfef0f-3f86-4a74-8fc3-73bf5dd26876`

## Batch 8

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` | `app/ops/templates/system/new/page.client.tsx` | Valid: the new system-template page derived the system key and forced HTML editor mode through effects that immediately set state. | High | Derive the system key and effective editor mode during render instead of correcting them through effects. Added characterization coverage for auto-derived keys and complex-HTML editor mode. | `pnpm tsc --noEmit`; `pnpm test --run tests/platform-system-email-template-new-page.test.tsx`; changed-scope React Doctor no longer reports this error. |
| `react-hooks-js/todo` | `app/ops/templates/system/new/page.client.tsx` | Valid: the create handler used `try` with `finally` cleanup, which blocks React Compiler optimization. | High | Replace `finally` cleanup with explicit success/error cleanup helpers. Added coverage that failed creates re-enable the Create button. | Focused test file passed; changed-scope React Doctor no longer reports this error. |
| `react-doctor/react-compiler-no-manual-memoization` | `app/ops/templates/system/new/page.client.tsx` | Valid: React Compiler is enabled, so local `useMemo` wrappers were redundant and one large preview calculation was better as a module-scope helper. | High | Move pure validation/preview/selection helpers to module scope and derive validation values directly in render. | Changed-scope React Doctor no longer reports manual memoization warnings for this file. |
| `react-doctor/rerender-state-only-in-handlers` | `app/ops/templates/system/new/page.client.tsx` | Valid: the active insertion target did not affect rendering and only guided event handlers. | High | Store the active insertion target in a ref instead of component state. | Changed-scope React Doctor no longer reports this warning. |
| `react-doctor/js-combine-iterations` | `app/ops/templates/system/new/page.client.tsx` | Valid: required variable names used chained `filter().map()` over the same list. | High | Replace with one `for...of` pass. | Changed-scope React Doctor no longer reports this warning. |

Changed-scope command after Batch 8: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Remaining changed-file warnings: `no-giant-component`, `prefer-useReducer` for `PlatformSystemEmailTemplateNewPage`; both are valid but larger structural refactors deferred to a separate batch.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-b72360c8-dc4b-44b1-8f36-dbb9709ad7d8`

Full command after Batch 8: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `5 / 100 Critical`
- Total diagnostics: `1371`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 298 warnings`, `Performance 121 errors + 39 warnings`, `Accessibility 54 warnings`, `Maintainability 823 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7f58c6f8-6c18-4459-ac7c-b8c51c29cc05`

## Batch 9

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` | `app/ops/templates/system/[systemKey]/page.client.tsx` | Valid: the edit page copied loaded template fields and branding logo URL into local state through effects, and auto-switched editor mode through another state-setting effect. | High | Derive template/branding values during render until a user edits a draft field; derive effective editor mode from body complexity instead of setting it in an effect. Added tests for loaded values, complex HTML mode, and quick-edit save behavior. | `pnpm tsc --noEmit`; `pnpm test --run tests/platform-system-email-template-page.test.tsx`; changed-scope React Doctor no longer reports this error. |
| `react-hooks-js/todo` | `app/ops/templates/system/[systemKey]/page.client.tsx` | Valid: member loading, save, branding save, logo upload, test send, and campaign send handlers used `finally` cleanup, which blocks React Compiler optimization. | High | Replace `finally` cleanup with explicit success/error cleanup helpers and keep version tracking in a handler-only ref. | Focused tests and full test suite passed; changed-scope React Doctor no longer reports compiler errors. |
| `react-doctor/react-compiler-no-manual-memoization` | `app/ops/templates/system/[systemKey]/page.client.tsx` | Valid: React Compiler is enabled, so local `useMemo` wrappers were redundant. | High | Move pure validation/preview/selection helpers to module scope and derive filtered orgs, selected org sets, variable checks, and preview HTML directly in render. | Changed-scope React Doctor no longer reports manual memoization warnings for this file. |
| `react-doctor/no-event-handler` / `react-doctor/no-chain-state-updates` | `app/ops/templates/system/[systemKey]/page.client.tsx` | Valid: opening the campaign dialog triggered organization loading indirectly through `campaignOpen` and an effect. | High | Load organizations directly from the dialog `onOpenChange` handler when opening. Added coverage for organization loading on dialog open. | Focused test file passed. |
| `react-doctor/control-has-associated-label` | `app/ops/templates/system/[systemKey]/page.client.tsx` | Valid: the hidden logo upload input had no accessible name. | High | Add an `aria-label` and assert the upload control is label-queryable. | Focused test file passed; changed-scope React Doctor no longer reports this warning. |

Changed-scope command after Batch 9: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `5`
- Remaining changed-file warnings: `no-giant-component`, `prefer-useReducer`, and `jsx-max-depth` for `PlatformSystemEmailTemplatePage`; all are valid but larger structural refactors deferred to a separate batch.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-28ba3d09-8055-4d5e-8dc7-537f55ef55b1`

Full command after Batch 9: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `10 / 100 Critical`
- Total diagnostics: `1336`
- Summary: `Security 2 warnings`, `Bugs 34 errors + 289 warnings`, `Performance 111 errors + 37 warnings`, `Accessibility 54 warnings`, `Maintainability 809 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-fb9ebcb4-619a-42e1-804e-3f891f4cefa8`

## Batch 10

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `components/surrogates/SurrogateApplicationTab.tsx` | Valid: form-link defaults, selected templates, selected intake links, upload field defaults, section-open defaults, and portal base URL were copied into local state through effects. | High | Derive defaults during render from current props/query data, while keeping explicit user choices in override state. Added a source regression guard for the old effect-driven defaults. | `pnpm tsc --noEmit`; `pnpm test --run tests/surrogate-application-tab.test.tsx tests/react-regressions-source.test.ts`; changed-scope React Doctor no longer reports errors. |
| `react-hooks-js/todo` | `components/surrogates/SurrogateApplicationTab.tsx` | Valid: approve, reject, send-link, export, upload, and delete handlers used `try` statements with `finally` cleanup, which blocks React Compiler optimization. | High | Replace `finally` cleanup with explicit success/error cleanup helpers and clear file inputs on every early-return/error/success path. | Focused tests and full test suite passed; changed-scope React Doctor no longer reports compiler errors for this file. |
| `react-doctor/control-has-associated-label` | `components/surrogates/SurrogateApplicationTab.tsx` | Valid: the hidden application upload input had no accessible name. | High | Add an `aria-label` and assert it in the source regression guard. | Changed-scope React Doctor no longer reports this accessibility warning. |

Changed-scope command after Batch 10: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `3`
- Remaining changed-file warnings: `prefer-module-scope-pure-function`, `no-giant-component`, and `prefer-useReducer` for `SurrogateApplicationTab`; all are valid but larger structural refactors deferred to separate batches.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-131f4490-9e5e-4086-9fcf-d9cd57352dcf`

Full command after Batch 10: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `19 / 100 Critical`
- Total diagnostics: `1296`
- Summary: `Security 2 warnings`, `Bugs 28 errors + 270 warnings`, `Performance 99 errors + 37 warnings`, `Accessibility 53 warnings`, `Maintainability 807 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-45216e1d-e7a5-4ec3-a531-f2484791ab4e`

## Batch 11

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `components/surrogates/detail/tabs/SurrogateOverviewTab.tsx` | Valid: inline select, height, race, and weight editors synchronized draft state from props through effects. | High | Initialize editor drafts when editing starts or cancels instead of mirroring props through effects. Added a source guard to prevent the effect pattern from returning. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/surrogate-detail.test.tsx tests/surrogates-accessibility.test.tsx`; changed-scope React Doctor no longer reports errors. |
| `react-hooks-js/todo` | `components/surrogates/detail/tabs/SurrogateOverviewTab.tsx` | Valid: inline save handlers, checklist toggles, SSN saves, and personal-section deletion used unsupported `try`/`finally` or bare `try` shapes. | High | Replace finalizers with explicit success/error cleanup helpers and add error handling where the previous code relied on rejected async handlers. | Focused tests and full test suite passed; changed-scope React Doctor no longer reports compiler errors. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/detail/tabs/SurrogateOverviewTab.tsx` | Valid: React Compiler is enabled, so local `useMemo` wrappers around derived stage, BMI, and warning values are redundant. | High | Remove manual memoization and derive the values directly during render. | Changed-scope React Doctor no longer reports manual memoization warnings for this file. |
| `react-doctor/prefer-tag-over-role` | `components/surrogates/detail/tabs/SurrogateOverviewTab.tsx` | Valid: inline editor display controls used `div role="button"` even though a native button fits the interaction. | High | Replace the faux buttons with `<button type="button">` controls. | Focused interaction/accessibility tests passed; changed-scope React Doctor no longer reports this warning. |

Changed-scope command after Batch 11: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `3`
- Remaining changed-file warnings: `no-giant-component` and `prefer-useReducer` for `SurrogateOverviewTab`; both are valid but larger structural refactors deferred to separate batches.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-3ad3072b-d442-4e93-b79e-8fcd797a6bc1`

Full command after Batch 11: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `26 / 100 Critical`
- Total diagnostics: `1264`
- Summary: `Security 2 warnings`, `Bugs 27 errors + 260 warnings`, `Performance 88 errors + 37 warnings`, `Accessibility 49 warnings`, `Maintainability 801 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-31a2e4f1-19a1-44bb-8289-2dd2594b4cb4`

## Batch 12

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `app/intake/[slug]/page.client.tsx` | Valid: draft-session identity, resume prompt clearing, and current-step bounds were adjusted through effects, causing extra renders and stale intermediate UI. | High | Collapse draft session id/existence into one initialized state object, derive the active resume prompt from current identity answers, and use a bounded current step instead of correcting step state through an effect. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/forms-shared-intake.test.tsx tests/react-regressions-source.test.ts`; changed-scope React Doctor no longer reports errors. |
| `react-hooks-js/todo` | `app/intake/[slug]/page.client.tsx` | Valid: restore/submit handlers used `finally`, and invalid form-payload handling used a throw inside a `try` path unsupported by React Compiler. | High | Replace finalizers with explicit success/error cleanup helpers and convert invalid payload handling to an early error state return. | Focused tests and full test suite passed; changed-scope React Doctor no longer reports compiler errors. |

Changed-scope command after Batch 12: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `85 / 100 Great`
- Total diagnostics in changed files: `28`
- Remaining changed-file warnings include manual memoization, upload/progress accessibility, lazy ref initialization, and structural `prefer-useReducer`/`no-giant-component`; all are valid but deferred because this batch targeted the 11-error intake cluster.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1e17099c-36b9-463c-9625-cda451fb98f4`

Full command after Batch 12: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `31 / 100 Critical`
- Total diagnostics: `1246`
- Summary: `Security 2 warnings`, `Bugs 22 errors + 254 warnings`, `Performance 82 errors + 36 warnings`, `Accessibility 49 warnings`, `Maintainability 801 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8574ec44-b8a2-41ef-bb4c-055b80d22701`

## Batch 13

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `app/embed/forms/[slug]/page.client.tsx` | Valid: the embedded form copied the initial parent origin into state through an effect, then cleared session state through another effect when slug/origin changed. | High | Initialize origin/loading/error as one bootstrap state object and key the active embed session by `slug + origin`, so stale tokens are ignored without effect-driven resets. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/forms-embed.test.tsx tests/react-regressions-source.test.ts`; changed-scope React Doctor no longer reports errors. |
| `react-hooks-js/todo` | `app/embed/forms/[slug]/page.client.tsx` | Valid: session creation, form loading, and submit handlers used `finally`, which blocks React Compiler optimization. | High | Replace finalizers with explicit cleanup after success/error handling while preserving duplicate-session guards and submit re-enable behavior. | Focused tests passed; changed-scope React Doctor no longer reports compiler errors for this file. |

Changed-scope command after Batch 13: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `5`
- Remaining changed-file warnings: `react-doctor/react-compiler-no-manual-memoization` and `react-doctor/prefer-useReducer` for `EmbedFormPageClient`; both are valid but larger cleanup than this 8-error batch.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-be34c1b5-456c-4b15-a882-dbe68339ee0f`

Full command after Batch 13: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `35 / 100 Critical`
- Total diagnostics: `1234`
- Summary: `Security 2 warnings`, `Bugs 19 errors + 250 warnings`, `Performance 77 errors + 36 warnings`, `Accessibility 49 warnings`, `Maintainability 801 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-741f62a4-3228-4c53-ad58-a41c66cebf69`

## Batch 14

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` | `app/(app)/settings/intelligent-suggestions-section.tsx` | Valid: the initial load effect immediately called a state-setting async loader, and a second effect normalized the new-rule stage draft by setting state after templates/stages changed. | High | Defer the initial loader through a timer and derive the normalized new-rule draft during render instead of writing normalized stage state from an effect. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/settings-page.test.tsx`; changed-scope React Doctor no longer reports errors. |
| `react-hooks-js/todo` | `app/(app)/settings/intelligent-suggestions-section.tsx` | Valid: settings load/save and rule create/toggle/update/delete handlers used `finally`, which blocks React Compiler optimization. | High | Replace finalizers with explicit cleanup after success/error handling while preserving toast/error behavior and rule-saving state resets. | Focused tests passed; changed-scope React Doctor no longer reports compiler errors for this file. |

Changed-scope command after Batch 14: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `9`
- Remaining changed-file warnings: `react-doctor/react-compiler-no-manual-memoization` for local callbacks/memos; valid but deferred because this batch targeted the 8-error compiler blockers.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-5c6f8b2e-878c-4f00-8e09-4ecf8aad9d5a`

Full command after Batch 14: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `39 / 100 Critical`
- Total diagnostics: `1224`
- Summary: `Security 2 warnings`, `Bugs 19 errors + 248 warnings`, `Performance 69 errors + 36 warnings`, `Accessibility 49 warnings`, `Maintainability 801 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9f5722fc-3c76-4013-8570-f967791b54ec`

## Batch 15

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `components/tasks/TaskEditModal.tsx` | Valid: the modal copied task fields into five local draft states from an effect, and callers pass freshly-created task objects that can reset user edits on parent re-render. | High | Replace separate field states with one keyed draft object initialized from `task.id`, then reset inline only when the active task id changes. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/tasks-page.test.tsx tests/react-regressions-source.test.ts`; changed-scope React Doctor reported no issues. |
| `react-hooks-js/todo` | `components/tasks/TaskEditModal.tsx` | Valid: the save handler used `finally`, which blocks React Compiler optimization. | High | Replace the finalizer with explicit success/error cleanup, keeping failed saves in the dialog and closing only after successful save. | Focused tests passed; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 15: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 15: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `43 / 100 Critical`
- Total diagnostics: `1210`
- Summary: `Security 2 warnings`, `Bugs 14 errors + 241 warnings`, `Performance 67 errors + 36 warnings`, `Accessibility 49 warnings`, `Maintainability 801 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-145efa15-c8ae-4717-a463-ec38fd06e325`

## Batch 16

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `components/surrogates/profile/ProfileCard/context.tsx` | Valid: profile overrides, hidden fields, staged changes, reveal state, mode, and section-open state were reset from effects when profile/schema data changed. | High | Collapse profile-local edit state into one `ProfileEditableState` keyed by a profile data fingerprint, and initialize section-open state from the same pure constructor. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/surrogate-profile-card-accessibility.test.tsx tests/surrogate-detail.test.tsx`; changed-scope React Doctor no longer reports errors. |
| `react-hooks-js/todo` | `components/surrogates/profile/ProfileCard/context.tsx` | Valid: profile PDF export used `finally`, which blocks React Compiler optimization. | High | Replace the finalizer with explicit success/error cleanup for `isExporting`. | Focused tests passed; changed-scope React Doctor no longer reports compiler errors for this file. |

Changed-scope command after Batch 16: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `90 / 100 Great`
- Total diagnostics in changed files: `31`
- Remaining changed-file warnings: manual memoization, provider size, and non-component exports in `ProfileCard/context.tsx`; valid but broader structural cleanup than this 8-error batch.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-5c76f200-bc85-4a5d-901c-608f757b865f`

Full command after Batch 16: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `47 / 100 Critical`
- Total diagnostics: `1202`
- Summary: `Security 2 warnings`, `Bugs 9 errors + 234 warnings`, `Performance 64 errors + 36 warnings`, `Accessibility 49 warnings`, `Maintainability 808 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-cd6c5c73-ec18-4498-8fc4-5fb0cbfd7031`

## Batch 17

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `app/(app)/settings/page.tsx` | Valid: profile fields and organization branding fields were reset through effects when user/signature/org settings changed, causing extra renders and risking draft loss on parent refreshes. | High | Replace profile and branding reset effects with keyed draft state derived from the active user/signature/org settings data. Move organization settings loading to a TanStack Query hook. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/settings-page.test.tsx`; full `pnpm test --run` passed; changed-scope React Doctor reported no issues. |
| `react-hooks-js/todo` | `app/(app)/settings/page.tsx` | Valid: profile save, organization branding save, org settings load, and preview handlers used `finally`, which blocks React Compiler optimization. | High | Remove finalizers and keep explicit success/error cleanup after awaited work. | Focused tests and changed-scope React Doctor reported no issues. |
| `react-doctor/control-has-associated-label` / `react-doctor/prefer-module-scope-pure-function` / `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/settings/page.tsx` | Valid: hidden file/color inputs lacked explicit labels, session helpers were rebuilt in `ActiveSessionsSection`, and preview sanitization had redundant manual memoization. | High | Add `aria-label` attributes, move session helpers to module scope, and derive sanitized preview HTML directly. | Focused tests and changed-scope React Doctor reported no issues. |

Changed-scope command before Batch 17 warning cleanup: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `90 / 100 Great`
- Total diagnostics in changed files: `6`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-0b5c4ab0-f541-40ce-8ade-2bbca072afff`

Changed-scope command after Batch 17 warning cleanup: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 17: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `51 / 100 Critical`
- Total diagnostics: `1183`
- Summary: `Security 2 warnings`, `Bugs 9 errors + 231 warnings`, `Performance 57 errors + 34 warnings`, `Accessibility 46 warnings`, `Maintainability 804 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-46cddc3e-cbdc-4176-b3f9-c00b63f174cc`

## Batch 18

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `app/(app)/settings/integrations/page.tsx` | Valid: the Zapier section copied inbound labels/secrets, field-paste webhook selection, outbound settings, stage mapping, and default test form id into local state through effects. | High | Replace effect-driven resets with keyed inbound/outbound draft state and derive active webhook/form defaults during render. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/integrations-page.test.tsx`; full `pnpm test --run` passed; changed-scope React Doctor no longer reports errors. |
| `react-hooks-js/todo` | `app/(app)/settings/integrations/page.tsx` | Valid: inbound webhook rotate/delete handlers used `finally`, which blocks React Compiler optimization. | High | Replace finalizers with explicit success/error cleanup for rotating/deleting ids. | Focused tests and changed-scope React Doctor no longer report compiler errors. |
| `react-doctor/role-supports-aria-props` / `react-doctor/prefer-tag-over-role` / `react-doctor/prefer-module-scope-pure-function` / `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/settings/integrations/page.tsx` | Valid: the webhook URL display used textbox ARIA on a non-input, copy/error helpers were rebuilt inside components, and a Zapier mapping value was manually memoized. | High | Remove unsupported textbox role/ARIA, move helper functions to module scope, and derive merged Zapier mapping directly. | Focused tests and changed-scope React Doctor no longer report these warnings. |

Changed-scope command after Batch 18: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `8`
- Remaining changed-file warnings: `no-giant-component` for several integrations sections and `prefer-useReducer` for `ZapierWebhookSection`; valid but larger structural refactors than this error-cleanup batch.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-13fb630a-7549-4643-81f7-e82eb49047c6`

Full command after Batch 18: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `54 / 100 Critical`
- Total diagnostics: `1166`
- Summary: `Security 2 warnings`, `Bugs 9 errors + 226 warnings`, `Performance 51 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 800 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8373784c-a1e6-4128-85b2-1663d9c74922`

## Batch 19

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `components/ai/AIChatPanel.tsx` | Valid: conversation messages and context-change stream state were synchronized through effects, causing extra renders and stale intermediate chat state. | High | Replace copied message state with keyed panel message state derived during render unless a stream is active, and adjust active stream state inline when the panel context changes. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/ai-chat-panel.test.tsx`; changed-scope React Doctor no longer reports errors. |
| `react-hooks-js/todo` | `components/ai/AIChatPanel.tsx` | Valid: the stream send handler used a `finally` clause, which blocks the current React Compiler path. | High | Replace the finalizer with explicit success/error/abort cleanup after awaited stream handling. | Focused tests passed; changed-scope React Doctor no longer reports compiler errors for this file. |
| `react-doctor/exhaustive-deps` | `components/ai/AIChatPanel.tsx` | Valid: the unmount cleanup read `streamAbortRef.current` directly. The current stream still needs latest-ref cleanup, but the dependency rule can be satisfied by moving the ref read behind a helper and depending on the ref object. | High | Add focused stream/frame cleanup helpers and use them from cleanup and event paths without suppressions. | Changed-scope React Doctor no longer reports the cleanup warning for this file. |

Changed-scope command after Batch 19: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Remaining changed-file warnings: `no-giant-component` and `prefer-useReducer` for `AIChatPanel`; both are valid but larger structural refactors than this error-cleanup batch.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-eb47f359-2923-4694-a202-a3c854e13555`

Full command after Batch 19: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1150`
- Summary: `Security 2 warnings`, `Bugs 7 errors + 219 warnings`, `Performance 49 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 795 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-96adef86-7974-4f35-b808-1858307c7ce7`

## Batch 20

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `lib/hooks/use-forms.ts` | Valid: three submission mutation hooks used dynamic `import()` expressions inside mutation functions even though `lib/hooks/use-forms.ts` already statically imports the forms API module. React Compiler currently cannot lower those import expressions. | High | Statically import `updateSubmissionAnswers`, `uploadSubmissionFile`, and `deleteSubmissionFile`, then call them directly from the mutation functions. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/use-mutation-invalidations.test.ts`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 20: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 20: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1147`
- Summary: `Security 2 warnings`, `Bugs 7 errors + 219 warnings`, `Performance 46 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 795 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-95348cac-83d8-436d-9777-aa0dbefb59dc`

## Batch 21

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/surrogates/interviews/InterviewComments/context.tsx` | Valid: comment, general-note, and reply submission handlers used `try`/`finally`, which blocks the current React Compiler path. | High | Replace finalizers with a promise-result helper that preserves rejected promises while explicitly clearing submission state. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/surrogate-interview-accessibility.test.tsx tests/transcript-viewer.test.tsx`; changed-scope React Doctor no longer reports errors. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/interviews/InterviewComments/context.tsx`, `components/surrogates/interviews/InterviewComments/CommentsSidebar.tsx` | Valid: React Compiler is enabled, so the local `useMemo`/`useCallback` wrappers are redundant in this context provider and sidebar. | High | Derive note lists/maps directly and use plain local functions. | Focused tests passed; changed-scope React Doctor no longer reports manual memoization warnings for these files. |
| `react-doctor/only-export-components` | `components/surrogates/interviews/InterviewComments/context.tsx` | Valid: `getMinSidebarHeight` is a non-component helper exported from a component file and used by sibling components. | High | Move the helper to `comment-layout.ts` and update sibling imports. | Focused tests passed; changed-scope React Doctor no longer reports `only-export-components` for this file. |

Changed-scope command after Batch 21: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `97 / 100 Great`
- Total diagnostics in changed files: `1`
- Remaining changed-file warning: `prefer-useReducer` for `InterviewCommentsProvider`; valid but larger state-shape refactor than this compiler-error batch.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-05b73d4c-ad91-4994-9e06-5bf0c28edf69`

Full command after Batch 21: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1124`
- Summary: `Security 2 warnings`, `Bugs 7 errors + 219 warnings`, `Performance 43 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 775 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1b251672-af4f-4d35-9a01-1e9241a83852`

## Batch 22

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/ui/calendar.tsx` | Valid: the RTL class names used `String.raw` tagged templates to preserve escaped Tailwind arbitrary selector underscores. React Compiler cannot lower that tagged template shape even though the value is static. | High | Replace the tagged templates with regular escaped string literals and add a source regression guard so the compiler-hostile form does not return. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor no longer reports compiler errors for the file. |

Changed-scope command after Batch 22: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `97 / 100 Great`
- Total diagnostics in changed files: `1`
- Remaining changed-file warning: `no-event-handler` for `components/ui/calendar.tsx`; valid but separate from the compiler syntax fix.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ec31bfd3-7e3b-4251-9f8e-206607433e60`

Full command after Batch 22: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1122`
- Summary: `Security 2 warnings`, `Bugs 7 errors + 219 warnings`, `Performance 41 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 775 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8941d365-9539-4666-88df-643512547bd0`

## Batch 23

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-adjust-state-on-prop-change` | `components/appointments/UnifiedCalendar.tsx` | Valid: the appointment detail dialog copied appointment link fields into local draft state through an effect after open/appointment changes, so a newly opened dialog could briefly render stale link-edit state. | High | Initialize the link draft state from the appointment when the dialog mounts and key the dialog by open appointment/link identity so each appointment opens with a fresh synchronous draft. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor no longer reports errors for the file. |

Changed-scope command after Batch 23: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `89 / 100 Great`
- Total diagnostics in changed files: `37`
- Remaining changed-file diagnostics: warnings only, led by `react-compiler-no-manual-memoization`, `prefer-tag-over-role`, `rerender-state-only-in-handlers`, `no-giant-component`, and `prefer-useReducer` in `UnifiedCalendar`; valid but larger refactor work than this state-sync error batch.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-70e0272c-5d37-46f4-ae11-d0cf70197ae0`

Full command after Batch 23: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1115`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 214 warnings`, `Performance 40 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 776 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4e1ccb8a-4ad5-49ac-8435-5de23df7f6f5`

## Batch 24

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-initialize-state` | `hooks/use-mobile.ts` | Valid: `useIsMobile` rendered an empty initial value and then set state in an effect from `window.innerWidth`, even though the real subscription source is `matchMedia`. | High | Replace effect-managed local state with `useSyncExternalStore` over the mobile media query. Added a hook test that fails when `matchMedia.matches` and `innerWidth` disagree. | `pnpm tsc --noEmit`; `pnpm test --run tests/use-mobile.test.tsx`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 24: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 24: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1113`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 213 warnings`, `Performance 39 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 776 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-0f7fa248-f09a-4814-85e7-102ea5f8dfc0`

## Batch 25

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-initialize-state` / `react-hooks-js/todo` | `app/(app)/settings/notifications/page.tsx` | Valid: the browser notification card initialized permission through an effect, treated a present-but-undefined `Notification` global as supported, and used `try/finally` in the request handler. | High | Read browser notification permission during state initialization, treat missing `Notification` as unsupported, and replace the request finalizer with an explicit promise chain cleanup. Added source and UI regression coverage. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/notification-settings-page.test.tsx`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 25: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 25: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1109`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 211 warnings`, `Performance 37 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 776 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-465a774f-bd78-4a29-a2ad-2cad01c756d5`

## Batch 26

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/surrogates/journey/JourneyTimeline.tsx` | Valid: journey milestone metadata used a mutable `globalIndex++` counter inside nested `map` calls, which React Compiler cannot lower cleanly. | High | Replace the mutable counter with a reducer that carries `nextIndex` across phases, matching the existing print-view pattern. Added a source regression guard. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 26: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 26: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1108`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 211 warnings`, `Performance 36 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 776 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8739e2f8-25c6-4cfb-a216-90c485027fdb`

## Batch 27

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` | `components/ui/date-time-picker.tsx` | Valid: the picker already resets its draft from `value` in the popover open handler, so the open-gated effect repeated the same prop-to-state synchronization after render. | High | Remove the duplicate effect and keep draft synchronization in the user-triggered open handler. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 27: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 27: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1105`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 209 warnings`, `Performance 35 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 776 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4b7fd980-5254-4701-9dc5-c2c6f2d62922`

## Batch 28

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` | `components/ui/date-range-picker.tsx` | Valid: `calendarDefaultMonth` only mirrored `customRange?.from` or today through an effect for `Calendar.defaultMonth`, while the picker already resets its local range when opening the custom calendar. | High | Remove the mirrored month state/effect and derive the calendar default month from the local range or incoming custom range. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/date-range-picker.test.tsx`; changed-scope React Doctor reported no issues. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/ui/date-range-picker.tsx` | Valid: React Compiler is enabled, so the local `useMemo` around `availableDateSet` is redundant manual memoization in a touched file. | High | Replace the manual memo with the plain derived `Set`. Added a source regression guard that failed before the fix. | Focused tests passed; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 28: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 28: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `55 / 100 Critical`
- Total diagnostics: `1102`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 208 warnings`, `Performance 34 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 775 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-109b5f61-ea30-4f43-beac-c90a9a0bdfe0`

## Batch 29

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/set-state-in-effect` / `react-doctor/no-derived-state` / `react-doctor/no-derived-useState` | `components/surrogates/journey/MilestoneImageSelector.tsx` | Valid: the selected featured-image draft copied `currentAttachmentId` into local state in an effect after opening, so reopening a dialog could briefly retain a stale cancelled selection. | High | Track the selected image in a small draft-state object and reset it synchronously when `open` or `currentAttachmentId` changes. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor reported no issues. |
| `react-hooks-js/todo` / `react-doctor/no-event-handler` / `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/journey/MilestoneImageSelector.tsx` | Valid: image preview URLs were loaded through a mutation, `useCallback`, an effect, and a `try/finally` finalizer even though they are server-state reads. | High | Replace mutation/effect URL loading with `useQueries` keyed by attachment id, and remove the `try/finally`, local URL/loading state, and manual callback memoization. | Focused tests passed; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 29: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 29: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1094`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 203 warnings`, `Performance 32 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 774 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-5a972b32-7ed2-488f-8141-62fa84a8ef2f`

## Batch 30

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/surrogates/journey/SurrogateJourneyTab.tsx` | Valid: the journey export handler used a `try/finally` finalizer, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch and clear `exportingVariant` after success or failure handling. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor reported no issues. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/journey/SurrogateJourneyTab.tsx` | Valid: React Compiler is enabled, so `useMemo`/`useCallback` wrappers around milestone lookup and handlers are redundant in this touched component. | High | Use a plain derived `Map` and plain local handlers. | Focused tests passed; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 30: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 30: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1090`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 203 warnings`, `Performance 31 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 771 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-12a6ff81-4a60-4fd3-9824-8cff40a97283`

## Batch 31

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/(app)/settings/sessions/page.tsx` | Valid: the individual session revoke handler used a `try/finally` finalizer only to clear row-level revoking state, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch and clear `revokingSessionId` after success or failure handling. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 31: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 31: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1089`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 203 warnings`, `Performance 30 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 771 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e7e5d44d-f415-4ea5-9fc3-3087def7efbd`

## Batch 32

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/(app)/welcome/page.tsx` | Valid: the profile completion submit handler used a `try/finally` finalizer only to clear submitting state, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch and clear `isSubmitting` after success or failure handling. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/welcome-page.test.tsx`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 32: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 32: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1088`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 203 warnings`, `Performance 29 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 771 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e52fa172-20a9-4867-87ce-fcb04f959aa8`

## Batch 33

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/ops/alerts/page.client.tsx` | Valid: the acknowledge and resolve handlers used `try/finally` finalizers only to clear row-level loading state, which blocks the current React Compiler path. | High | Replace both finalizers with explicit promise-result branches and clear `actionLoading` after success or failure handling. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/ops-alerts-page.test.tsx`; changed-scope React Doctor reported no issues after also addressing touched-file memoization. |
| `react-doctor/react-compiler-no-manual-memoization` | `app/ops/alerts/page.client.tsx` | Valid: React Compiler is enabled, so the touched file's `useCallback` around `fetchAlerts` is redundant manual memoization. | High | Move alert loading into a module-level helper and use a plain refresh handler plus a filter-driven effect. Extended the source guard to fail on reintroduced `useCallback`. | Focused tests passed; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 33: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 33: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1085`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 203 warnings`, `Performance 27 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 770 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-08c82089-5bb1-4bb6-a696-806ad3490683`

## Batch 34

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/ops/page.client.tsx`, `app/ops/agencies/new/page.client.tsx` | Valid: the ops dashboard load effect and new-agency submit handler used `try/finally` only to clear loading/submitting state, which blocks the current React Compiler path. | High | Replace both finalizers with explicit promise-result branches and clear loading state after success or failure handling. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor reported no issues after also addressing touched-file helper placement. |
| `react-doctor/prefer-module-scope-pure-function` | `app/ops/agencies/new/page.client.tsx` | Valid: `generateSlug` is pure and does not read component state, so rebuilding it on every render is unnecessary. | High | Move `generateSlug` to module scope and extend the source guard to require the helper outside the component. | Focused tests passed; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 34: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 34: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1082`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 203 warnings`, `Performance 25 errors + 34 warnings`, `Accessibility 44 warnings`, `Maintainability 769 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-bbb927ed-b5ce-40e4-85e9-2f95ca4bb331`

## Batch 35

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/intended-parents/TrustInfoCard.tsx` | Valid: the trust address and trust notes save handlers used `try/finally` only to clear saving state, which blocks the current React Compiler path. | High | Replace both finalizers with explicit promise-result branches and clear `isSaving` after success or failure handling. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/intended-parent-detail.test.tsx`; changed-scope React Doctor reported no issues after also addressing touched-file button semantics. |
| `react-doctor/prefer-tag-over-role` | `components/intended-parents/TrustInfoCard.tsx` | Valid: the trust address and notes edit affordances were clickable `div` elements with `role="button"`, but native buttons provide the intended interaction semantics. | High | Convert both affordances to `button type="button"` and remove custom keyboard handling. Extended the source guard to fail on reintroduced `role="button"`. | Focused tests passed; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 35: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 35: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1078`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 203 warnings`, `Performance 23 errors + 34 warnings`, `Accessibility 42 warnings`, `Maintainability 769 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-33d06a75-09d8-464b-9a4f-8aabd2a08324`

## Batch 36

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/intended-parents/IntendedParentClinicCard.tsx` | Valid: the select save and delete-section handlers used `try/finally` only to clear saving/deleting state, which blocks the current React Compiler path. | High | Replace both finalizers with explicit promise-result branches; preserve prior error propagation by clearing loading state before rethrowing failed saves/deletes. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/intended-parent-detail.test.tsx`; changed-scope React Doctor no longer reports the compiler blocker. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/intended-parents/IntendedParentClinicCard.tsx` | Valid: React Compiler is enabled, so the touched file's `useMemo` wrappers around small section derivations are redundant. | High | Replace the three memoized derivations with plain render-time derivation while keeping the existing single-pass section logic. Extended the source guard to fail on reintroduced `useMemo`. | Focused tests passed; full React Doctor shows redundant memoization dropped by 3. |
| `react-doctor/rerender-state-only-in-handlers` | `components/intended-parents/IntendedParentClinicCard.tsx` | Invalid: `manuallyAddedSections` and `optimisticallyHiddenSections` are read during render to compute `visibleSections`, which controls whether clinic/embryo sections render. They are not handler-only refs. | High | Leave as state. No suppression added; logged as an invalid touched-file finding. | Existing intended-parent detail tests cover adding/hiding clinic sections. |

Changed-scope command after Batch 36: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `97 / 100 Great`
- Total diagnostics in changed files: `2`
- Invalid diagnostics: `react-doctor/rerender-state-only-in-handlers` for `manuallyAddedSections` and `optimisticallyHiddenSections`

Full command after Batch 36: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1075`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 203 warnings`, `Performance 21 errors + 36 warnings`, `Accessibility 42 warnings`, `Maintainability 766 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-c172d2ed-f46d-40ed-81b9-078698845329`

## Batch 37

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/surrogates/PregnancyTrackerCard.tsx` | Valid: the embryo-stage save handler used a `try/finally` finalizer only to clear saving state, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch and clear `isSavingEmbryoStage` after success or failure handling. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/surrogate-detail.test.tsx`; isolated changed-scope React Doctor reported no issues. |
| `react-doctor/prefer-tag-over-role` | `components/surrogates/PregnancyTrackerCard.tsx` | Valid: the embryo-stage display was a clickable `div` with `role="button"`, but a native button fits the interaction and removes custom keyboard handling. | High | Convert the display affordance to `button type="button"` and remove the manual key handler. Extended the source guard to fail on reintroduced `role="button"`. | Focused tests passed; isolated changed-scope React Doctor reported no issues. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/PregnancyTrackerCard.tsx` | Valid: React Compiler is enabled, so the local `useMemo` around pregnancy tracking derivation is redundant in this touched component. | High | Derive pregnancy tracking values directly inside the hook and remove the `useMemo` import. Extended the source guard to fail on reintroduced `useMemo`. | Focused tests passed; full React Doctor shows redundant memoization dropped by 1. |
| `react-doctor/control-has-associated-label` | `components/surrogates/PregnancyTrackerCard.tsx` | Valid: the icon-only due-date edit control rendered through the badge had no accessible name. | High | Add `aria-label="Edit due date"` to the rendered button and assert it in the source guard. | Focused tests passed; isolated changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 37: `cd /private/tmp/react-doctor-pregnancy-codex-84352/apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 37: `cd /private/tmp/react-doctor-pregnancy-codex-84352/apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1071`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 203 warnings`, `Performance 20 errors + 36 warnings`, `Accessibility 40 warnings`, `Maintainability 765 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4ec3cb42-c84f-42f2-b5ce-c83308903860`

## Batch 38

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/surrogates/CombinedMedicalInsuranceCard.tsx` | Valid: the section delete handler used a `try/finally` finalizer only to clear deleting state, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch, clear `isDeletingSection` after success or failure handling, and preserve prior rejection behavior by rethrowing failed deletes after cleanup. Extended the source regression guard so it failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor no longer reports the compiler blocker. |
| `react-hooks/set-state-in-effect` | `components/surrogates/CombinedMedicalInsuranceCard.tsx` | Valid: the optimistic hidden-section cleanup effect synchronously set state after render. | High | Replace effect cleanup with optimistic hidden entries keyed to the current `surrogateData` object, so the section is hidden only while the stale pre-update data snapshot is still rendering. Extended the source guard to fail on reintroduced `useEffect`. | Focused source guard and TypeScript passed; `pnpm lint` no longer reports this file's set-state-in-effect warning. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/CombinedMedicalInsuranceCard.tsx` | Valid: React Compiler is enabled, so the local `useMemo` wrappers around section derivation are redundant in this touched component. | High | Derive section lists directly during render with explicit loops and no chained `filter().map()` sweep. Extended the source guard to fail on reintroduced `useMemo`. | Focused source guard passed; full React Doctor shows redundant memoization dropped by 3. |
| `react-doctor/rerender-state-only-in-handlers` | `components/surrogates/CombinedMedicalInsuranceCard.tsx` | Invalid: `manuallyAdded` and `optimisticallyHiddenSections` are read during render to build `visibleSections`, which determines whether medical/insurance sections are shown. They are not handler-only refs. | High | Leave as state. No suppression added; logged as an invalid touched-file finding. | Changed-scope React Doctor reports only these two warnings, score `97 / 100 Great`. |

Changed-scope command after Batch 38: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `97 / 100 Great`
- Total diagnostics in changed files: `2`
- Invalid diagnostics: `react-doctor/rerender-state-only-in-handlers` for `manuallyAdded` and `optimisticallyHiddenSections`

Full command after Batch 38: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1067`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 202 warnings`, `Performance 18 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 762 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a68560ac-8bbb-47de-86cd-056bcdacffdc`

## Batch 39

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/(app)/surrogates/unassigned/page.client.tsx` | Valid: the claim handler used a `try/finally` finalizer only to clear row-level claiming state, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch and clear `claimingId` after success or error handling while preserving success/error toasts. Extended the source regression guard so it failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor reported no issues. |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/surrogates/unassigned/page.client.tsx` | Valid: React Compiler is enabled, so the local `useCallback` wrappers around pagination and claim handlers are redundant in this touched page. | High | Use plain local functions for `setPageAndUrl` and `handleClaim`. Extended the source guard to fail on reintroduced `useCallback`. | Focused source guard passed; full React Doctor shows redundant memoization dropped by 2. |

Changed-scope command after Batch 39: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 39: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1064`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 202 warnings`, `Performance 17 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 760 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-475793fe-2fb2-453f-8b38-876fddd42a62`

## Batch 40

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/surrogates/detail/SurrogateDetailLayout/HeaderActions.tsx` | Valid: the export action used a `try/finally` finalizer only to clear exporting state, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch, preserve success/failure toasts, and clear `isExporting` after success or error handling. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/header-actions.test.tsx`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 40: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 40: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1063`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 202 warnings`, `Performance 16 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 760 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-acf1eb78-f412-402b-9291-da663cec8a77`

## Batch 41

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/ops/agencies/SupportSessionDialog.tsx` | Valid: the support-session start handler used a `try/finally` finalizer only to clear submitting state, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch, preserve popup redirect/close behavior and success/error toasts, and clear submitting after success or error handling. Extended the source guard so it failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/ops-support-session-dialog.test.tsx`; changed-scope React Doctor reported no issues. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/ops/agencies/SupportSessionDialog.tsx` | Valid: React Compiler is enabled, so the local `useMemo` wrappers around portal URL normalization and host derivation are redundant in this touched component. | High | Move URL normalization and portal host derivation into module-scope helpers and call them directly during render. Extended the source guard to fail on reintroduced `useMemo`. | Focused tests passed; full React Doctor shows redundant memoization dropped by 2. |

Changed-scope command after Batch 41: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 41: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics: `1060`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 202 warnings`, `Performance 15 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 758 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-c46f877d-aaff-4696-9400-694179773891`

## Batch 42

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `lib/auth-context.tsx` | Valid: the auth fetch helper used a `try/finally` finalizer only to clear loading state, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch and clear loading after success or error handling while preserving 401-as-logged-out behavior. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/auth-context.test.tsx`; changed-scope React Doctor reported no issues. |
| `react-hooks/set-state-in-effect` | `lib/auth-context.tsx` | Valid: the mount effect directly called `fetchUser`, which synchronously set loading/error state before the effect returned. | High | Initialize ops-route loading state synchronously with `shouldSkipAuthFetch`, then defer the mount fetch with `window.setTimeout` so the effect schedules external work instead of directly setting state. Extended the source guard to fail on the old mount flow. | `pnpm lint` no longer reports the `lib/auth-context.tsx` warning; focused auth tests passed. |

Changed-scope command after Batch 42: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 42: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `57 / 100 Critical`
- Total diagnostics: `1057`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 201 warnings`, `Performance 13 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 758 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-08071977-253f-4c22-a91c-34f33a7972ac`

## Batch 43

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/invite/[id]/page.client.tsx` | Valid: the invite acceptance loader used a `try/finally` finalizer only to clear loading state, which blocks the current React Compiler path. | High | Replace the finalizer with an explicit promise-result branch and clear loading after success or error handling while preserving success and missing-invite behavior. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/invite-page.test.tsx`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 43: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`

Full command after Batch 43: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `57 / 100 Critical`
- Total diagnostics: `1056`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 201 warnings`, `Performance 12 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 758 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1a6ce04e-e219-40d2-a970-c4d918f461c8`

## Batch 44

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/(app)/reports/page.tsx` | Valid: the reports PDF export handler used a `try/finally` finalizer only to clear exporting state, which blocks the current React Compiler path and surfaced twice in the same handler. | High | Replace the finalizer and thrown HTTP failure with a typed promise-result branch, preserve success download behavior, preserve failure toast copy, and clear exporting after success or error handling. Added a source regression guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/reports-page.test.tsx`; full React Doctor errors dropped from `17` to `15`. |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/reports/page.tsx` | Valid: React Compiler is enabled, so the local `useMemo` wrappers around report date, counts, top items, insights, and campaign labels are redundant in this touched page. | High | Replace those wrappers with plain derived values and module-scope helpers. Extended the source guard so it failed on reintroduced `useMemo`. | Focused tests and TypeScript passed; changed-scope React Doctor no longer reports redundant memoization for the reports page. |
| `react-doctor/prefer-module-scope-pure-function` | `app/(app)/reports/page.tsx` | Valid: `formatTokens`, `isPerformanceMode`, and `formatShortDate` used no render-local state and were rebuilt during render. | High | Move the helpers to module scope and reuse them from render. Extended the source guard so it failed on render-local helper declarations. | Focused tests and TypeScript passed; full React Doctor pure-function count dropped from `36` to `33`. |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/reports/page.tsx` | Valid but deferred: `ReportsPage` remains a large component with five state hooks. Fixing it requires a component split and state-shape decision beyond the export/compiler cleanup. | High | Logged for a later structural reports-page batch instead of mixing a broader refactor into this commit. | Changed-scope React Doctor reports only these two remaining warnings for the reports page. |

Changed-scope command after Batch 44: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e7e0446a-a495-4605-81d9-f2465ad49ed6`

Full command after Batch 44: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `57 / 100 Critical`
- Total diagnostics: `1043`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 201 warnings`, `Performance 10 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 747 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7ad751bb-d8d1-4e32-aa10-d5f8e1a8d5ab`

## Batch 45

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `components/surrogates/interviews/InterviewTab/context.tsx` | Valid: transcription start used a `try/finally` finalizer only to clear upload state, which blocks the current React Compiler path. | High | Replace the finalizer with a typed mutation-result branch, preserve success/error toasts, and clear upload state after success or error handling. Extended the source guard so it failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/interview-tab.test.tsx`; full React Doctor errors dropped from `15` to `13`. |
| `react-hooks/set-state-in-effect` | `components/surrogates/interviews/InterviewTab/context.tsx` | Valid: the editor reset effect synchronously copied dialog/interview data into form state after render. | High | Move form construction into `buildInterviewFormState` and reset form directly when `openEditor` runs, eliminating the editor-reset effect while preserving add/edit dialog initialization. | Focused interview tests passed; `pnpm lint` no longer reports the `InterviewTab/context.tsx:206` warning. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/interviews/InterviewTab/context.tsx` | Valid: React Compiler is enabled, so local `useCallback` wrappers and the context `useMemo` wrapper are redundant in this touched provider. | High | Use plain local functions and a plain typed context value object. Extended the source guard so it failed on reintroduced `useCallback` or `useMemo`. | Focused tests and TypeScript passed; full React Doctor redundant memoization count dropped from `614` to `594`. |
| `react-doctor/async-await-in-loop`, `react-doctor/no-giant-component` | `components/surrogates/interviews/InterviewTab/context.tsx` | Valid but deferred: attachment uploads are intentionally sequential today and provider extraction is a broader structural change. | Medium | Logged for a later interview-context batch instead of mixing upload semantics or provider decomposition into this commit. | Changed-scope React Doctor reports only these two remaining warnings for the interview context. |

Changed-scope command after Batch 45: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Performance 1 warning`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-824536a3-44ff-416e-870a-9d879b4d0a16`

Full command after Batch 45: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `57 / 100 Critical`
- Total diagnostics: `1018`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 198 warnings`, `Performance 8 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 727 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e65463b5-17ec-43a9-947e-55d614e906a1`

## Batch 46

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/(app)/ai-studio/page.tsx` | Valid: reference image import used a `try/finally` finalizer only to clear the adding-image flag, which blocks the current React Compiler path. | High | Replace the finalizer with a typed `Promise.all` result branch, preserve duplicate filtering and validation errors, and clear adding-image state after success or error handling. Added a source guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/ai-studio-page.test.tsx`; full React Doctor finalizer errors dropped from `3` to `2`. |
| `react-hooks/set-state-in-effect` | `app/(app)/ai-studio/page.tsx` | Valid: the settings dialog effect synchronously copied fetched settings into local form state after render. | High | Move settings form construction into `buildSettingsFormState` and initialize it in `openSettingsDialog`, preserving the settings dialog behavior without the effect. | Focused AI Studio tests passed; `pnpm lint` no longer reports the `ai-studio/page.tsx:564` warning. |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/ai-studio/page.tsx` | Valid: React Compiler is enabled, so the permission `useMemo` wrapper is redundant in this touched page. | High | Build the permission `Set` directly during render and extend the source guard so it fails on reintroduced `useMemo`. | Focused tests and TypeScript passed; full React Doctor redundant memoization count dropped from `594` to `593`. |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/ai-studio/page.tsx` | Valid but deferred: `AIStudioPage` remains a large component with nineteen local state hooks. Fixing it requires a page/component split and state-shape decision beyond the compiler-blocker cleanup. | High | Logged for a later AI Studio structural batch instead of mixing a broader page refactor into this commit. | Changed-scope React Doctor reports only these two remaining warnings for AI Studio. |

Changed-scope command after Batch 46: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-950a1d61-5004-43c7-ab42-bb7498698dc1`

Full command after Batch 46: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `58 / 100 Critical`
- Total diagnostics: `1010`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 193 warnings`, `Performance 6 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 726 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ee46da21-c078-4d88-bae2-c1777ee2a8d0`

## Batch 47

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks-js/todo` | `app/ops/templates/workflows/[id]/page.client.tsx` | Valid: workflow save and publish used `try/finally` finalizers only to clear saving/publishing state, which blocks the current React Compiler path. | High | Replace both finalizers with typed result branches, preserve validation short-circuits, success toasts, failure toasts, publish dialog close behavior, and published-state updates. Added a source guard that failed before the fix. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; full React Doctor finalizer errors dropped from `2` to `0`. |
| `react-doctor/react-compiler-no-manual-memoization`, `react-doctor/prefer-module-scope-pure-function`, `react-doctor/no-many-boolean-props` | `app/ops/templates/workflows/[id]/page.client.tsx` | Valid but deferred: the workflow editor still has memoized trigger helpers/options, a render-local validation helper, and a boolean-heavy header API. | Medium | Logged for a later workflow-editor cleanup because those changes touch hook dependency behavior and component API shape beyond the save/publish finalizer fix. | Changed-scope React Doctor reports only these workflow-editor warnings after the finalizer fix. |

Changed-scope command after Batch 47: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `90 / 100 Great`
- Total diagnostics in changed files: `13`
- Summary: `Maintainability 13 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9dd9770b-62de-42d7-9c3c-555e96b48fe0`

Full command after Batch 47: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `58 / 100 Critical`
- Total diagnostics: `1008`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 193 warnings`, `Performance 4 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 726 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-f3ac4b77-1493-42f3-9d03-e0dd6a574e98`

## Batch 48

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks/preserve-manual-memoization` | `components/surrogates/detail/SurrogateDetailLayout/context.tsx` | Valid: `visibleStageOptions` read `user.role`, while its dependency array used `user?.role`; React Compiler inferred the broader `user` dependency and skipped optimizing the provider. | High | Align the manual memo dependency with the compiler-inferred `user` object dependency while preserving the existing memoized context-value shape. Extended the source guard so it failed on the old dependency array. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; full React Doctor errors dropped from `9` to `8`. |
| `react-doctor/react-compiler-no-manual-memoization`, `react-doctor/no-event-handler`, `react-doctor/no-giant-component` | `components/surrogates/detail/SurrogateDetailLayout/context.tsx` | Valid but deferred: the provider still has many manual memo wrappers, a dialog-reset effect, and an oversized provider body. | Medium | Logged for a later provider-structure batch because removing all provider memoization and moving event logic changes a broad context API and render-propagation surface beyond this single compiler-skip fix. | Changed-scope React Doctor reports these warnings after the dependency fix. |

Changed-scope command after Batch 48: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `90 / 100 Great`
- Total diagnostics in changed files: `33`
- Summary: `Bugs 1 warning`, `Maintainability 32 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a557290c-f078-402f-a8c9-1af451c4c18c`

Full command after Batch 48: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `59 / 100 Critical`
- Total diagnostics: `1007`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 193 warnings`, `Performance 3 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 726 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-82642791-6da4-4b7f-bc6a-154def5ce780`

## Batch 49

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks/set-state-in-effect` | `components/forms/PublicFormFieldRenderer.tsx` | Valid: the height field effect synchronously copied incoming prop-derived feet/inches into local select state after render. | High | Replace the two mirrored select states and reset effect with a single draft selection keyed by the serialized height value, so external prop changes are derived during render while user-cleared drafts remain stable after parent acceptance. Added a source guard that failed on the old effect. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/public-form-field-renderer.test.tsx`; `pnpm lint` no longer reports `PublicFormFieldRenderer.tsx:426`; full React Doctor errors dropped from `8` to `7`. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/forms/PublicFormFieldRenderer.tsx` | Valid: `FixedTableFieldInput` memoized rows derived directly from props even though React Compiler can cache the value. | High | Remove the `React.useMemo` wrapper and compute normalized table rows directly during render. Extended the source guard so it failed before this fix. | Changed-scope React Doctor dropped from `2` warnings to `1` warning after removing the wrapper. |
| `react-doctor/prefer-tag-over-role` | `components/forms/PublicFormFieldRenderer.tsx` | Invalid: the flagged `role="group"` wraps a configured table row, not contact information; replacing it with `<address>` would give incorrect native semantics. | High | Left the row container as `role="group"` and logged the false positive instead of changing semantics for score. | Changed-scope React Doctor reports this as the only remaining touched-file warning. |

Changed-scope command after Batch 49: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `97 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Accessibility 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-3ed0baa0-5fc9-43bf-a566-efcd54e6a137`

Full command after Batch 49: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `60 / 100 Needs work`
- Total diagnostics: `998`
- Summary: `Security 2 warnings`, `Bugs 5 errors + 189 warnings`, `Performance 2 errors + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 722 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-23c8c09e-1d5d-4308-a741-bac3ed6f2fe1`

## Batch 50

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks/set-state-in-effect`, `react-doctor/no-adjust-state-on-prop-change` | `components/forms/builder/ShareApplicationDialog.tsx` | Valid: the dialog effect synchronously copied `selectedQrLink` props into local embed-settings state, creating a stale render when the selected link changed. | High | Replace the effect with render-derived settings plus a link-keyed local draft, preserving local edits for the active link and deriving settings immediately when a different link is selected. Added a behavior test for switching links and a source guard that failed on the old effect. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/share-application-dialog.test.tsx`; full React Doctor errors dropped from `7` to `5`. |
| `react-doctor/no-giant-component` | `components/forms/builder/ShareApplicationDialog.tsx` | Valid but deferred: `ShareApplicationDialog` remains a large component after removing the state-sync effect. | Medium | Logged for a later structural split because extracting the hosted/QR/embed tab sections is broader than the prop-sync error fix. | Changed-scope React Doctor reports this as the only remaining touched-file warning. |

Changed-scope command after Batch 50: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-57e5fe16-a8fc-4df1-a0e4-dc456e859f8a`

Full command after Batch 50: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `61 / 100 Needs work`
- Total diagnostics: `995`
- Summary: `Security 2 warnings`, `Bugs 4 errors + 188 warnings`, `Performance 1 error + 38 warnings`, `Accessibility 40 warnings`, `Maintainability 722 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-152446e0-0bc3-4593-a69e-154b5189c43f`

## Batch 51

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-hooks/set-state-in-effect`, `react-doctor/no-adjust-state-on-prop-change` | `components/forms/builder/FormBuilderWorkspace.tsx` | Valid: the field inspector effect synchronously reset the active settings tab to General after `selectedFieldData.id` changed, causing a stale Advanced tab render for the newly selected field. | High | Replace the effect with selected-field-keyed tab state so a different field derives `general` during render while preserving tab selection for the active field. Added a behavior test for switching fields and a source guard that failed on the old effect. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/form-builder-page.test.tsx`; full React Doctor errors dropped from `5` to `3`. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/forms/builder/FormBuilderWorkspace.tsx` | Valid: React Compiler is enabled, so the touched workspace's `useMemo`/`useCallback` wrappers around canvas fields, page labels, conditional field lists, and lookup maps were redundant. | High | Remove the wrappers and derive these values directly during render. Extended the source guard so it failed on reintroduced manual memoization. | Changed-scope React Doctor dropped from `7` warnings to `2` warnings. |
| `react-doctor/prefer-tag-over-role`, `react-doctor/no-giant-component` | `components/forms/builder/FormBuilderWorkspace.tsx` | Valid but deferred: changing the field surface from `role="button"` to `<button>` needs a nested-action-button restructure, and splitting `FieldInspector` is a broad component extraction. | Medium | Logged for a later structural form-builder batch instead of mixing markup/API restructuring into this prop-sync fix. | Changed-scope React Doctor reports only these two warnings after the tab and memoization cleanup. |

Changed-scope command after Batch 51: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Accessibility 1 warning`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-fb2a7fcf-2a81-4bd3-a84b-c50fa3c7d107`

Full command after Batch 51: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `63 / 100 Needs work`
- Total diagnostics: `987`
- Summary: `Security 2 warnings`, `Bugs 3 errors + 187 warnings`, `Performance 38 warnings`, `Accessibility 40 warnings`, `Maintainability 717 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9434f942-1a63-49c5-99cf-d8b9d39ab347`

## Batch 52

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-adjust-state-on-prop-change` | `app/(app)/dashboard/components/kpi-card.tsx` | Valid: the sparkline effect synchronously measured and stored container size when the prop-derived `hasData` value changed, creating duplicated dimension state before rendering the chart. | High | Remove the measurement state/effect and let `ResponsiveContainer` fill the existing fixed-height sparkline wrapper. Extended the KPI source guard so it failed on the old effect and required the responsive container sizing. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor reports no issues; full React Doctor errors dropped from `3` to `1`. |

Changed-scope command after Batch 52: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 52: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `64 / 100 Needs work`
- Total diagnostics: `985`
- Summary: `Security 2 warnings`, `Bugs 1 error + 187 warnings`, `Performance 38 warnings`, `Accessibility 40 warnings`, `Maintainability 717 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-15f8a7db-fcf4-4f87-8e86-f691030a97e1`

## Batch 53

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-adjust-state-on-prop-change`, `react-doctor/no-derived-state`, `react-doctor/no-initialize-state` | `app/book/self-service/[orgId]/manage/[token]/page.tsx` | Valid: the manage page copied appointment timezone and appointment month into local state after data arrived, set invalid-link load state from route params in an effect, and initialized browser timezone through a mount effect. | High | Derive invalid-link render state from route params, derive timezone from user override → appointment timezone → browser/default snapshot, derive view month from user navigation override → appointment month, and read browser timezone through `useSyncExternalStore`. Added a source guard and behavior assertion for appointment-timezone slot lookup. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/self-service-manage-page.test.tsx`; full React Doctor errors dropped from `1` to `0`. |
| `react-doctor/react-compiler-no-manual-memoization` | `app/book/self-service/[orgId]/manage/[token]/page.tsx` | Valid: the file still had manual `useCallback`/`useMemo` wrappers around load-state assignment and directly derived option/calendar values. | High | Remove those wrappers while keeping the same rendered data and API calls. Extended the source guard so the wrappers cannot be reintroduced in this page. | Changed-scope React Doctor no longer reports manual memoization for this page. |
| Dropdown label rule | `app/book/self-service/[orgId]/manage/[token]/page.tsx` | Valid: the timezone select stored IANA ids and used a self-closing `SelectValue`, which can leak raw stored values in this project’s shared select. | High | Add `getTimezoneLabel` and render the selected timezone through the same friendly label helper used by the dropdown options. | `pnpm test --run tests/self-service-manage-page.test.tsx` asserts `Eastern Time (US)` is visible for the appointment default. |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/book/self-service/[orgId]/manage/[token]/page.tsx` | Valid but deferred: splitting the 488-line page and consolidating the remaining 11 state fields are broader structural work. | Medium | Logged for a later self-service page refactor instead of mixing a page extraction/reducer redesign into this state-derivation error fix. | Changed-scope React Doctor reports only these two warnings after the derivation cleanup. |

Changed-scope command after Batch 53: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-c00ace4e-0035-44fe-88db-a608edc252ba`

Full command after Batch 53: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `65 / 100 Needs work`
- Total diagnostics: `976`
- Summary: `Security 2 warnings`, `Bugs 182 warnings`, `Performance 38 warnings`, `Accessibility 40 warnings`, `Maintainability 714 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a736f813-211f-4705-a43b-5ffc306d4801`

## Batch 54

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `lib/forms/use-form-builder-document.ts` | Valid: React Compiler is enabled and the hook wrapped derived values and local handlers in `useMemo`/`useCallback` even though they resolve to React APIs. | High | Remove the memoization wrappers and use plain values/functions. Added a source guard that failed on the old `useMemo`/`useCallback` imports and calls. Stable reset handlers use lazy `useState` function initialization; a ref-backed identity workaround was rejected because full React Doctor flagged render-time ref access. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/form-builder-page.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `581` to `543`. |
| `react-doctor/prefer-module-scope-pure-function` | `lib/forms/use-form-builder-document.ts` | Valid: after unwrapping, pure helpers that did not use hook state were rebuilt inside the hook. | High | Move `handleDragOver`, `moveFieldToIndex`, and `insertFieldAtIndex` to module scope. | Full React Doctor no longer reports pure-function rebuilds for `use-form-builder-document.ts`. |

Changed-scope command after Batch 54: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 54: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `65 / 100 Needs work`
- Total diagnostics: `938`
- Summary: `Security 2 warnings`, `Bugs 182 warnings`, `Performance 38 warnings`, `Accessibility 40 warnings`, `Maintainability 676 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-40a01f68-4dfc-4a43-b287-056f19393bfb`

## Batch 55

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `lib/forms/use-template-form-builder-page.ts` | Valid: the template form-builder hook still wrapped draft payloads, handlers, autosave labels, and workspace document props in manual `useMemo`/`useCallback` even though React Compiler can cache them. | High | Remove the wrappers, derive the payload and workspace document directly, and keep autosave behavior stable by debouncing a deterministic payload fingerprint instead of a fresh object. Added a source guard that failed on the old `useMemo`/`useCallback` imports and calls. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/platform-form-template-page.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `543` to `529`. |
| `react-doctor/rerender-lazy-ref-init` | `lib/forms/use-template-form-builder-page.ts` | Valid: `useRef<Promise<void>>(Promise.resolve())` rebuilt a throwaway promise on every render. | High | Initialize the save queue ref with `null` and lazily create the resolved queue inside the module-scope queue helper when a save actually runs. | Full React Doctor no longer reports `rerender-lazy-ref-init` for `use-template-form-builder-page.ts`; performance warnings dropped from `38` to `37`. |

Changed-scope command after Batch 55: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 55: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `65 / 100 Needs work`
- Total diagnostics: `923`
- Summary: `Security 2 warnings`, `Bugs 182 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 662 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7bc3a239-5aed-442d-b2e1-08af751af1db`

## Batch 56

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `lib/forms/use-template-form-builder-state.ts`, `lib/forms/use-automation-form-builder-state.ts` | Valid: both reducer-backed state hooks wrapped stable dispatch helpers in `useCallback`, which is redundant with React Compiler. The returned action identities still need to stay stable because page hooks depend on them from effects. | High | Replace the `useCallback` wrappers with lazy `useState` function initializers that capture React's stable reducer dispatch once. Added a source guard that failed on the old `useCallback` imports and wrappers. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/platform-form-template-page.test.tsx tests/form-builder-page.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `529` to `523`. |

Changed-scope command after Batch 56: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 56: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `65 / 100 Needs work`
- Total diagnostics: `917`
- Summary: `Security 2 warnings`, `Bugs 182 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 656 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ac527b0c-93a4-4dc2-8a52-4b42c51f264b`

## Batch 57

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/dashboard/context/dashboard-filters.tsx` | Valid: the dashboard filter provider wrapped URL sync handlers and the date-parameter getter in `useCallback`; React Compiler can cache these values without manual wrappers. | High | Remove the `useCallback` import and derive the handlers/getter as plain functions while preserving reducer state updates and URL writes. Extended the existing dashboard filter source guard so it failed on the old wrapper import/calls. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/dashboard.test.tsx tests/accessibility-hardening.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `523` to `517`. |

Changed-scope command after Batch 57: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 57: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `65 / 100 Needs work`
- Total diagnostics: `911`
- Summary: `Security 2 warnings`, `Bugs 182 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 650 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7ae5e07e-f4bc-4e8c-a99d-ad05b31e9acd`

## Batch 58

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/dashboard/page.client.tsx`, `app/(app)/dashboard/components/kpi-cards-section.tsx`, `app/(app)/dashboard/components/trend-chart.tsx`, `app/(app)/dashboard/components/stage-chart.tsx` | Valid: dashboard overview and chart components wrapped local derived values and callbacks in `useMemo`/`useCallback` even though React Compiler can cache these values. | High | Remove the wrappers and keep the same direct calculations for dashboard totals, timestamps, chart params, chart data, and refresh/navigation handlers. Added a source guard that failed on the old imports/calls. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/dashboard.test.tsx tests/accessibility-hardening.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `517` to `502`. |

Changed-scope command after Batch 58: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 58: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `65 / 100 Needs work`
- Total diagnostics: `896`
- Summary: `Security 2 warnings`, `Bugs 182 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 635 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9936e2a8-1f68-4501-a247-50da47d3d1bc`

## Batch 59

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `lib/forms/use-automation-form-builder-page.ts` | Valid: the automation form-builder controller wrapped draft payloads, autosave labels, builder document props, and local UI/submission handlers in manual `useMemo`/`useCallback`. | High | Remove the wrappers, derive the controller values directly, and replace object-identity autosave debounce with a deterministic draft fingerprint plus an explicit timeout. Hoisted pure QR/submission helpers to module scope so unwrapping did not introduce new pure-function rebuild warnings. Added a source guard that failed on the old `useMemo`/`useCallback` imports and calls. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/form-builder-page.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `502` to `457`. |

Changed-scope command after Batch 59: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 59: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `65 / 100 Needs work`
- Total diagnostics: `851`
- Summary: `Security 2 warnings`, `Bugs 182 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 590 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a9ea583a-5c62-4b4e-a4e5-60efbd080f56`

## Batch 60

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization`, `react-doctor/prefer-module-scope-pure-function` | `app/(app)/automation/page.client.tsx` | Valid: the automation page manually memoized option arrays and selected workflow lookup, and rebuilt pure server-error/action-validation helpers inside the component. | High | Remove `useMemo`, derive options directly, and hoist the pure helpers to module scope. Added a source guard that failed on the old `useMemo` import/calls and local helper declarations. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/automation-page.test.tsx`; full React Doctor manual memoization count dropped from `457` to `449`; pure-function rebuild count dropped from `33` to `31`. |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/automation/page.client.tsx` | Valid but out of scope: the page remains a 2k-line orchestration surface and still owns several related local UI states. | Medium | Deferred to a separate behavior/refactor batch because splitting the workflow page and grouping the remaining local state changes the component structure more broadly than this memoization cleanup. | Changed-scope React Doctor reports these two remaining warnings with score `92 / 100`; no suppression added. |

Changed-scope command after Batch 60: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Deferred: `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` in `app/(app)/automation/page.client.tsx`

Full command after Batch 60: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `65 / 100 Needs work`
- Total diagnostics: `841`
- Summary: `Security 2 warnings`, `Bugs 182 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 580 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a9f0f47f-fe48-44b0-92c8-623747649fd4`

## Batch 61

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/automation/ai-builder/page.client.tsx` | Valid: the AI builder manually memoized email-template sanitization and variable derivations that React Compiler can cache. | High | Remove `useMemo`, derive the sanitized body, detected variables, allowed variable set, required variable list, missing variables, and unknown variables directly, while preserving the existing single-pass required-variable loop. Added a source guard that failed on the old `useMemo` import/calls. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/ai-builder-page.test.tsx`; changed-scope React Doctor reports no manual memoization warnings; full React Doctor manual memoization count dropped from `449` to `443`. |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/automation/ai-builder/page.client.tsx` | Valid but out of scope: the page remains a large orchestration component with 17 local state hooks. | Medium | Deferred to a separate behavior/refactor batch because splitting the page and grouping generation/template state is broader than the template-derivation cleanup. | Changed-scope React Doctor reports these two remaining warnings with score `92 / 100`; no suppression added. |

Changed-scope command after Batch 61: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Deferred: `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` in `app/(app)/automation/ai-builder/page.client.tsx`

Full command after Batch 61: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `65 / 100 Needs work`
- Total diagnostics: `835`
- Summary: `Security 2 warnings`, `Bugs 182 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 574 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7364dcad-e707-4d97-8876-62de7d1bf9d7`

## Batch 62

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/require-pnpm-hardening` | `pnpm-workspace.yaml`, `pnpm-lock.yaml` | Valid: the frontend workspace had `minimumReleaseAgeExclude` but no active `minimumReleaseAge`, and no `trustPolicy`, leaving newly published or downgraded-trust packages unchecked. Enabling `trustPolicy: no-downgrade` also exposed `semver@6.3.1` as a lockfile trust downgrade through the old Babel override. | High | Add `minimumReleaseAge: 1440` and `trustPolicy: no-downgrade`, move the explicit `@babel/core` override from `7.29.6` to current `8.0.1`, and refresh the lockfile so Babel uses `semver@7`. Verified the keys with `pnpm config get` and verified `pnpm install` passes under the active policy. | `pnpm config get minimumReleaseAge --location project`; `pnpm config get trustPolicy --location project`; `pnpm install`; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; full React Doctor security count dropped from `2` to `0` and score rose from `65` to `66`. |

Changed-scope command after Batch 62: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Result: skipped because this batch changes only `pnpm-workspace.yaml`, not source files.

Full command after Batch 62: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `833`
- Summary: `Bugs 182 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 574 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-df6bf46e-e504-4f47-bebd-7e976cb7b03e`

## Batch 63

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/exhaustive-deps` | `app/(app)/ai-assistant/page.tsx`, `app/(app)/dashboard/components/dashboard-filter-bar.tsx` | False positive after code review: both effects intentionally clean up the latest mutable ref value on unmount. Capturing the ref value from mount time would miss the active stream controller or refresh timeout. | High | Add `oxlint-disable-next-line react-doctor/exhaustive-deps` comments with local evidence for the latest-ref cleanup behavior. Added a source guard that failed while the effects lacked React Doctor rule-name comments. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/dashboard.test.tsx tests/matches-page.test.tsx tests/intended-parents-page.test.tsx tests/surrogates.test.tsx`; changed-scope React Doctor reports no `exhaustive-deps` warnings. |
| `react-doctor/exhaustive-deps` | `app/(app)/intended-parents/matches/page.client.tsx`, `app/(app)/intended-parents/page.client.tsx`, `app/(app)/surrogates/page.client.tsx` | Valid suppression with wrong tool target: these URL hydration effects intentionally depend on normalized `currentQuery` and compare state inside the effect to avoid URL/state feedback loops. ESLint still needs `react-hooks/exhaustive-deps`, while React Doctor needs an Oxlint suppression on the dependency-array line. | High | Keep the ESLint hook suppressions and add `oxlint-disable-line react-doctor/exhaustive-deps` on the dependency-array lines. Added a source guard that rejects invalid ESLint comments for React Doctor rules. | Changed-scope React Doctor reports no `exhaustive-deps` warnings; full React Doctor bug count dropped from `182` to `177`. |
| `react-doctor/react-compiler-no-manual-memoization`, `react-doctor/no-event-handler`, `react-doctor/no-cascading-set-state`, `react-doctor/prefer-module-scope-pure-function`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | Changed files from this batch | Valid but out of scope: these are pre-existing broader memoization, URL synchronization, pure-function, and component-structure findings in the touched files. | Medium | Deferred to separate focused batches because this batch only validated the five exhaustive-deps findings. No suppressions added. | Changed-scope React Doctor score is `82 / 100` with `79` remaining warnings in the touched files. |

Changed-scope command after Batch 63: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `82 / 100 Needs work`
- Total diagnostics in changed files: `79`
- Summary: `Bugs 31 warnings`, `Maintainability 48 warnings`
- Deferred: pre-existing memoization, URL effect, pure-function, giant-component, and reducer findings in the touched files.

Full command after Batch 63: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `828`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 574 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-51fd5311-dbb6-4da1-bb4d-4c03ac0a5b19`

## Batch 64

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization`, `react-doctor/prefer-module-scope-pure-function` | `app/(app)/intended-parents/matches/page.client.tsx` | Valid: the matches list manually memoized local URL handler callbacks, and rebuilt a pure proposed-date formatter inside the page component. | High | Move URL construction and proposed-date formatting to module-scope helpers, remove `useCallback`, and use plain event handlers that call the helpers. Added a source guard that failed on the old `useCallback` import/calls and local date formatter. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/matches-page.test.tsx`; changed-scope React Doctor reports no manual-memoization or pure-function warning for this page; full React Doctor manual memoization count dropped from `443` to `440`, pure-function count dropped from `31` to `30`. |
| `react-doctor/no-event-handler`, `react-doctor/no-cascading-set-state` | `app/(app)/intended-parents/matches/page.client.tsx` | Valid but out of scope: the remaining findings are the existing debounced search and URL hydration effects. Fixing them safely requires a separate state-model refactor that preserves browser navigation, query hydration, and debounced search behavior. | Medium | Deferred to a separate URL-state batch because this batch only targeted compiler-friendly memoization and pure-helper rebuilds. No suppression added. | Changed-scope React Doctor score is `88 / 100` with `6` remaining bug warnings in this page. |

Changed-scope command after Batch 64: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `88 / 100 Great`
- Total diagnostics in changed files: `6`
- Summary: `Bugs 6 warnings`
- Deferred: `react-doctor/no-event-handler`, `react-doctor/no-cascading-set-state` in `app/(app)/intended-parents/matches/page.client.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-3458a492-2fec-4d1e-9560-64350869914c`

Full command after Batch 64: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `823`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 569 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7313039c-0612-4200-87fd-87ee9a5a2a93`

## Batch 65

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization`, `react-doctor/prefer-module-scope-pure-function` | `app/(app)/intended-parents/page.client.tsx` | Valid: the intended-parents list manually memoized local URL handler callbacks, and rebuilt a pure created-date formatter inside the page component. | High | Move URL construction and created-date formatting to module-scope helpers, remove `useCallback`, and use plain event handlers that call the helpers. Added a source guard that failed on the old `useCallback` import/calls and local date formatter. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/intended-parents-page.test.tsx`; changed-scope React Doctor reports no manual-memoization or pure-function warning for this page; full React Doctor manual memoization count dropped from `440` to `435`, pure-function count dropped from `30` to `29`. |
| `react-doctor/no-event-handler`, `react-doctor/no-cascading-set-state`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/intended-parents/page.client.tsx` | Valid but out of scope: the remaining findings are the existing debounced search and URL hydration effects plus page-level state/component size. Fixing them safely requires a separate URL-state reducer and component split that preserves browser navigation, query hydration, and debounced search behavior. | Medium | Deferred to a separate URL-state/page-structure batch because this batch only targeted compiler-friendly memoization and pure-helper rebuilds. No suppression added. | Changed-scope React Doctor score is `88 / 100` with `10` remaining warnings in this page. |

Changed-scope command after Batch 65: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `88 / 100 Great`
- Total diagnostics in changed files: `10`
- Summary: `Bugs 9 warnings`, `Maintainability 1 warning`
- Deferred: `react-doctor/no-event-handler`, `react-doctor/no-cascading-set-state`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` in `app/(app)/intended-parents/page.client.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-cd816704-d5d2-4c5a-b43a-75344cb4cd2b`

Full command after Batch 65: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `817`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 563 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-717899bd-bec7-4a9b-8c73-2e0ec04bad44`

## Batch 66

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/intended-parents/matches/[id]/hooks/useMatchDetailTabState.ts` | Valid: the match-detail tab state hook manually memoized URL construction and tab/source handlers even though React Compiler can cache them. | High | Move match-detail tab URL construction to a module-scope helper, remove `useCallback`, and return plain tab/source change handlers. Added a source guard that failed on the old `useCallback` import/calls and missing helper. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/match-detail.test.tsx tests/match-detail-overview-tabs.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `435` to `432`. |

Changed-scope command after Batch 66: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 66: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `814`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 560 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-377a428d-4d81-4717-a454-51259453f976`

## Batch 67

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/intended-parents/matches/[id]/hooks/useMatchDetailTabData.ts` | Valid: the match-detail tab data hook manually memoized deterministic note, file, task, activity, and source-filter derivations. | High | Move note/file/task builders to module scope, remove `useMemo`, and return plain derived arrays so React Compiler can cache the hook work. Added a source guard that failed on the old `useMemo` import/calls. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/match-detail-tab-data.test.tsx tests/match-detail.test.tsx tests/match-detail-overview-tabs.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `432` to `424`. |

Changed-scope command after Batch 67: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 67: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `806`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 552 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a742f16c-5d20-4dc6-b5b9-368589c97449`

## Batch 68

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/matches/page.tsx` | Valid: the top-level match creation dialog manually memoized deterministic stage-label and eligible-surrogate derivations from hook data. | High | Remove `useMemo` and compute the label and filtered eligible surrogate list directly during render. Added a source guard that failed on the old `useMemo` import/calls, while the existing matches page behavior test covers the eligible-surrogate filtering behavior. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/matches-main-page.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `424` to `422`. |

Changed-scope command after Batch 68: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 68: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `804`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 550 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8f002223-581b-4e12-aa0f-1ee93b421521`

## Batch 69

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/search/page.tsx` | Valid: the search page manually memoized an Escape key handler that only clears local query state. | High | Remove `useCallback` and use the same plain key handler directly. Added a source guard that failed on the old `useCallback` import/call, while the existing search debounce test covers the page query behavior. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/search-debounce.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `422` to `421`. |

Changed-scope command after Batch 69: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 69: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `803`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 549 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-119478a5-3948-4e8b-85f9-bcdc83c102c1`

## Batch 70

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/settings/compliance/page.tsx`, `app/(app)/settings/integrations/meta/forms/[id]/page.tsx`, `app/(app)/settings/team/roles/[role]/page.client.tsx` | Valid: these settings pages manually memoized deterministic maps derived from fetched data or route detail data. | High | Remove `useMemo` from the three derived maps. For compliance, build the initial policy-edit map inside the existing `policies` effect so the effect depends on `policies` rather than an always-new map object. Added a source guard that failed on the old `useMemo` imports/calls. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/meta-form-mapping-page.test.tsx`; changed-scope React Doctor no longer reports manual memoization for these files; full React Doctor manual memoization count dropped from `421` to `418`. |
| `react-doctor/no-cascading-set-state`, `react-doctor/rerender-state-only-in-handlers`, `react-doctor/no-event-handler`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | Same changed settings files | Valid but out of scope: the remaining findings are broader state-model and component-structure concerns in the touched settings pages. Fixing them safely requires reducer/ref or component extraction work beyond this memoization batch. | Medium | Deferred to separate settings state-structure batches. No suppressions added. | Changed-scope React Doctor score is `87 / 100` with `7` remaining warnings in changed files. |

Changed-scope command after Batch 70: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `87 / 100 Great`
- Total diagnostics in changed files: `7`
- Summary: `Bugs 4 warnings`, `Performance 1 warning`, `Maintainability 2 warnings`
- Deferred: settings state-model and component-structure findings listed above.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-40050451-d954-4dc1-9f33-7336bd4fd3fc`

Full command after Batch 70: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `800`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 546 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1f087f8c-301a-40fe-8593-4ab84c944531`

## Batch 71

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization`, `react-doctor/prefer-module-scope-pure-function` | `app/(app)/settings/audit/page.tsx` | Valid: the audit settings page manually memoized deterministic export-job derivations and rebuilt pure export/redaction type guards inside the component. | High | Move the export/redaction/AI activity type guards and constants to module scope, remove `useMemo`, and derive visible export jobs plus pending status directly during render. Added a source guard that failed on the old local helpers and `useMemo` import/calls, while the audit page behavior test covers rendered audit/export behavior. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/audit-log-page.test.tsx`; changed-scope React Doctor no longer reports manual memoization or pure-function warnings for this page; full React Doctor manual memoization count dropped from `418` to `416`, pure-function count dropped from `29` to `27`. |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/settings/audit/page.tsx` | Valid but out of scope: the page remains a large component with several related UI state fields. Fixing that safely should be a separate component-split/reducer batch with behavior coverage for export filters, AI activity filtering, and pagination. | Medium | Deferred to a separate audit page structure batch. No suppression added. | Changed-scope React Doctor score is `92 / 100` with `2` remaining warnings in this page. |

Changed-scope command after Batch 71: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Deferred: `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` in `app/(app)/settings/audit/page.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7cdb9767-4006-44a6-8c77-cd6111556f01`

Full command after Batch 71: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `796`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 542 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-2d89d73a-a91b-4561-ba28-0d7f4fef59be`

## Batch 72

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/settings/integrations/meta/page.client.tsx` | Valid: Meta asset selection manually memoized a deterministic flattening of paginated ad account/page assets from query data. | High | Remove the lone `useMemo` import/call and derive the flattened asset lists directly during render. Added a source guard that failed on the old `useMemo`, while the Meta integrations page test covers asset rendering and conflicting asset overwrite behavior. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/meta-integrations-page.test.tsx`; changed-scope React Doctor no longer reports manual memoization for this page; full React Doctor manual memoization count dropped from `416` to `415`. |
| `react-doctor/prefer-useReducer`, `react-doctor/no-giant-component` | `app/(app)/settings/integrations/meta/page.client.tsx` | Valid but out of scope: the touched Meta integration page still has reducer-worthy local state in asset selection and the top-level page, plus a large page component. Fixing this safely should be a separate state-model/component split batch. | Medium | Deferred to separate Meta integration structure work. No suppression added. | Changed-scope React Doctor score is `92 / 100` with `3` remaining warnings in this page. |

Changed-scope command after Batch 72: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `3`
- Summary: `Bugs 2 warnings`, `Maintainability 1 warning`
- Deferred: `react-doctor/prefer-useReducer`, `react-doctor/no-giant-component` in `app/(app)/settings/integrations/meta/page.client.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-237d4788-e7ce-4d8b-8761-d426e735bff4`

Full command after Batch 72: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `795`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 541 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-13249db6-a5a7-4e71-868d-20f473a5e179`

## Batch 73

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/tickets/page.tsx` | Valid: the tickets list manually memoized deterministic filter params derived from local status, priority, and query state. | High | Remove `useMemo` and derive `TicketListParams` directly during render. Added a source guard that failed on the old `useMemo` import/call. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts`; changed-scope React Doctor no longer reports manual memoization for this page; full React Doctor manual memoization count dropped from `415` to `414`. |
| `react-doctor/prefer-useReducer` | `app/(app)/tickets/page.tsx` | Valid but out of scope: the page still has related status, priority, query, compose-open, compose-subject, and compose-body state fields that React Doctor flags as reducer-worthy. | Medium | Deferred to a separate tickets state-model batch. No suppression added. | Changed-scope React Doctor score is `97 / 100` with `1` remaining warning in this page. |

Changed-scope command after Batch 73: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `97 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Bugs 1 warning`
- Deferred: `react-doctor/prefer-useReducer` in `app/(app)/tickets/page.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-bbfa41e8-1ae9-4ca5-a50e-a2284398b71f`

Full command after Batch 73: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `794`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 540 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9ff9e33a-1507-4610-b4a8-3ff5440eb4d8`

## Batch 74

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/settings/intelligent-suggestions-section.tsx` | Valid: the section imported React `useMemo`/`useCallback` and used them for deterministic stage maps, template maps, stage label helpers, draft builders, and the initial settings loader. React Compiler is enabled in `apps/web/next.config.js`, and the current rule prompt says these wrappers are redundant unless a preserve-manual-memoization case applies. | High | Move pure stage/template/draft helpers to module scope, derive maps directly during render, keep retry loading as a plain handler, and make the initial load effect call a cancellable async loader keyed by pipeline data instead of depending on a memoized callback. Added a source guard that failed on the old `useMemo`/`useCallback` import/calls. | `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run tests/react-regressions-source.test.ts tests/settings-page.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `414` to `405`. |

Changed-scope command after Batch 74: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 74: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `785`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 531 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-6d26159c-ba2d-40a5-b7db-86f8f9887793`

## Batch 75

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/tasks/page.client.tsx` | Valid: the tasks page used `useCallback` around direct URL-sync, filter, selection, and bulk-complete handlers. React Compiler is enabled, and these wrappers do not guard a confirmed preserve-manual-memoization case. | High | Remove the `useCallback` import and convert the affected handlers to plain functions while preserving their existing state updates and mutation flow. Added a source guard that failed on the old `useCallback` import/calls. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/tasks-page.test.tsx`; changed-scope React Doctor no longer reports manual memoization for this page; full React Doctor manual memoization count dropped from `405` to `400`. |
| `react-doctor/no-event-handler`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/tasks/page.client.tsx` | Valid but out of scope: the page still contains event-handler and state-structure findings that need a separate reducer/component-structure batch with focused task workflow coverage. | Medium | Deferred to a separate tasks page structure batch. No suppression added. | Changed-scope React Doctor score is `92 / 100` with `3` remaining warnings in this page. |

Changed-scope command after Batch 75: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `3`
- Summary: `Bugs 2 warnings`, `Maintainability 1 warning`
- Deferred: `react-doctor/no-event-handler`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` in `app/(app)/tasks/page.client.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-bbf0fa81-af21-4d99-8793-362218c6b9dc`

Full command after Batch 75: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `780`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 526 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a4f8e1b0-7439-4789-8687-c8a3c3fcade4`

## Batch 76

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/FileUploadZone.tsx`, `components/ai/AssistantRichText.tsx`, `components/app-link.tsx`, `components/charts/funnel-chart.tsx`, `components/charts/us-map-chart.tsx` | Valid: these shared display/navigation components resolved to React `useCallback`, `React.useCallback`, `useMemo`, or `React.useMemo` wrappers. The current rule docs say to use the plain value, function, or component after confirming no preserve-manual-memoization case applies. | High | Convert the upload drop handler, app-link click handler, assistant markdown derivations, funnel max-count derivation, and US state count map derivation to plain render-local values/functions. Added a source guard that failed on the old wrappers. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/file-upload-zone-accessibility.test.tsx tests/app-link.test.tsx tests/assistant-rich-text.test.tsx`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `400` to `394`. |

Changed-scope command after Batch 76: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 76: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `774`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 40 warnings`, `Maintainability 520 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ee762a5a-a3c7-4c4e-9a20-32216072e1a3`

## Batch 77

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/email/TemplateVariablePicker.tsx`, `components/forms/FormBuilderPalette.tsx`, `components/forms/builder/FieldLibrarySheet.tsx`, `components/forms/builder/FormBuilderCanvasPreview.tsx` | Valid: form-builder palettes, preview derivations, and the template-variable picker used React `useMemo` wrappers around deterministic category, grouping, filtering, schema, and visible-field derivations. No preserve-manual-memoization case applied. | High | Move static category lists to module scope, extract template-variable grouping/filter helpers, and derive preview schema plus visible fields directly in render. Added a source guard that failed on the old wrappers. | `pnpm tsc --noEmit`; `pnpm test --run tests/react-regressions-source.test.ts tests/form-builder-page.test.tsx tests/email-templates-page.test.tsx tests/platform-system-email-template-page.test.tsx tests/platform-system-email-template-new-page.test.tsx`; changed-scope React Doctor no longer reports manual memoization; full React Doctor manual memoization count dropped from `394` to `385`. |
| `react-doctor/prefer-tag-over-role` | `components/forms/FormBuilderPalette.tsx` | Valid: the touched field-category filter wrapper was a generic `div` with static `role="group"`. The rule's generic suggestion was not contextually right, but the element is category navigation. | High | Replace the role-bearing wrapper with native `<nav aria-label="Field categories">` and add a source guard to prevent reintroducing `role="group"`. | Changed-scope React Doctor originally reported `1` accessibility warning after the memoization edits; after the semantic fix it reports no issues. Full React Doctor accessibility warnings dropped from `40` to `39`. |

Changed-scope command after Batch 77: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 77: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `764`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 39 warnings`, `Maintainability 511 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e53aa5b4-f614-4698-854f-a88b42acb9ae`

## Batch 78

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/ai-assistant/page.tsx` | Valid: the AI assistant page used React `useCallback` and `useMemo` wrappers around reducer patch helpers, chat-history helpers, session selection, message update handlers, and current-session derivation. React Compiler is already enabled in `apps/web/next.config.js`, and no preserve-manual-memoization case applied. | High | Move stable chat-history helper logic to module scope where practical, convert remaining handlers and derived values to plain functions/values, and add a source guard that failed on the old wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/ai-assistant.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor no longer reports manual memoization for this page; full React Doctor manual memoization count dropped from `385` to `365`. |
| React Compiler purity diagnostic | `app/(app)/ai-assistant/page.tsx` | Valid: after removing manual wrappers, changed-scope React Doctor surfaced four compiler-blocking direct `Date.now()` calls inside render-created handlers. The linked docs route did not expose a prompt markdown for this internal diagnostic, but the diagnostic text pointed to React's purity rule and the code showed timestamp IDs embedded in handlers. | High | Add module-scope `createTimestampId` and route session/message ID generation through it, including fallback IDs while parsing stored history. | Changed-scope React Doctor dropped the four compiler errors and improved from `82 / 100` to `98 / 100`. |
| `react-doctor/no-giant-component` | `app/(app)/ai-assistant/page.tsx` | Valid but out of scope: `AIAssistantPage` is still a large component after the memoization cleanup. Splitting the chat shell/sidebar/message list is a separate structural refactor with higher review surface. | Medium | Deferred to a separate AI assistant structure batch. No suppression added. | Final changed-scope React Doctor reports only this one warning in the touched file. |

Changed-scope command after Batch 78: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Deferred: `react-doctor/no-giant-component` in `app/(app)/ai-assistant/page.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-29b2176e-a695-4438-b07c-6afa48128ed6`

Full command after Batch 78: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `744`
- Summary: `Bugs 177 warnings`, `Performance 37 warnings`, `Accessibility 39 warnings`, `Maintainability 491 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-32eb0ccf-0db9-4e77-b15d-856e39aa0945`

## Batch 79

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/automation/email-templates/page.tsx` | Valid: the email-template page used `React.useMemo` and `useCallback` around deterministic template validation, preview, test-send, signature dirty-state, and insertion helpers. React Compiler is enabled in `apps/web/next.config.js`, and none of these wrappers matched a preserve-manual-memoization case. | High | Move reusable pure helpers to module scope, derive render-local values directly, and remove the `useCallback` import. Added a source guard that failed on the old wrappers and now rejects `useMemo`/`useCallback` in this page. | `pnpm test --run tests/react-regressions-source.test.ts tests/email-templates-page.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor no longer reports manual memoization in this page; full React Doctor manual memoization count dropped from `365` to `350`. |
| `react-doctor/prefer-module-scope-pure-function` | `app/(app)/automation/email-templates/page.tsx` | Valid: `handleCopySignatureHtml` did not read component state or props and was rebuilt on every render. | High | Move the clipboard helper to module scope and add a source guard to prevent reintroducing the render-local async helper. | Changed-scope React Doctor dropped this warning after the helper move. |
| `react-doctor/control-has-associated-label` | `app/(app)/automation/email-templates/page.tsx` | Valid: the hidden signature photo file input had no accessible name, even though the visible trigger button was named. | High | Add `aria-label="Upload signature photo"` to the file input and extend the existing email-template accessibility test to assert it. | Changed-scope React Doctor dropped the accessibility warning; full React Doctor accessibility warnings dropped from `39` to `38`. |
| `react-doctor/no-cascading-set-state`, `react-doctor/rerender-state-only-in-handlers`, `react-doctor/no-event-handler`, `react-doctor/no-giant-component`, `react-doctor/prefer-explicit-variants`, `react-doctor/no-many-boolean-props`, `react-doctor/prefer-useReducer` | `app/(app)/automation/email-templates/page.tsx` | Valid but out of scope: the remaining email-template findings are state-model and component-structure refactors around modal open/reset flow, signature hydration, `templateBodyModeTouched`, and boolean-heavy component APIs. | Medium | Deferred to a separate email-template state/component-structure batch. No suppression added. | Final changed-scope React Doctor reports `15` remaining warnings in this page and no manual memoization, pure-helper, or accessibility finding from this batch. |

Changed-scope command after Batch 79: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `86 / 100 Great`
- Total diagnostics in changed files: `15`
- Summary: `Bugs 7 warnings`, `Performance 5 warnings`, `Maintainability 3 warnings`
- Deferred: state-model and component-structure warnings in `app/(app)/automation/email-templates/page.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-d328f106-6e75-4b42-9287-f4e93212aa92`

Full command after Batch 79: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `724`
- Summary: `Bugs 176 warnings`, `Performance 37 warnings`, `Accessibility 38 warnings`, `Maintainability 473 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-714f1b9b-74b2-4a64-ab89-03dea849ab0e`

## Batch 80

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/settings/pipelines/page.tsx` | Valid: the pipelines settings editor wrapped draft construction, draft fingerprints, change detection, preview payload construction, and preview fingerprinting in `useMemo`. The underlying helpers are module-scope pure builders and React Compiler is enabled. | High | Remove the `useMemo` import and derive the draft state, fingerprints, change flag, and preview payload directly. Extended the existing source guard so it failed on the old `useMemo` wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/pipelines-settings-page.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor no longer reports manual memoization in this page; full React Doctor manual memoization count dropped from `350` to `344`. |
| `react-doctor/no-many-boolean-props` | `app/(app)/settings/pipelines/page.tsx` | Valid but out of scope: `DraftActionsCard` still takes four boolean props for saving, preview loading, validation, and blocking-issue state. Splitting that API into named variants is a separate component-shape refactor. | Medium | Deferred to a future pipelines component API batch. No suppression added. | Final changed-scope React Doctor reports only this one warning in the touched file. |

Changed-scope command after Batch 80: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Deferred: `react-doctor/no-many-boolean-props` in `app/(app)/settings/pipelines/page.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-929c392b-c9d4-449e-8774-0c7314d1f705`

Full command after Batch 80: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `718`
- Summary: `Bugs 176 warnings`, `Performance 37 warnings`, `Accessibility 38 warnings`, `Maintainability 467 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-622a3907-993d-4d2c-b6ab-045b7e94a500`

## Batch 81

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/embed/forms/[slug]/page.client.tsx` | Valid: the public embed client wrapped parent messaging, session creation, visible-field derivation, and renderable-field derivation in `React.useCallback`/`React.useMemo`. React Compiler is enabled, and these wrappers were not protecting a preserve-manual-memoization case. | High | Move parent postMessage and embed-session creation helpers to module scope, derive visible and renderable fields directly in render, and extend the source guard so it failed on the old manual memoization. | `pnpm test --run tests/react-regressions-source.test.ts tests/forms-embed.test.tsx`; `pnpm tsc --noEmit`; scoped React Doctor for `app/embed/forms/[slug]` no longer reports manual memoization; full React Doctor manual memoization count dropped from `344` to `340`. |
| `react-doctor/prefer-useReducer` | `app/embed/forms/[slug]/page.client.tsx` | Valid: form load state, session state, answers, date-picker state, submit state, submitted state, and errors were maintained through several related `useState` calls in one workflow. | High | Group the embed form state in `embedFormReducer`, keep duplicate-session guards in refs, and pass a reducer-backed date-picker setter to `PublicFormFieldRenderer`. Added a source guard that failed before the reducer and existing embed behavior tests cover load, session creation, sanitized attribution, validation, submit, lifecycle messages, and duplicate-session prevention. | Scoped React Doctor for `app/embed/forms/[slug]` reports `100 / 100` with no issues; changed-scope React Doctor reports `100 / 100` with no issues. |

Changed-scope command after Batch 81: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 81: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `713`
- Summary: `Bugs 175 warnings`, `Performance 37 warnings`, `Accessibility 38 warnings`, `Maintainability 463 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-12fb686e-138b-4b21-9068-fae4aa21f88c`

## Batch 82

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/intake/[slug]/page.client.tsx` | Valid: the hosted intake client wrapped draft autosave and resume handlers in `React.useCallback`, and kept validation/visibility helpers inside the component. React Compiler is enabled, and none of these wrappers matched a preserve-manual-memoization case. | High | Move draft emptiness, visibility, validation, persistence, and save helpers to module scope; replace callback wrappers with plain handlers; and extend the source guard so it failed on the old wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/forms-shared-intake.test.tsx`; `pnpm tsc --noEmit`; scoped React Doctor no longer reports manual memoization in this page; full React Doctor manual memoization count dropped from `340` to `335`. |
| `react-doctor/control-has-associated-label` | `app/intake/[slug]/page.client.tsx` | Valid: the hidden file input had no accessible name, even though the visible upload trigger was named. | High | Add `aria-label="Select files to upload"` to the hidden input and assert the file input is label-queryable in the hosted intake test. | Scoped React Doctor dropped the file-input label warning. |
| `react-doctor/prefer-tag-over-role` | `app/intake/[slug]/page.client.tsx` | Valid: the progress indicator used `role="progressbar"` instead of a native tag, and the upload drop zone used a `div` with button role and keyboard handling. | High | Replace the custom progress role with native `<progress>` and replace the upload drop zone with a native `button`. Updated the test to assert the native progress element, value, and max. | Scoped React Doctor dropped both `prefer-tag-over-role` warnings. |
| `react-doctor/rerender-lazy-ref-init` | `app/intake/[slug]/page.client.tsx` | Valid: resume lookup refs were initialized with `new Set()` and `new Map()` during render. A first fix introduced render-time ref reads, which React Doctor correctly flagged. | High | Initialize those refs with `null` and lazily create the `Set`/`Map` only inside effects and event handlers. Added a source guard against render-time `new Set()`/`new Map()` ref initialization. | Scoped React Doctor no longer reports lazy ref init or ref-access-during-render findings. |
| `react-doctor/js-set-map-lookups` | `app/intake/[slug]/page.client.tsx` | Low-impact rule-shape finding: the reported lines were string identity heuristics using `.includes`, not repeated `Set`/`Map` membership checks. | Medium | Extract the identity heuristics into named module-scope helpers, which made the scanner warning disappear and improved readability without changing matching semantics. No suppression added. | Scoped React Doctor no longer reports these lookup warnings. |
| `react-doctor/prefer-module-scope-pure-function` | `app/intake/[slug]/page.client.tsx` | Valid: draft save and validation helpers did not require component-local closures once their inputs were explicit. | High | Move pure helpers to module scope with explicit parameters. | Scoped React Doctor dropped the pure-function warnings from this page. |
| `react-doctor/no-event-handler`, `react-doctor/prefer-useReducer`, `react-doctor/no-giant-component` | `app/intake/[slug]/page.client.tsx` | Valid but out of scope: the remaining hosted-intake warnings are tied to the initial draft-session state shape, many related `useState` calls, and the large page component. | Medium | Deferred to a separate intake state-machine/component split batch. This batch partially reduced the draft-session issue by removing setter-driven render state writes, but did not change the whole page state model. No suppression added. | Final scoped and changed-scope React Doctor still report these remaining hosted-intake warnings. |
| `react-doctor/async-defer-await` | `app/intake/[slug]/page.client.tsx` | Low-confidence/likely invalid for this flow: the stale response guard intentionally runs after the awaited lookup so older async responses cannot update the current prompt. Moving that check before `await` would not protect against stale responses. | Medium | Kept the post-await sequence guard and documented the rationale. No suppression added. | Scoped React Doctor still reports this warning; behavior tests continue to pass. |

Scoped command after Batch 82: `cd apps/web && npx react-doctor@latest 'app/intake/[slug]' --verbose`

- Score: `79 / 100 Needs work`
- Total diagnostics in scope: `5`
- Remaining: `react-doctor/no-event-handler` ×2, `react-doctor/async-defer-await`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1b7c439f-0fcf-4c5a-8b09-0d69571fcf30`

Changed-scope command after Batch 82: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `90 / 100 Great`
- Total diagnostics in changed files: `5`
- Remaining: same hosted-intake warnings listed above
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a4c51428-3aa0-4061-aa10-553b528e7bed`

Full command after Batch 82: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `690`
- Summary: `Bugs 175 warnings`, `Performance 24 warnings`, `Accessibility 35 warnings`, `Maintainability 456 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-0eda7c3e-f3ad-4f9e-85b8-5d17d0916e37`

## Batch 83

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/email/EmailAttachmentsPanel.tsx` | Valid: the panel wrapped selected attachment IDs, filtered attachments, totals, blocking state, constraint errors, selection toggling, upload, file-picker, and input-change handlers in `React.useMemo`/`React.useCallback`. React Compiler is enabled, and these wrappers were deterministic render-local derivations or ordinary handlers. | High | Replace memo wrappers with plain render-local values/functions and add a source guard that failed on the old wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/email-attachments-panel.test.tsx`; `pnpm tsc --noEmit`; scoped `components/email` React Doctor no longer reports any `EmailAttachmentsPanel` manual memoization findings; full React Doctor manual memoization count dropped from `335` to `326`. |
| `react-doctor/control-has-associated-label` | `components/email/EmailAttachmentsPanel.tsx` | Valid: the visually hidden email attachment file input used only the generic section label, which did not describe the upload control clearly. | High | Add `aria-label="Choose email attachments to upload"` to the file input and update the upload behavior test to query that label before firing the change event. | Scoped `components/email` React Doctor dropped this accessibility warning; full React Doctor accessibility warnings dropped from `35` to `34`. |
| `react-doctor/react-compiler-no-manual-memoization`, `react-doctor/prefer-tag-over-role` | `components/email/EmailComposeDialog.tsx` | Valid but out of scope: the remaining email-component findings are in the compose dialog, not the attachments panel. | High | Deferred to a separate compose-dialog batch to keep this commit focused and easy to review. No suppression added. | Final `components/email` React Doctor reports `19` remaining warnings, all in `EmailComposeDialog.tsx`. |

Scoped command after Batch 83: `cd apps/web && npx react-doctor@latest components/email --verbose`

- Score: `83 / 100 Needs work`
- Total diagnostics in scope: `19`
- Remaining: `EmailComposeDialog.tsx` manual memoization ×18 and `prefer-tag-over-role` ×1
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e56e924e-bd0d-425b-9711-594caba36de4`

Changed-scope command after Batch 83: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 83: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `680`
- Summary: `Bugs 175 warnings`, `Performance 24 warnings`, `Accessibility 34 warnings`, `Maintainability 447 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-f2e5065c-b6b3-4719-adca-8bd19e3861fb`

## Batch 84

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/email/EmailComposeDialog.tsx` | Valid: the compose dialog wrapped preview variables, unresolved-variable checks, preview HTML, footer HTML, template labels, and ordinary event handlers in `React.useMemo`/`React.useCallback`. React Compiler is enabled, and none of these wrappers matched a preserve-manual-memoization case. | High | Replace memo wrappers with plain render-local values/functions and add a source guard that failed on the old wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/email-compose-dialog.test.tsx`; `pnpm tsc --noEmit`; scoped `components/email` React Doctor no longer reports manual memoization in `EmailComposeDialog.tsx`; full React Doctor manual memoization count dropped from `326` to `308`. |
| React Compiler purity diagnostic | `components/email/EmailComposeDialog.tsx` | Valid: after removing callback wrappers, React Doctor surfaced compiler-blocking `Date.now()` and `Math.random()` calls in the render-local send handler fallback path. | High | Move idempotency-key generation into a module-scope helper so the render-local handler does not embed non-deterministic calls. | Changed-scope React Doctor dropped the compiler purity warning after the helper extraction. |
| `react-doctor/js-length-check-first` | `components/email/EmailComposeDialog.tsx` | Valid: the new reducer no-op guard compared selected attachment arrays without the scanner-preferred explicit length check first. | High | Compare lengths before the element-wise equality check. | Changed-scope React Doctor dropped the array-comparison warning after the guard rewrite. |
| `react-doctor/prefer-tag-over-role` | `components/email/EmailComposeDialog.tsx` | Low-confidence/likely invalid for this flow: `MessagePreview` is a content-editable rich HTML preview editor with `role="textbox"`, `aria-label`, `aria-labelledby`, and `aria-multiline`. Replacing it with `<input>` would break HTML preview editing, and `<textarea>` would show markup rather than the editable preview. | Medium | Kept the role-bearing contentEditable editor and documented the rationale. No suppression added. | Changed-scope React Doctor still reports this one warning; existing compose-dialog tests cover preview editing and sending edited preview content. |

Scoped command after Batch 84: `cd apps/web && npx react-doctor@latest components/email --verbose`

- Score: `91 / 100 Great`
- Total diagnostics in scope: `1`
- Remaining: `prefer-tag-over-role` in `EmailComposeDialog.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-5867f2fc-42a2-4a3d-a5bf-47d7df7df0ab`

Changed-scope command after Batch 84: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `97 / 100 Great`
- Total diagnostics in changed files: `1`
- Remaining: `prefer-tag-over-role` in `EmailComposeDialog.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9dcb13e1-3f69-4ab1-91e0-32a92d1e3faa`

Full command after Batch 84: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `662`
- Summary: `Bugs 175 warnings`, `Performance 24 warnings`, `Accessibility 34 warnings`, `Maintainability 429 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-f1e76770-d521-4eec-9c93-825a9b36266a`

## Batch 85

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/(app)/surrogates/page.client.tsx` | Valid: the surrogates list page wrapped URL-sync, filter, pagination, reset, and active-filter helpers in `useCallback`. React Compiler is enabled, and these handlers are ordinary render-local functions. | High | Remove the `useCallback` import and convert the affected helpers to plain functions. Added a source guard that failed on the old `useCallback` import/calls. | `pnpm test --run tests/react-regressions-source.test.ts tests/surrogates.test.tsx tests/surrogates-accessibility.test.tsx`; `pnpm tsc --noEmit`; scoped React Doctor no longer reports manual memoization for the surrogates page; full React Doctor manual memoization count dropped from `308` to `294`. |
| `react-doctor/no-effect-with-fresh-deps` / `react-doctor/exhaustive-deps` | `app/(app)/surrogates/page.client.tsx` | Valid follow-up: after removing `useCallback`, the debounced-search URL-sync effect depended on the newly render-local `updateUrlParams` function, which recreated every render. | High | Extract URL construction into module-scope `buildSurrogatesFilterUrl` and make the effect depend on stable primitive inputs plus `replace`, not the render-local helper. | Scoped and changed-scope React Doctor dropped the fresh-dependency error. |
| `react-doctor/no-cascading-set-state`, `react-doctor/no-event-handler`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/surrogates/page.client.tsx` | Valid but out of scope: the remaining findings are the page's URL-to-state synchronization effect and broad state/component structure. Fixing them requires a reducer/state-model batch rather than a memoization cleanup. | Medium | Deferred to a separate surrogates state-model/component-structure batch. No suppression added. | Final scoped React Doctor reports `17` remaining warnings in this page and no manual memoization or fresh-dependency error. |

Scoped command after Batch 85: `cd apps/web && npx react-doctor@latest 'app/(app)/surrogates' --verbose`

- Score: `71 / 100 Needs work`
- Total diagnostics in scope: `17`
- Remaining: `no-cascading-set-state`, `no-event-handler` ×14, `no-giant-component`, `prefer-useReducer`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-adbd3b03-32b8-469d-a50d-7b3d4334257d`

Changed-scope command after Batch 85: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `88 / 100 Great`
- Total diagnostics in changed files: `17`
- Remaining: same surrogates page state/component-structure warnings listed above
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1a600895-884c-4ff4-87ba-ecece29254ff`

Full command after Batch 85: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `648`
- Summary: `Bugs 175 warnings`, `Performance 24 warnings`, `Accessibility 34 warnings`, `Maintainability 415 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-3f3cab4d-c74c-403d-986e-47fec8fc94ff`

## Batch 86

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/ops/templates/email/[id]/page.client.tsx` | Valid: the platform email-template editor wrapped deterministic variable sets, validation helpers, preview HTML, reducer dispatch helpers, text insertion helpers, and ordinary save/publish/test/delete handlers in `useMemo`/`useCallback`. React Compiler is enabled, and these wrappers did not preserve an identity-sensitive contract. | High | Remove `useMemo`/`useCallback`, convert the derived values and handlers to plain render-local values/functions, and add a source guard that failed on the previous wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/platform-email-template-page.test.tsx`; `pnpm tsc --noEmit`; scoped and changed-scope React Doctor report no issues; full React Doctor manual memoization count dropped from `294` to `266`. |
| `react-doctor/prefer-module-scope-pure-function` | `app/ops/templates/email/[id]/page.client.tsx` | Valid follow-up: after unwrapping callbacks, React Doctor correctly identified the text insertion helper as a pure function rebuilt inside the controller on every render. | High | Move `applyTextInsertion` to module scope while keeping its ref/value/commit dependencies explicit parameters. | Scoped React Doctor for the email-template editor improved from `96 / 100` with one helper warning to `100 / 100` with no issues. |

Scoped command after Batch 86: `cd apps/web && npx react-doctor@latest 'app/ops/templates/email/[id]' --verbose`

- Score: `100 / 100 Great`
- Total diagnostics in scope: `0`
- Summary: `No issues found`

Changed-scope command after Batch 86: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 86: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `620`
- Summary: `Bugs 175 warnings`, `Performance 24 warnings`, `Accessibility 34 warnings`, `Maintainability 387 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-06570955-c15b-4904-869b-4cee9398a426`

## Batch 87

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/reports/MetaSpendDashboard.tsx`, `components/reports/TeamPerformanceChart.tsx`, `components/reports/TeamPerformanceTable.tsx` | Valid: the report components wrapped deterministic query params, chart series, sorted rows, mobile summaries, and average calculations in `useMemo`. React Compiler is enabled, and none of these wrappers guarded an identity-sensitive contract. | High | Replace the memo wrappers with plain derived values and add a source guard that failed against the previous `useMemo` imports/usages. | `pnpm test --run tests/react-regressions-source.test.ts tests/team-performance-table.test.tsx`; `pnpm tsc --noEmit`; scoped React Doctor no longer reports manual memoization in `components/reports`; full React Doctor manual memoization count dropped from `266` to `258`. |
| `react-doctor/prefer-module-scope-pure-function` | `components/reports/TeamPerformanceTable.tsx` | Valid: `formatDays`, `formatPercent`, and `conversionBadgeClass` do not depend on render-local state and were rebuilt every render. | High | Move those helpers to module scope. | Scoped React Doctor no longer reports pure-function warnings in the reports scope. |
| `react-doctor/prefer-tag-over-role` | `components/reports/TeamPerformanceTable.tsx` | Valid: the mobile summary used `role="list"` on a generic container even though native list markup could preserve the same presentation and label. | High | Replace the role-bearing container with `<ul>`/`<li>` while preserving the existing `aria-label` and article labels. | Focused table tests still pass; scoped React Doctor no longer reports the role warning. |
| `react-doctor/no-giant-component` | `components/reports/TeamPerformanceTable.tsx` | Valid but out of scope: splitting the table into smaller sections is a structural component refactor, separate from this compiler/accessibility cleanup. | Medium | Deferred to a dedicated report table decomposition batch. No suppression added. | Final scoped React Doctor reports one remaining warning: `TeamPerformanceTable` is still a large component. |

Scoped command after Batch 87: `cd apps/web && npx react-doctor@latest components/reports --verbose`

- Score: `96 / 100 Great`
- Total diagnostics in scope: `1`
- Remaining: `no-giant-component` in `TeamPerformanceTable.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-198eef04-8221-4c78-868d-dc9ced79b374`

Changed-scope command after Batch 87: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Remaining: `no-giant-component` in `components/reports/TeamPerformanceTable.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-955797dc-e66b-4f8c-80ce-2bf66fb8c43a`

Full command after Batch 87: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `608`
- Summary: `Bugs 175 warnings`, `Performance 24 warnings`, `Accessibility 33 warnings`, `Maintainability 376 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-718293b5-ac7b-45b2-a728-7e017d501a36`

## Batch 88

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/ops/templates/PublishDialog.tsx` | Valid: the publish dialog wrapped filtered org lists and selected-id lookup state in `useMemo`, but React Compiler is enabled and these are ordinary render-local derivations. | High | Remove `useMemo` and compute organizations, filtered organizations, and selected IDs as plain derived values. Added a source guard that failed on the old wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/publish-dialog.test.tsx`; `pnpm tsc --noEmit`; scoped React Doctor reports no issues; full React Doctor manual memoization count dropped from `258` to `255`. |
| `react-doctor/no-cascading-set-state` | `components/ops/templates/PublishDialog.tsx` | Valid: the open-reset effect set mode, selected org IDs, and search through three separate state setters. | High | Consolidate publish dialog state into one state object and reset it with a single transition update. Added a component test covering reopen reset behavior for mode, search, and selected org IDs. | Scoped and changed-scope React Doctor no longer report the cascading state warning; full React Doctor `Multiple setState calls in one effect` count dropped from `14` to `13`. |

Scoped command after Batch 88: `cd apps/web && npx react-doctor@latest components/ops/templates --verbose`

- Score: `100 / 100 Great`
- Total diagnostics in scope: `0`
- Summary: `No issues found`

Changed-scope command after Batch 88: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 88: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `604`
- Summary: `Bugs 174 warnings`, `Performance 24 warnings`, `Accessibility 33 warnings`, `Maintainability 373 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-62c5321c-60ba-4dfc-a5f7-1684c9f33a62`

## Batch 89

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/ops/templates/page.client.tsx` | Valid: the templates landing page wrapped the query result arrays in `useMemo`, but each wrapper returned the same array unchanged and React Compiler already caches these render-local derivations. | High | Remove the redundant `useMemo` import and derive the email, form, workflow, and system template rows directly. Added a source guard that failed on the previous wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/ops-templates-studio-page.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `255` to `251`. |

Scoped command after Batch 89: `cd apps/web && npx react-doctor@latest app/ops/templates --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics in scope: `20`
- Remaining: workflow editor manual memoization/helper warnings plus deferred system-template structural warnings.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-d4e51be7-3fad-456f-8da6-024ee374160e`

Changed-scope command after Batch 89: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 89: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `66 / 100 Needs work`
- Total diagnostics: `600`
- Summary: `Bugs 174 warnings`, `Performance 24 warnings`, `Accessibility 33 warnings`, `Maintainability 369 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-fb4deda9-3c9b-4966-a41a-63810f856934`

## Batch 90

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/app-sidebar.tsx`, `components/search-command.tsx` | Valid: the sidebar wrapped permission/navigation derivations and dispatch handlers in `useMemo`/`useCallback`, and the search dialog wrapped its select handler in `useCallback`. React Compiler is enabled and these values do not provide an identity-sensitive API contract. | High | Remove the redundant wrappers and keep the sidebar/search handlers as plain render-local functions. Added source guards that failed on the previous wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/app-sidebar-permissions.test.tsx tests/search-debounce.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `251` to `244`. |
| `react-doctor/prefer-use-effect-event`, `react-doctor/no-reset-all-state-on-prop-change`, `react-doctor/no-event-handler` | `components/search-command.tsx` | Valid follow-up: once the sidebar passed a plain hotkey callback, the hotkey listener needed to stop depending on callback identity, and the dialog query reset was still effect-driven from `open`. | High | Use `useEffectEvent` inside `useSearchHotkey`, and key an inner search dialog component on `open` so close/open resets local query state without an effect. | Changed-scope React Doctor improved from `91 / 100` with two search-command warnings to `100 / 100` with no issues. |

Changed-scope command after Batch 90: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 90: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `67 / 100 Needs work`
- Total diagnostics: `591`
- Summary: `Bugs 172 warnings`, `Performance 24 warnings`, `Accessibility 33 warnings`, `Maintainability 362 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7d0c5afd-e720-4275-80ca-dbb6f291d1e0`

## Batch 91

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/automation/workflow-templates-panel.tsx` | Valid: `publishedForms` was a simple filtered render-local derivation wrapped in `useMemo`, and React Compiler is enabled for this app. | High | Replace the memo wrapper with a plain derived array and add a source guard that failed against the previous wrapper/import. | `pnpm test --run tests/react-regressions-source.test.ts tests/templates-page.test.tsx`; `pnpm tsc --noEmit`; scoped React Doctor no longer reports manual memoization in `components/automation`; full React Doctor manual memoization count dropped from `244` to `243`. |
| `react-doctor/no-event-handler` | `components/automation/workflow-templates-panel.tsx` | Valid: a `useEffect` corrected non-admin workflow scope back to `personal`, creating an effect-driven event path for state that can be derived from current permissions. | High | Keep the admin-selectable value in `selectedWorkflowScope`, derive the effective `workflowScope` as `personal` for non-admin users, and remove the effect and transition import. | Scoped and changed-scope React Doctor no longer report the event-handler warning. |
| `react-doctor/control-has-associated-label` | `components/automation/workflow-templates-panel.tsx` | Valid scanner finding: the checkbox had a neighboring visible `Label`, but the rule still reported no accessible label for the native control. | Medium | Add an explicit `aria-label` matching the visible label while preserving the visible `Label`/`htmlFor` association. | Scoped React Doctor no longer reports the checkbox label warning; full React Doctor accessibility count dropped from `33` to `32`. |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `components/automation/workflow-templates-panel.tsx` | Valid but out of scope: the panel remains a 453-line component with five related state hooks. Splitting the dialog/card sections and consolidating workflow form state should be handled as a dedicated component-decomposition batch. | Medium | Deferred. No suppression added. | Final scoped React Doctor reports only these two remaining warnings. |

Scoped command after Batch 91: `cd apps/web && npx react-doctor@latest components/automation --verbose`

- Score: `86 / 100 Great`
- Total diagnostics in scope: `2`
- Remaining: `no-giant-component` and `prefer-useReducer` in `WorkflowTemplatesPanel`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-3a182bb7-382b-49e5-9acb-8c2b76323a88`

Changed-scope command after Batch 91: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Remaining: `no-giant-component` and `prefer-useReducer` in `components/automation/workflow-templates-panel.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-0df68c22-3c63-423b-81cd-a452111fcf46`

Full command after Batch 91: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `67 / 100 Needs work`
- Total diagnostics: `588`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 32 warnings`, `Maintainability 361 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ac26defc-c7b4-4377-89c0-554e910ba699`

## Batch 92

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/matches/ProposeMatchFromIPDialog.tsx` | Valid: `eligibleStageLabel` and `eligibleSurrogates` were ordinary render-local derivations wrapped in `useMemo`, and React Compiler is enabled. | High | Remove the `useMemo` import and compute the label and filtered surrogate list directly. Added a source guard that failed on the previous wrappers. | `pnpm test --run tests/react-regressions-source.test.ts`; `pnpm tsc --noEmit`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `243` to `241`. |

Scoped command after Batch 92: `cd apps/web && npx react-doctor@latest components/matches --verbose`

- Score: `81 / 100 Needs work`
- Total diagnostics in scope: `12`
- Remaining: `10` `MatchTasksCalendar` manual memoization warnings plus `UploadFileDialog` label/helper warnings.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-70f19dbe-80c1-4052-bd71-308447afd23f`

Changed-scope command after Batch 92: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 92: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `67 / 100 Needs work`
- Total diagnostics: `586`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 32 warnings`, `Maintainability 359 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-48a80e39-dbe2-47a6-811a-430b24fbb866`

## Batch 93

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-module-scope-pure-function` | `components/matches/UploadFileDialog.tsx` | Valid: `formatFileSize` does not depend on component-local state or props and was rebuilt on every render. | High | Move `formatFileSize` to module scope and add a source guard that failed while it was render-local. | `pnpm test --run tests/react-regressions-source.test.ts tests/upload-file-dialog.test.tsx`; `pnpm tsc --noEmit`; scoped React Doctor no longer reports the helper warning; full React Doctor pure-function count dropped from `19` to `18`. |
| `react-doctor/control-has-associated-label` | `components/matches/UploadFileDialog.tsx` | Valid scanner finding: the hidden file input was associated with a visible `Label`, but React Doctor still reported the control as unlabeled. | Medium | Add an explicit `aria-label` to the file input while preserving the visible `Label`/`htmlFor` link. | Scoped React Doctor no longer reports the upload dialog label warning; full React Doctor accessibility count dropped from `32` to `31`. |

Scoped command after Batch 93: `cd apps/web && npx react-doctor@latest components/matches --verbose`

- Score: `83 / 100 Needs work`
- Total diagnostics in scope: `10`
- Remaining: `10` `MatchTasksCalendar` manual memoization warnings.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-b418e6e9-f8a7-4539-8cea-8f30db19db52`

Changed-scope command after Batch 93: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 93: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `67 / 100 Needs work`
- Total diagnostics: `584`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 31 warnings`, `Maintainability 358 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-629db53c-d7ae-4505-a550-71b1de71bf96`

## Batch 94

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/matches/MatchTasksCalendar.tsx` | Valid: the month/week/day views and top-level calendar wrapped date windows, grouped task/appointment maps, day filters, and combined task lists in `useMemo`. These are render-local derivations and React Compiler is enabled. | High | Remove the `useMemo` import and compute the same date windows, grouped maps, filtered arrays, and task source map directly. Added a source guard that failed against the previous wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/match-tasks-calendar.test.tsx`; `pnpm tsc --noEmit`; scoped and changed-scope React Doctor report no issues; full React Doctor manual memoization count dropped from `241` to `231`. |

Scoped command after Batch 94: `cd apps/web && npx react-doctor@latest components/matches --verbose`

- Score: `100 / 100 Great`
- Total diagnostics in scope: `0`
- Summary: `No issues found`

Changed-scope command after Batch 94: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 94: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `67 / 100 Needs work`
- Total diagnostics: `574`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 31 warnings`, `Maintainability 348 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-55348d9c-56c4-473e-a787-89ddab7093aa`

## Batch 95

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/import/CSVUpload.tsx` | Valid: drag/file/drop handlers were wrapped in `useCallback`, but React Compiler is enabled and no downstream API depends on their stable identity. | High | Remove `useCallback` and keep the handlers as plain render-local functions. Added a source guard that failed on the previous import/wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/import-page.test.tsx`; `pnpm tsc --noEmit`; scoped React Doctor no longer reports manual memoization in `components/import`; full React Doctor manual memoization count dropped from `231` to `227`. |
| `react-doctor/prefer-module-scope-pure-function` | `components/import/CSVUpload.tsx` | Valid: `resolveErrorDetail` uses only its arguments and was rebuilt on every render. | High | Move `resolveErrorDetail` to module scope. | Scoped React Doctor no longer reports the helper warning; full React Doctor pure-function count dropped from `18` to `17`. |
| `react-doctor/prefer-tag-over-role`, `react-doctor/control-has-associated-label` | `components/import/CSVUpload.tsx` | Valid: the dropzone was a clickable generic container with `role="button"` and the hidden file input was flagged as unlabeled. | High | Use a native `<button type="button">` for the dropzone, move the hidden file input to a sibling, and add an explicit `aria-label` to the input. | Scoped React Doctor no longer reports the tag/label warnings; full React Doctor accessibility count dropped from `31` to `29`. |
| `react-doctor/no-giant-component` | `components/import/CSVUpload.tsx` | Valid but out of scope: `CSVUpload` remains a 934-line import workflow component, and splitting it into upload, mapping, preview, and approval sections is a larger refactor than this compiler/accessibility cleanup. | Medium | Deferred. No suppression added. | Final scoped React Doctor reports only the large-component warning. |

Scoped command after Batch 95: `cd apps/web && npx react-doctor@latest components/import --verbose`

- Score: `96 / 100 Great`
- Total diagnostics in scope: `1`
- Remaining: `no-giant-component` in `CSVUpload`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7e298ee1-397f-4684-8b69-a0d8da4d8397`

Changed-scope command after Batch 95: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Remaining: `no-giant-component` in `components/import/CSVUpload.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-586eccb5-9df1-404f-b958-88c83cab239c`

Full command after Batch 95: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `67 / 100 Needs work`
- Total diagnostics: `567`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 29 warnings`, `Maintainability 343 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-94ae2bd1-3335-4bfb-ad83-92462a16fbb0`

## Batch 96

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/inline-date-field.tsx` | Valid: display label formatting and selected edit date parsing were ordinary render-local derivations wrapped in `useMemo`, and React Compiler is enabled. | High | Compute both values directly during render and add a source guard that failed against the previous `React.useMemo` wrappers. | `pnpm test --run tests/react-regressions-source.test.ts tests/inline-fields-accessibility.test.tsx tests/surrogates-accessibility.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor reports no issues; full React Doctor manual memoization count dropped from `227` to `225`. |
| `react-doctor/prefer-tag-over-role` | `components/inline-date-field.tsx` | Valid: the non-editing date display is an actionable edit trigger and was implemented as a generic element with `role="button"`. | High | Replace the display trigger with a native `<button type="button">`, preserving disabled behavior and the existing accessible name. | Focused accessibility tests pass, changed-scope React Doctor reports no issues, and full React Doctor accessibility count dropped from `29` to `28`. |

Changed-scope command after Batch 96: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 96: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `67 / 100 Needs work`
- Total diagnostics: `564`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 28 warnings`, `Maintainability 341 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-c13a626b-c887-49da-9989-9993a99b6a30`

## Batch 97

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/control-has-associated-label` | `components/forms/builder/AutomationFormSettingsPanel.tsx`, `components/surrogates/interviews/InterviewTab/AttachmentsDialog.tsx` | Valid: both hidden file inputs were activated by visible upload buttons but had no accessible name of their own. | High | Add explicit `aria-label` values to the form logo upload and interview attachment upload inputs. Added focused accessibility tests that failed before the labels were added. | `pnpm test --run tests/automation-form-settings-panel-accessibility.test.tsx tests/surrogate-interview-accessibility.test.tsx`; scoped React Doctor no longer reports missing labels in `components/forms/builder` or `components/surrogates/interviews/InterviewTab`; full React Doctor accessibility count dropped from `28` to `26`. |
| `react-doctor/no-giant-component` | `components/forms/builder/AutomationFormSettingsPanel.tsx` | Valid but out of scope: the settings panel remains a 411-line component. Splitting identity, delivery, public-copy, and upload-rule sections should be a separate component decomposition batch. | Medium | Deferred. No suppression added. | Changed-scope React Doctor reports only this pre-existing large-component warning. |

Scoped command after Batch 97: `cd apps/web && npx react-doctor@latest components/forms/builder --verbose`

- Score: `86 / 100 Great`
- Total diagnostics in scope: `5`
- Remaining: `prefer-tag-over-role` in `FormBuilderWorkspace` plus four `no-giant-component` warnings.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-87055461-0d88-4400-97c3-2f805de02ddc`

Scoped command after Batch 97: `cd apps/web && npx react-doctor@latest components/surrogates/interviews/InterviewTab --verbose`

- Score: `86 / 100 Great`
- Total diagnostics in scope: `2`
- Remaining: `async-await-in-loop` and `no-giant-component` in `context.tsx`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e743e405-65e8-4b0a-8c71-6b41d789c4b5`

Changed-scope command after Batch 97: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Remaining: `no-giant-component` in `components/forms/builder/AutomationFormSettingsPanel.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ab1179b6-d405-42e1-a530-8dc371b8c9bc`

Full command after Batch 97: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `562`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 26 warnings`, `Maintainability 341 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-89554275-2bda-443a-802e-5f350c549063`

## Batch 98

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-tag-over-role` | `components/forms/builder/FormBuilderWorkspace.tsx` | Valid: the canvas field selector used a generic element with `role="button"`, `tabIndex`, and keyboard emulation for a native button interaction. | High | Replace the generic role button with a native full-field `<button type="button">` overlay. Keep preview content and duplicate/delete actions as sibling elements so no interactive controls are nested inside the select button. Added a source guard that failed on the previous `role="button"` pattern. | `pnpm test --run tests/react-regressions-source.test.ts tests/form-builder-page.test.tsx tests/platform-form-template-page.test.tsx`; scoped React Doctor no longer reports `prefer-tag-over-role` in `components/forms/builder`; full React Doctor accessibility count dropped from `26` to `25`. |
| `react-doctor/no-giant-component` | `components/forms/builder/FormBuilderWorkspace.tsx` | Valid but out of scope: `FieldInspector` remains a 603-line component. Splitting inspector sections is a larger component-decomposition batch. | Medium | Deferred. No suppression added. | Changed-scope React Doctor reports only this pre-existing large-component warning. |

Scoped command after Batch 98: `cd apps/web && npx react-doctor@latest components/forms/builder --verbose`

- Score: `93 / 100 Great`
- Total diagnostics in scope: `4`
- Remaining: four `no-giant-component` warnings.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-d532de29-2054-495e-a3a3-4622ddd98220`

Changed-scope command after Batch 98: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Remaining: `no-giant-component` in `components/forms/builder/FormBuilderWorkspace.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9917771a-3220-4fed-818c-e8d6e72dbc2e`

Full command after Batch 98: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `561`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 25 warnings`, `Maintainability 341 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-c9142dad-e54c-4a97-aff1-0519ce59a967`

## Batch 99

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-tag-over-role` | `components/ui/input-group.tsx` | Valid: `InputGroup` is a visual input wrapper, not an actionable button, but it exposed `role="button"` to assistive technology. | High | Remove the fake button role and add a regression test that asserts the shared primitive does not create a button landmark. | The new test failed before the fix and passed after it: `pnpm test --run tests/input-group-accessibility.test.tsx tests/react-regressions-source.test.ts`; changed-scope React Doctor reports no issues. |
| `react-doctor/no-noninteractive-tabindex` | `components/ui/input-group.tsx` | Valid: `InputGroupAddon` was only a decorative/focus-forwarding area but added `tabIndex={0}`, creating an extra keyboard stop that did not perform its own action. | High | Remove `tabIndex`, keep pointer/touch focus forwarding via `onPointerDown`, and skip forwarding when the event starts from a nested interactive control. | Focused accessibility test verifies the addon is not tabbable and still focuses the real input on pointer interaction; full React Doctor accessibility count dropped from `25` to `22`. |
| `react-doctor/react-compiler-no-manual-memoization` | `components/ui/input-group.tsx` | Valid: the input-focus helper was wrapped in `React.useCallback` even though React Compiler is enabled and the helper does not need manual memoization. | High | Move the helper to module scope and call it from the pointer handler. | Source guard verifies `React.useCallback` is absent; full React Doctor manual memoization count dropped from `225` to `224`. |

Changed-scope command after Batch 99: `cd apps/web && npx react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 99: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `557`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 340 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a8dc3da3-f71d-4dc2-bb71-70173d1d4c66`

## Batch 100

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `lib/hooks/use-unified-calendar-data.ts` | Valid: `userTimezone` was a pure browser capability fallback wrapped in `useMemo`, but React Compiler is enabled and this derivation does not need manual memoization. | High | Move the timezone lookup to a module-scope helper and call it directly during render. Added a source guard that failed against the previous `useMemo` wrapper. | `pnpm test --run tests/react-regressions-source.test.ts tests/unified-calendar-reschedule-dnd.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; hooks-scope React Doctor manual memoization count dropped from `7` to `6`; changed-scope React Doctor reports no issues. |

Scoped command after Batch 100: `cd apps/web && npx react-doctor@latest lib/hooks --verbose`

- Score: `72 / 100 Needs work`
- Total diagnostics in scope: `53`
- Summary: `Bugs 47 warnings`, `Maintainability 6 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-75336268-7c21-42f6-b023-f3dbbc606faf`

Changed-scope command after Batch 100: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 100: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `556`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 339 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8137139e-1718-45ac-9af6-b1ed7183f48a`

## Batch 101

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `lib/hooks/use-ai.ts`, `lib/hooks/use-browser-notifications.ts`, `lib/hooks/use-dashboard-socket.ts`, `lib/hooks/use-notification-socket.ts` | Valid with caveat: the `useCallback` wrappers were redundant under React Compiler, but the socket hooks could not be converted to raw render-scope callbacks because that introduced `exhaustive-deps` warnings and React Compiler errors. | High | Remove the remaining hook-level `useCallback` wrappers. Keep simple returned helpers as plain functions, move socket connector recursion into the owning effect, and combine notification socket connection state with `useReducer` so the changed files stay compiler-clean. Added a source guard that failed against the previous wrappers. | RED: `pnpm test --run tests/react-regressions-source.test.ts` failed on `useCallback`. GREEN: `pnpm test --run tests/react-regressions-source.test.ts tests/dashboard-socket.test.tsx tests/notification-socket-hook.test.tsx tests/notification-bell.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; hook-scope React Doctor manual memoization count dropped from `6` to `0`; changed-scope React Doctor reports no issues. |

Invalid implementation shapes rejected during Batch 101:

- Render-scope raw socket functions fixed manual memoization but introduced `react-hooks/exhaustive-deps` warnings and React Doctor compiler errors for hoisted function references.
- Ref-backed socket functions fixed dependencies but wrote `ref.current` during render, which React Compiler rejects.

Scoped command after Batch 101: `cd apps/web && npx react-doctor@latest lib/hooks --verbose`

- Score: `75 / 100 Needs work`
- Total diagnostics in scope: `47`
- Summary: `Bugs 47 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-d13c6dbb-f967-4d31-82f3-28454e74c5e3`

Changed-scope command after Batch 101: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 101: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `550`
- Summary: `Bugs 171 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 333 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9fe11557-de99-4dc7-9b48-1c8d0c804223`

## Batch 102

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-import.ts` lifecycle mutations: preview, submit, approve, reject, retry, run inline, cancel | Valid scanner finding with behavior already protected: these mutations already invalidated import and surrogate caches through `invalidateImportCaches`, but React Doctor's rule only detects cache operations in the mutation options tree. | High | Inline the existing import list, pending approval, detail, and surrogate cache invalidations inside each mutation `onSuccess`, and add the missing reject-import assertion to the mutation invalidation contract test. | RED: `pnpm test --run tests/use-mutation-invalidations.test.ts tests/react-regressions-source.test.ts` failed on the new source guard. GREEN: same focused command passed with `226` tests. Hook-scope React Doctor warnings dropped from `47` to `40`; all lifecycle import warnings cleared. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-import.ts` `useAiMapImport` | False positive: AI column mapping is a one-shot preview action. It does not mutate persisted import state and has no matching cached query to refresh. | High | Logged as invalid for this batch; no dummy invalidation added. | After Batch 102, the only remaining `use-import.ts` warning is `use-import.ts:198`, which is `useAiMapImport`. |

Scoped command after Batch 102: `cd apps/web && npx react-doctor@latest lib/hooks --verbose`

- Score: `75 / 100 Needs work`
- Total diagnostics in scope: `40`
- Summary: `Bugs 40 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-2b2ed03d-8494-441b-8178-dcde0a0baec4`

Changed-scope command after Batch 102: `cd apps/web && npx react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 102: `cd apps/web && npx react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `543`
- Summary: `Bugs 164 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 333 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-d0e753ea-157a-413a-aebf-66603455e3cf`

## Batch 103

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-ai.ts` focused AI generation mutations: `useSummarizeSurrogate`, `useDraftEmail`, `useAnalyzeDashboard` | Valid scanner finding with behavior already protected: these mutations already refreshed AI usage summary caches through `invalidateAIUsageCaches`, but React Doctor's rule only detects cache operations inside the mutation options tree. | High | Inline the existing usage-summary invalidations directly in each mutation `onSuccess`, preserving `queryKey: aiKeys.usageSummary()` and `exact: false`. Added a source guard that fails if these focused hooks hide the invalidation behind the helper again. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "focused AI usage"` failed on `useSummarizeSurrogate`. GREEN: `pnpm test --run tests/use-mutation-invalidations.test.ts tests/react-regressions-source.test.ts` passed with `227` tests; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. Hook-scope React Doctor warnings dropped from `40` to `37`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-ai.ts` `useTestAPIKey` | False positive: API-key testing validates supplied credentials and returns an immediate test result. It does not mutate a persisted cached AI resource and has no matching query cache to refresh. | High | Logged as invalid for this batch; no dummy invalidation added. | After Batch 103, the only remaining `use-ai.ts` warning is `use-ai.ts:51`, which is `useTestAPIKey`. |

Scoped command after Batch 103: `cd apps/web && npx -y react-doctor@latest lib/hooks --verbose`

- Score: `75 / 100 Needs work`
- Total diagnostics in scope: `37`
- Summary: `Bugs 37 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-70e7a874-aafd-45ad-9108-2a30ac6d3619`

Changed-scope command after Batch 103: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 103: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `540`
- Summary: `Bugs 161 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 333 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ae64e736-0e33-48e8-ad42-3aecc4d69079`

## Batch 104

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-interviews.ts` AI summary mutations: `useSummarizeInterview`, `useSummarizeAllInterviews` | Valid scanner finding with behavior already protected: interview AI summary mutations already refreshed the AI usage summary through `invalidateAIUsageCaches`, but React Doctor's rule only detects cache operations inside mutation options. | High | Inline the existing AI usage-summary invalidation inside each interview summary mutation. Kept `aiKeys` private because the existing source guard requires hook key factories to stay private; used the same literal usage-summary key already asserted by the mutation contract test. Made `invalidateAIUsageCaches` private after removing its last external import. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "interview AI usage"` failed on `useSummarizeInterview`. Rejected shape: exporting `aiKeys` failed the existing private-key-factory source guard. GREEN: `pnpm test --run tests/use-mutation-invalidations.test.ts tests/react-regressions-source.test.ts` passed with `228` tests; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. Hook-scope React Doctor warnings dropped from `37` to `35`, and hook score moved from `75` to `76`. |

Scoped command after Batch 104: `cd apps/web && npx -y react-doctor@latest lib/hooks --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics in scope: `35`
- Summary: `Bugs 35 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-f82b6d07-193e-4a02-a474-619d690efd8b`

Changed-scope command after Batch 104: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 104: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `538`
- Summary: `Bugs 159 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 333 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-80c0e0fb-d9bd-4c9a-91db-da736005c7e2`

## Batch 105

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-workflows.ts` workflow lifecycle mutations: `useUpdateWorkflow`, `useDeleteWorkflow`, `useToggleWorkflow`, `useDuplicateWorkflow` | Valid scanner finding with behavior already protected: these mutations already refreshed workflow list, stats, and detail caches through helper functions, but React Doctor's rule only detects cache operations inside mutation options. | High | Inline the existing list, stats, detail set, detail invalidate, and detail remove cache operations inside each mutation `onSuccess`. Added a source guard that fails if these mutations hide cache operations behind helper wrappers again. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "workflow mutation cache invalidations"` failed on `invalidateWorkflowCollectionCaches`. GREEN: `pnpm test --run tests/use-mutation-invalidations.test.ts tests/react-regressions-source.test.ts` passed with `229` tests; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reports no issues. Hook-scope React Doctor warnings dropped from `35` to `32`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-workflows.ts` `useTestWorkflow` | False positive: workflow testing runs a one-shot test against a selected entity and returns the immediate test result. It does not mutate persisted workflow configuration or a cached workflow collection, and there is no matching query cache to refresh. | High | Logged as invalid for this batch; no dummy invalidation added. | After Batch 105, the only remaining `use-workflows.ts` warning is `use-workflows.ts:185`, which is `useTestWorkflow`. |

Scoped command after Batch 105: `cd apps/web && npx -y react-doctor@latest lib/hooks --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics in scope: `32`
- Summary: `Bugs 32 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8f2dc845-60ca-46b0-a9e2-eccc47bad276`

Changed-scope command after Batch 105: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 105: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `535`
- Summary: `Bugs 156 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 333 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-dc89ed51-6423-4dfe-acbb-539a28182ee6`

## Batch 106

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-email-templates.ts` `useSendEmail` | Valid scanner finding with behavior already protected: sending a surrogate email already refreshed surrogate activity, detail, list, and analytics activity-feed caches through `invalidateSurrogateCrmCaches`, but React Doctor's rule only detects cache operations inside mutation options. | High | Inline the existing surrogate/activity-feed invalidations inside `useSendEmail` and add a source guard that fails if the hook hides those cache operations behind the helper again. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "email send surrogate cache invalidations"` failed on `invalidateSurrogateCrmCaches`. GREEN: `pnpm test --run tests/use-mutation-invalidations.test.ts tests/react-regressions-source.test.ts` passed with `230` tests; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reports no issues. Hook-scope React Doctor warnings dropped from `32` to `31`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-email-templates.ts` `useSendTestEmailTemplate` | False positive: sending a test template email validates and returns the immediate test-send result. It does not mutate persisted template state, surrogate CRM state, or a cached template collection. | High | Logged as invalid for this batch; no dummy invalidation added. | After Batch 106, the only remaining `use-email-templates.ts` warning is `use-email-templates.ts:118`, which is `useSendTestEmailTemplate`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-campaigns.ts` `usePreviewFilters` | False positive: recipient filter preview runs an ad hoc preview against supplied filter criteria before campaign creation. It does not mutate persisted campaign state and has no matching campaign query cache to refresh. | High | Logged as invalid after code inspection; no dummy invalidation added. | Hook-scope React Doctor still reports `use-campaigns.ts:101`, which is `usePreviewFilters`. |

Scoped command after Batch 106: `cd apps/web && npx -y react-doctor@latest lib/hooks --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics in scope: `31`
- Summary: `Bugs 31 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-558c3562-bcf7-4b73-995a-3abd8792c75b`

Changed-scope command after Batch 106: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 106: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `534`
- Summary: `Bugs 155 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 333 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-82136ab0-3fed-4187-81d6-d11cc1065785`

## Batch 107

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-user-integrations.ts` Zoom mutations: `useCreateZoomMeeting`, `useSendZoomInvite` | Valid scanner finding with behavior already protected: these mutations already refreshed surrogate activity, detail, list, and analytics activity-feed caches through `invalidateSurrogateCrmCaches`, but React Doctor's rule only detects cache operations inside mutation options. | High | Inline the existing surrogate/activity-feed invalidations inside both Zoom mutation `onSuccess` handlers and add a source guard that fails if these hooks hide those cache operations behind the helper again. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "Zoom surrogate cache invalidations"` failed on `invalidateSurrogateCrmCaches`. GREEN: the same source guard passed; `pnpm test --run tests/use-mutation-invalidations.test.ts -t "Zoom"` passed with `2` tests; changed-scope React Doctor reports no issues. Hook-scope React Doctor warnings dropped from `31` to `30`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-user-integrations.ts` OAuth redirect mutations: `useConnectZoom`, `useConnectGmail`, `useConnectGoogleCalendar`, `useConnectGcp` | False positive: each mutation fetches an authorization URL and immediately leaves the app via `window.location.assign(...)`. The durable integration state changes on the provider callback flow, not in these mutations, so there is no local query cache to refresh before redirect. | High | Logged as invalid for this batch; no dummy invalidation added. | After Batch 107, the only remaining `use-user-integrations.ts` warnings are `use-user-integrations.ts:84`, `109`, `134`, and `211`, which are the OAuth redirect mutations. |

Scoped command after Batch 107: `cd apps/web && npx -y react-doctor@latest lib/hooks --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics in scope: `30`
- Summary: `Bugs 30 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-2326971d-2730-48dd-8b59-99ef107d7536`

Changed-scope command after Batch 107: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 107: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `533`
- Summary: `Bugs 154 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 333 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a3a4cd59-141b-48c3-8300-97019fff2da0`

## Batch 108

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-surrogates.ts` bulk selected-surrogate mutations: `useBulkAssign`, `useBulkArchive` | Valid scanner finding with behavior already protected: these mutations already refreshed selected surrogate activity/detail plus list, stats, unassigned-queue, and analytics activity-feed caches through `invalidateSelectedSurrogateMutationCaches`, but React Doctor's rule only detects cache operations inside mutation options. | High | Inline the existing selected-surrogate invalidations inside both bulk mutation `onSuccess` handlers and add a source guard that fails if these hooks hide those cache operations behind the helper again. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "selected surrogate mutation cache invalidations"` failed on `invalidateSelectedSurrogateMutationCaches`. GREEN: `pnpm test --run tests/use-surrogates-hooks.test.ts tests/react-regressions-source.test.ts` passed with `215` tests; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. Hook-scope React Doctor warnings dropped from `30` to `28`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-surrogates.ts` `usePreviewSurrogateMassEditStage` | False positive: mass-edit stage preview returns an immediate preview for supplied filters and limits. It does not apply a stage change, mutate persisted surrogate state, or update any cached surrogate collection. | High | Logged as invalid for this batch; no dummy invalidation added. | After Batch 108, the only remaining `use-surrogates.ts` warning is `use-surrogates.ts:391`, which is `usePreviewSurrogateMassEditStage`. |

Scoped command after Batch 108: `cd apps/web && npx -y react-doctor@latest lib/hooks --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics in scope: `28`
- Summary: `Bugs 28 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-5192538d-599f-40ab-b154-f0e666c8c926`

Changed-scope command after Batch 108: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 108: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `531`
- Summary: `Bugs 152 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 333 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-6ea854f3-0fcc-44cb-90bb-44961189366a`

## Batch 109

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-forms.ts` form intake/submission mutations: `useSendFormIntakeLink`, `useApproveFormSubmission`, `useRejectFormSubmission`, `useUpdateSubmissionAnswers`, `useUploadSubmissionFile`, `useDeleteSubmissionFile` | Valid scanner finding with behavior already protected: these mutations already refreshed surrogate CRM, submission-list, surrogate-submission, and intake-lead caches through form-specific helper functions, but React Doctor's rule only detects cache operations inside mutation options. | High | Inline the existing cache invalidations inside each mutation `onSuccess` handler and add a source guard that fails if these hooks hide those cache operations behind helper wrappers again. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "form mutation cache invalidations"` failed on `invalidateFormSubmissionMutationCaches`. GREEN: `pnpm test --run tests/use-mutation-invalidations.test.ts tests/react-regressions-source.test.ts` passed with `233` tests; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. Hook-scope React Doctor warnings dropped from `28` to `22`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-forms.ts` `useUploadFormLogo` | False positive: form logo upload returns uploaded asset data for the caller to place into a draft or form update. It does not itself persist a form record or update a cached form collection. | High | Logged as invalid for this batch; no dummy invalidation added. | After Batch 109, the only remaining `use-forms.ts` warning is `use-forms.ts:519`, which is `useUploadFormLogo`. |

Scoped command after Batch 109: `cd apps/web && npx -y react-doctor@latest lib/hooks --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics in scope: `22`
- Summary: `Bugs 22 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-be43ad62-02ad-4670-b0ea-1de80b76567c`

Changed-scope command after Batch 109: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: `No issues found`

Full command after Batch 109: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `525`
- Summary: `Bugs 146 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 333 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-51ea9c4b-0f7e-431e-aea4-05f261bc6d12`

## Batch 110

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/interviews/**`: `CommentCard.tsx`, `TranscriptViewer.tsx`, `SelectionPopover.tsx`, `TranscriptEditor.tsx`, `InterviewComments/TranscriptPane.tsx`, `InterviewComments/MobileLayout.tsx`, `InterviewComments/hooks/useInteractionClasses.ts`, `InterviewComments/index.tsx` | Valid scanner finding: every flagged `memo`, `useMemo`, and `useCallback` resolved to the React package. `apps/web/next.config.js` has `reactCompiler: true`, `babel-plugin-react-compiler` is installed, and the local Next 16 docs confirm this setup reduces the need for manual `useMemo`/`useCallback`. | High | Removed redundant manual memoization wrappers in the interviews feature. Replaced the listener-ref update pattern introduced by plain handlers with React 19 `useEffectEvent`, and moved a pure keydown helper to module scope so the cleanup did not create fresh-dependency React Doctor errors. | Baseline and GREEN: `pnpm test --run tests/transcript-viewer.test.tsx tests/selection-popover-listeners.test.tsx tests/surrogate-interview-accessibility.test.tsx tests/interview-tab.test.tsx` passed with `14` tests; `pnpm test --run tests/react-regressions-source.test.ts -t "interview"` passed with `6` selected tests; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`. Focused interviews React Doctor manual memoization warnings dropped from `29` to `0`; focused total diagnostics dropped from `55` to `22`; full diagnostics dropped from `525` to `492`; global redundant manual memoization dropped from `217` to `188`. |
| `react-doctor/no-effect-with-fresh-deps` | `SelectionPopover.tsx`, `TranscriptViewer.tsx` | Valid secondary finding after removing `useCallback`: ref-sync effects depended on newly allocated plain handlers. | High | Used `useEffectEvent` for document/listener callbacks that need current props/state and removed a no-op `mousedown` listener in `TranscriptViewer`. | Changed-scope React Doctor no longer reports `no-effect-with-fresh-deps` errors. |

Scoped command after Batch 110: `cd apps/web && npx -y react-doctor@latest components/surrogates/interviews --verbose`

- Score: `62 / 100 Needs work`
- Total diagnostics in scope: `22`
- Summary: `Bugs 12 warnings`, `Performance 3 warnings`, `Accessibility 3 warnings`, `Maintainability 4 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-471f43a7-05c5-4ea0-95c8-15e45e144f27`

Changed-scope command after Batch 110: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `85 / 100 Great`
- Total diagnostics in changed files: `17`
- Summary: `Bugs 9 warnings`, `Performance 2 warnings`, `Accessibility 3 warnings`, `Maintainability 3 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8193265a-a049-4cee-a020-335b7d98ef7f`
- Note: remaining changed-file diagnostics are non-manual-memoization findings that require separate behavior validation.

Full command after Batch 110: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `492`
- Summary: `Bugs 142 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 304 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-d4b28ba2-f9f3-432d-aae6-753535ffa36a`

## Batch 111

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/profile/ProfileCard/context.tsx` | Valid scanner finding: every flagged `useMemo` and `useCallback` resolved to React imports. `apps/web/next.config.js` has `reactCompiler: true`, `babel-plugin-react-compiler@^1.0.0` is installed, and the Next 16 docs confirm this setup reduces the need for manual `useMemo`/`useCallback`. | High | Removed all manual memoization wrappers in the ProfileCard provider, moved pure equality helpers to module scope, and added a source regression guard so this provider does not reintroduce `useMemo` or `useCallback`. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "profile card provider"` failed on `useMemo`. GREEN: the same test passed; `pnpm test --run tests/surrogate-profile-card-accessibility.test.tsx` passed with `3` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Focused ProfileCard diagnostics dropped from `32` to `2`; focused manual memoization warnings dropped from `29` to `0`; full diagnostics dropped from `492` to `462`; global redundant manual memoization dropped from `188` to `159`. |
| `react-doctor/only-export-components` | `components/surrogates/profile/ProfileCard/context.tsx:16` | Valid but not addressed in this batch: the file intentionally exports context constants/types/hooks next to the provider. Moving those exports is a separate module-boundary refactor with import churn outside the manual-memoization scope. | Medium | Logged for a later focused batch; no suppression added. | Changed-scope React Doctor reports this as the only remaining changed-file issue. |
| `react-doctor/no-many-boolean-props` | `components/surrogates/profile/ProfileCard/FieldRow.tsx:41` | Valid but outside this batch: splitting `FieldRowValue` variants would change component structure and should be handled with a dedicated behavior/accessibility test slice. | Medium | Logged for a later focused batch; no suppression added. | Focused ProfileCard React Doctor reports this as one of two remaining ProfileCard issues. |

Scoped command after Batch 111: `cd apps/web && npx -y react-doctor@latest components/surrogates/profile/ProfileCard --verbose`

- Score: `88 / 100 Great`
- Total diagnostics in scope: `2`
- Summary: `Maintainability 2 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1ab76cb4-1f42-4b90-b0a9-46f42eb7d442`

Changed-scope command after Batch 111: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-b5dfcf29-060b-4da9-90fb-7a4c295384ac`
- Note: remaining changed-file diagnostic is `only-export-components` in the touched context file and requires a separate import-boundary refactor.

Full command after Batch 111: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `462`
- Summary: `Bugs 142 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 274 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a6b2cbbd-f044-4d13-8d87-90707d8d8297`

## Batch 112

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/detail/SurrogateDetailLayout/context.tsx` | Valid scanner finding: every flagged `useMemo` and `useCallback` resolved to React imports. `apps/web/next.config.js` has `reactCompiler: true`, `babel-plugin-react-compiler@^1.0.0` is installed, and the Next 16 docs confirm this setup reduces the need for manual `useMemo`/`useCallback`. | High | Removed all manual memoization wrappers in the SurrogateDetailLayout provider, used `useEffectEvent` for invalid-tab normalization after plain handler conversion, moved local timezone fallback to a module helper, and added a source regression guard so this provider does not reintroduce `useMemo` or `useCallback`. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate detail layout context internals"` failed first on `useMemo`. GREEN: the same test passed; `pnpm test --run tests/surrogate-detail.test.tsx tests/surrogate-detail-dialog-pickers.test.tsx tests/header-actions.test.tsx` passed with `66` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Focused SurrogateDetailLayout manual memoization warnings dropped from `31` to `0`; full diagnostics dropped from `462` to `430`; global redundant manual memoization dropped from `159` to `128`. |
| `react-doctor/no-event-handler` | `components/surrogates/detail/SurrogateDetailLayout/context.tsx:314` | Valid secondary finding after removing manual memoization: the Zoom idempotency ref reset was routed through an `activeDialog` effect even though `activeDialog` is local state set by dialog handlers. The canonical rule validation identifies this as work that belongs in the handler that changed the state. | High | Moved the Zoom idempotency ref reset into `openDialog` for non-Zoom dialogs and into `closeDialog`, then added a source guard preventing the `activeDialog` effect from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate detail layout context internals"` failed on `}, [activeDialog]`. GREEN: the same test passed; focused and changed-scope React Doctor no longer report `no-event-handler` for this file. |
| `react-doctor/no-prevent-default` | `components/surrogates/detail/SurrogateDetailLayout/dialogs/EditDialog.tsx:142` | Valid but outside this batch: converting the surrogate edit form from `onSubmit`/`preventDefault` to a progressive form action changes dialog submission behavior and should be handled with a dedicated form regression slice. | Medium | Logged for a later focused batch; no suppression added. | Focused SurrogateDetailLayout React Doctor reports this as one of two remaining SurrogateDetailLayout issues. |
| `react-doctor/no-giant-component` | `components/surrogates/detail/SurrogateDetailLayout/context.tsx:259` | Valid but outside this batch: splitting the 448-line provider into smaller modules is a broader context-boundary refactor with import and provider-surface risk. | High | Logged for a later focused batch; no suppression added. | Changed-scope React Doctor reports this as the only remaining changed-file issue. |

Scoped command after Batch 112: `cd apps/web && npx -y react-doctor@latest components/surrogates/detail/SurrogateDetailLayout --verbose`

- Score: `78 / 100 Needs work`
- Total diagnostics in scope: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1478520b-7a89-4772-b34a-f76cc3656eb3`

Changed-scope command after Batch 112: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-60a0455b-0a4d-4551-a775-854edb5bd9f2`
- Note: remaining changed-file diagnostic is the valid `no-giant-component` provider split and requires a separate context-boundary refactor.

Full command after Batch 112: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `430`
- Summary: `Bugs 141 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 243 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-0982ba45-0bf4-4c1d-bae0-2e83862d9e6d`

## Batch 113

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/ChangeStageModal.tsx` | Valid scanner finding: every flagged `useMemo` resolved to the React import. React Compiler is enabled for this app, so these local derivation wrappers are redundant. | High | Removed the `useMemo` import and replaced stage/date/validation derivations with plain values. Added a source regression guard so the modal does not reintroduce manual `useMemo` or `useCallback`. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "change stage modal free of manual React memoization"` failed on `useMemo`. GREEN: the same test passed; `pnpm test --run tests/change-stage-modal.test.tsx` passed with `10` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Full manual memoization warnings dropped from `128` to `118`. |
| `react-doctor/no-cascading-set-state`, `react-doctor/no-event-handler` | `components/surrogates/ChangeStageModal.tsx` modal-open reset effect and interview-stage reset effect | Valid scanner finding: the modal reset was replayed through effects after the parent opened the controlled dialog, and interview field resets were driven by selected-stage state instead of the stage-selection event. | High | Split the controlled wrapper from mounted dialog content, initialized modal state on mount, and moved interview field reset into the stage selection handler. Added a source guard to keep reset logic out of effects. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "change stage modal reset logic out of effects"` failed on missing mounted content split and existing `useEffect`. GREEN: the same test passed; `pnpm test --run tests/change-stage-modal.test.tsx tests/react-regressions-source.test.ts` passed with `220` tests. Changed-scope React Doctor no longer reports `no-cascading-set-state` or `no-event-handler` for this file. |
| `react-doctor/prefer-useReducer` | `components/surrogates/ChangeStageModal.tsx:112` | Valid but outside this batch: the modal still has many related state fields. Consolidating them into a reducer is a larger state-shape refactor and should be handled as its own behavior-preserving slice. | High | Logged for a later focused batch; no suppression added. | Changed-scope React Doctor reports this as one of two remaining changed-file issues. |
| `react-doctor/no-giant-component` | `components/surrogates/ChangeStageModal.tsx:97` | Valid but outside this batch: splitting the 613-line mounted modal content into subcomponents is a broader component-boundary refactor. | High | Logged for a later focused batch; no suppression added. | Changed-scope React Doctor reports this as one of two remaining changed-file issues. |

Scoped command after Batch 113: `cd apps/web && npx -y react-doctor@latest components/surrogates --verbose`

- Score: `56 / 100 Critical`
- Total diagnostics in scope: `90`
- Summary: `Bugs 24 warnings`, `Performance 5 warnings`, `Accessibility 3 warnings`, `Maintainability 58 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a5ebaa5d-9f65-4d76-9c25-e161f3fe8e5a`

Changed-scope command after Batch 113: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-be09fb5a-52ed-40fe-a21e-486e52f79730`
- Note: remaining changed-file diagnostics are the valid `prefer-useReducer` and `no-giant-component` structural refactors.

Full command after Batch 113: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `417`
- Summary: `Bugs 138 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 233 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-eeb84b42-019b-41d0-b8ab-69b65ce86671`

## Batch 114

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/ActivityTimeline.tsx`, `components/intended-parents/IntendedParentActivityTimeline.tsx` | Valid scanner finding: every flagged `memo` and `useMemo` resolved to the React import. React Compiler is enabled for this app, and the React Doctor rule docs confirm these wrappers are redundant when no `preserve-manual-memoization` case applies. | High | Removed `memo` wrappers around timeline row components and replaced stage/task derivation `useMemo` calls with plain derivations. Added a source regression guard for both activity timeline files. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "activity timelines free of manual React memoization"` failed on `useMemo`. GREEN: the same guard passed; `pnpm test --run tests/activity-timeline.test.tsx tests/intended-parent-activity-timeline.test.tsx` passed with `20` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Changed-scope React Doctor reports no issues and scores `100 / 100`. Full manual memoization warnings dropped from `118` to `104`; full diagnostics dropped from `417` to `402`. |

Changed-scope command after Batch 114: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: no issues found

Full command after Batch 114: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `402`
- Summary: `Bugs 138 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 218 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-34288bce-07c6-4ebf-a1a5-c5c679734c98`

## Batch 115

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/MassEditStageModal.tsx` | Valid scanner finding: every flagged `React.useMemo` resolved to the React namespace import. React Compiler is enabled for this app, and the React Doctor rule docs say to delete React `useMemo`/`useCallback`/`memo` wrappers when no preserve-manual-memoization case applies. | High | Replaced the modal's stage, filter, validation, preview-signature, and selected-stage `useMemo` derivations with plain values. Updated the existing source guard to keep this modal free of manual React memoization while preserving the late-stage-load guard. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "MassEditStageModal"` failed on `React.useMemo`. GREEN: the same guard passed; `pnpm test --run tests/mass-edit-stage-modal.test.tsx` passed with `5` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Changed-scope React Doctor scored `98 / 100` with only the pre-existing `no-giant-component` warning for `MassEditStageModal`. Full diagnostics dropped from `402` to `391`; global redundant manual memoization dropped from `104` to `93`. |
| `react-doctor/no-giant-component` | `components/surrogates/MassEditStageModal.tsx:185` | Valid but outside this batch: the modal is still a large component. Splitting it into sections is a broader component-boundary refactor and should be handled separately with behavior coverage. | High | Logged for a later focused batch; no suppression added. | Changed-scope React Doctor reports this as the only remaining changed-file issue. |

Changed-scope command after Batch 115: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-463ab610-1bfe-4dfd-b682-2e879a1ee747`

Full command after Batch 115: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `391`
- Summary: `Bugs 138 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 207 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-51cd5e13-29be-4280-9883-a64d117108e6`

## Batch 116

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/BulkChangeStageModal.tsx`, `components/surrogates/LogContactAttemptDialog.tsx`, `components/surrogates/LogInterviewOutcomeDialog.tsx` | Valid scanner finding: each flagged `React.useMemo` resolved to the React namespace import, and the React Doctor rule docs say to delete React `useMemo`/`useCallback`/`memo` wrappers when no preserve-manual-memoization case applies. | High | Replaced the bulk stage list `useMemo` with the plain filtered/sorted value and moved local max-datetime derivation into module-scope helpers for the contact and interview dialogs. Added a source guard covering all three dialogs. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "small surrogate stage dialogs"` failed on `BulkChangeStageModal` `React.useMemo`. GREEN: the same guard passed; `pnpm test --run tests/bulk-change-stage-modal.test.tsx tests/log-interview-outcome-dialog.test.tsx` passed with `6` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; changed-scope React Doctor scored `97 / 100`; full diagnostics dropped from `391` to `388`; global redundant manual memoization dropped from `93` to `90`. |
| `react-doctor/prefer-useReducer` | `components/surrogates/LogContactAttemptDialog.tsx:63` | Valid but outside this batch: the dialog still has five related state fields. Consolidating them into a reducer is a broader state-shape refactor and should be handled as a separate behavior-preserving slice. | High | Logged for a later focused batch; no suppression added. | Changed-scope React Doctor reports this as the only remaining changed-file issue. |

Changed-scope command after Batch 116: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `97 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Bugs 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-3a7e813b-5741-4704-b71b-3f83c12f11db`
- Note: remaining changed-file diagnostic is the valid `prefer-useReducer` state refactor for `LogContactAttemptDialog`.

Full command after Batch 116: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `388`
- Summary: `Bugs 138 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 204 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-27d722a2-af7b-4626-99f5-377bf6d5342d`

## Batch 117

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/detail/SurrogateDetailContext.tsx`, `components/surrogates/detail/SurrogateDetailHeader.tsx` | Valid scanner finding: both flagged `React.useMemo` calls resolved to the React namespace import, and the React Doctor rule docs say to delete React `useMemo`/`useCallback`/`memo` wrappers when no preserve-manual-memoization case applies. | High | Replaced the context value and current-stage object memoization with plain object derivations. Added a source guard covering both files. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate detail header context"` failed on `React.useMemo`. GREEN: the same guard passed; `pnpm test --run tests/surrogate-detail.test.tsx` passed with `52` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; changed-scope React Doctor scored `100 / 100`; full diagnostics dropped from `388` to `386`; global redundant manual memoization dropped from `90` to `88`. |

Changed-scope command after Batch 117: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: no issues found

Full command after Batch 117: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `386`
- Summary: `Bugs 138 warnings`, `Performance 24 warnings`, `Accessibility 22 warnings`, `Maintainability 202 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9d1738f2-a290-4088-9942-ddb9366d66e0`

## Batch 118

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/ui/carousel.tsx` | Valid scanner finding: all three flagged `React.useCallback` calls resolved to the React namespace import. Next.js docs confirm React Compiler is enabled through `reactCompiler`, and the React Doctor rule docs say to replace React `useCallback` with the bare handler when no preserve-manual-memoization case applies. | High | Replaced the carousel scroll and keyboard handlers with plain functions. Added a source guard to keep the carousel root free of manual memoization. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "carousel root free"` failed on `React.useCallback`. GREEN: the same guard passed; `pnpm test --run tests/carousel-listener-cleanup.test.tsx` passed with `4` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; changed-scope React Doctor scored `100 / 100`; full redundant manual memoization dropped from `88` to `85`. |
| `react-doctor/prefer-tag-over-role` | `components/ui/carousel.tsx:84` | Valid scanner finding: the generic carousel root used `role="region"`, and the React Doctor rule docs say a generic `div` with a static role that maps to a native element should use the semantic tag instead. | High | Changed the carousel root to a named native `<section>` and preserved caller-provided `aria-label` / `aria-labelledby`. Added behavior coverage for the named region and existing arrow-key scrolling. | RED: `pnpm test --run tests/carousel-listener-cleanup.test.tsx -t "named native region"` failed because the root was an unnamed `div role="region"`; the source guard also failed on `role="region"`. GREEN: focused carousel tests passed; changed-scope React Doctor reported no issues; full accessibility warnings dropped from `22` to `21`. |

Changed-scope command after Batch 118: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: no issues found

Full command after Batch 118: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `382`
- Summary: `Bugs 138 warnings`, `Performance 24 warnings`, `Accessibility 21 warnings`, `Maintainability 199 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-81470991-97d0-4dce-b6a4-8e71ae53a61a`

## Batch 119

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `lib/context/ai-context.tsx` | Valid scanner finding: all five flagged `useCallback` calls resolved to the React named import. React Compiler is enabled through `next.config.js`, and the React Doctor rule docs say to replace React `useCallback` wrappers with plain handlers when no preserve-manual-memoization case applies. | High | Replaced the context and panel callback wrappers with plain functions. Added a source guard to keep this provider free of manual callback memoization. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "AI context state"` failed on the old source shape. GREEN: the same guard passed; `pnpm test --run tests/ai-context-provider.test.tsx` passed with `3` behavior tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; changed-scope React Doctor scored `100 / 100`; full redundant manual memoization dropped from `85` to `80`. |
| `react-doctor/no-cascading-set-state` | `lib/context/ai-context.tsx:60` | Valid scanner finding: the route-change effect cleared three related entity-context state fields together. The fields are one logical context snapshot, so a reducer action is the right state boundary. | High | Consolidated `entityType`, `entityId`, and `entityName` into `aiEntityContextReducer`, including a single route-sync action that preserves the existing route-away cleanup behavior. Added behavior coverage for setting, clearing, route cleanup, and keyboard panel toggle. | Focused provider tests passed; `npx -y react-doctor@latest lib/context --verbose` reported no issues; full `no-cascading-set-state` diagnostics dropped from `11` to `10`. |
| `react-doctor/no-event-handler` | `lib/context/ai-context.tsx:66` | Valid as a scanner pattern but not an event-handler smell in this provider: the effect responds to `usePathname`, an external navigation signal. The reducer rewrite still removed the finding without moving route cleanup into unrelated callers. | Medium | Replaced the conditional multi-setter effect body with one reducer dispatch. No suppression added. | `npx -y react-doctor@latest lib/context --verbose` reported no issues; full `no-event-handler` diagnostics dropped from `53` to `52`. |

Changed-scope command after Batch 119: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: no issues found

Full command after Batch 119: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `375`
- Summary: `Bugs 136 warnings`, `Performance 24 warnings`, `Accessibility 21 warnings`, `Maintainability 194 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-afeff8b0-1b4a-4c8e-8015-a59a1caaec2b`

## Batch 120

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/tasks/TasksListView.tsx` | Valid scanner finding: both flagged `useMemo` calls resolved to the React named import. React Compiler is enabled through `next.config.js`, and the React Doctor rule docs say to replace React `useMemo` wrappers with plain derivations when no preserve-manual-memoization case applies. | High | Replaced the grouped-task and selected-count memo wrappers with one plain render-time pass over `incompleteTasks`. Added a source guard to keep the task list view free of manual memoization. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "uses named task list components"` failed on `useMemo`. GREEN: the same guard passed; `pnpm test --run tests/tasks-page.test.tsx` passed with `13` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; changed-scope React Doctor scored `100 / 100`; full diagnostics dropped from `375` to `373`; global redundant manual memoization dropped from `80` to `78`. |

Changed-scope command after Batch 120: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: no issues found

Path-scope command after Batch 120: `cd apps/web && npx -y react-doctor@latest components/tasks --verbose`

- Score: `89 / 100 Great`
- Total diagnostics in `components/tasks`: `1`
- Summary: `Bugs 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-00818bff-aae9-4700-a497-90621b8b7376`
- Note: the remaining `components/tasks` diagnostic is the existing `prefer-useReducer` warning in `AddTaskDialog.tsx`.

Full command after Batch 120: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `373`
- Summary: `Bugs 136 warnings`, `Performance 24 warnings`, `Accessibility 21 warnings`, `Maintainability 192 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-60661933-dc56-4f35-8107-5f080cb263c0`

## Batch 121

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/safe-html-content.tsx` | Valid scanner finding: both flagged calls resolved to `React.useMemo`. React Compiler is enabled through `next.config.js`, and the React Doctor rule docs say to replace React `useMemo` wrappers with plain values when no preserve-manual-memoization case applies. | High | Replaced the parsed-content and sanitized-html memo wrappers with plain render-time derivations. Added a source guard to keep the safe HTML parser and sanitizer free of manual React memoization. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "safe HTML parsing"` failed on the memoized source. GREEN: the same guard passed; `pnpm test --run tests/safe-html-content.test.tsx` passed with `2` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`; changed-scope React Doctor scored `100 / 100`. Full diagnostics dropped from `373` to `371`; global redundant manual memoization dropped from `78` to `76`. |

Changed-scope command after Batch 121: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: no issues found

Full command after Batch 121: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `68 / 100 Needs work`
- Total diagnostics: `371`
- Summary: `Bugs 136 warnings`, `Performance 24 warnings`, `Accessibility 21 warnings`, `Maintainability 190 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8177f010-1403-4ee0-af62-c682de93c3f4`

## Batch 122

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/SurrogateTasksCalendar.tsx` | Valid scanner finding: all three flagged `useMemo` calls resolved to the React named import. React Compiler is enabled through `next.config.js`, and the React Doctor rule docs say to replace React `useMemo` wrappers with plain derivations when no preserve-manual-memoization case applies. | High | Moved task grouping, orphaned-completed detection, completed-count derivation, and due-label formatting into pure helpers, then used plain render-time derivations from the calendar shell. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate card, task calendar"` failed before implementation because the sync-store helper did not exist and the old source still used memoized derivations. GREEN: the same guard passed; `pnpm test --run tests/surrogate-tasks-calendar-accessibility.test.tsx` passed with `2` behavior tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`; changed-scope React Doctor scored `100 / 100`. Full diagnostics dropped from `371` to `366`; global redundant manual memoization dropped from `76` to `73`. |
| `react-doctor/no-event-handler` | `components/surrogates/SurrogateTasksCalendar.tsx:91` | Valid underlying smell: the effect was not an event-handler workflow, but it was still initializing client storage state from an effect. The React Doctor docs call `useSyncExternalStore` the hydration-safe path for external client state. | High | Replaced the mounted-state/localStorage effect with `useSurrogateTaskViewMode`, backed by `useSyncExternalStore`, a server snapshot, a storage-event subscription, and a same-tab custom event after view changes. Added behavior coverage for persisted calendar view and list-view persistence. | The new persisted-view behavior test passed; changed-scope React Doctor reported no issues; full `no-event-handler` diagnostics dropped from `52` to `51`. |
| `react-doctor/no-giant-component` | `components/surrogates/SurrogateTasksCalendar.tsx:78` | Valid scanner finding: the component mixed the shell, header controls, empty state, list rendering, due-label formatting, and derivation logic. | High | Split the shell into focused files: `SurrogateTasksCalendarHeader.tsx`, `SurrogateTasksEmptyState.tsx`, `SurrogateTasksListView.tsx`, `surrogate-task-derivations.ts`, and `use-surrogate-task-view-mode.ts`. | Changed-scope React Doctor reported no issues; full `no-giant-component` diagnostics dropped from `56` to `55`. |

Changed-scope command after Batch 122: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: no issues found

Full command after Batch 122: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `69 / 100 Needs work`
- Total diagnostics: `366`
- Summary: `Bugs 135 warnings`, `Performance 24 warnings`, `Accessibility 21 warnings`, `Maintainability 186 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-f5798063-995f-4cbe-a876-12541aa212ab`

## Batch 123

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/rich-text-editor.tsx` | Valid scanner finding: all five flagged calls resolved to React's named `useCallback` import. React Compiler is enabled through `next.config.js`, and the React Doctor rule docs say to replace React `useMemo` / `useCallback` / `memo` wrappers with plain values/functions when no preserve-manual-memoization case applies. | High | Removed the redundant callback wrappers and used plain editor command handlers. Added a source guard to keep the root rich-text editor free of compiler-obsolete callbacks. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "RichTextEditor split"` failed on `useCallback`. GREEN: the same guard passed; `pnpm test --run tests/rich-text-editor.test.tsx` passed with `7` behavior tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Full redundant manual memoization dropped from `73` to `68`. |
| `react-doctor/no-giant-component` | `components/rich-text-editor.tsx:53` | Valid scanner finding: the root editor mixed Tiptap setup, loading skeleton, toolbar controls, emoji-picker UI, submit handling, and editor content rendering in one 397-line component. | High | Split loading, toolbar, and emoji popover UI into `rich-text-editor-loading.tsx`, `rich-text-editor-toolbar.tsx`, and `rich-text-editor-emoji-popover.tsx` while keeping the public `RichTextEditor` props and ref handle unchanged. | Existing behavior tests for emoji control visibility, emoji insertion, suggestion mode switching, undo/redo labels, and React 19 ref insertion all passed. Full giant-component diagnostics dropped from `55` to `54`. |
| `react-doctor/no-event-handler` | `components/rich-text-editor.tsx:69`, `:74`, `:85-88`, `:92` | Invalid for this batch: the rule docs define the target pattern as a cleanup-less `useEffect` with an `if` reading state/props, but these lines are Tiptap `useEditor` configuration for extensions, initial content, editor attributes, and the Tiptap `onUpdate` callback. There is no state-plus-effect event-handler hop to move into a UI handler. | Medium-high | Logged as a false positive/needs upstream scanner refinement for the Tiptap `useEditor` options shape. No suppression or config change was added. | Changed-scope React Doctor still reports these residual findings; no code change attempted because moving editor ownership to parent would be product-architecture work, not a safe cleanup. |
| `react-doctor/no-pass-data-to-parent` | `components/rich-text-editor.tsx:113` | Invalid for the cited line: the rule docs define a cleanup-less effect that calls a prop function with child-generated data. The cited effect only syncs an external `content` prop into the existing Tiptap editor via `editor.commands.setContent(content)` and does not call a parent callback. | Medium-high | Logged as a false positive/needs upstream scanner refinement. Kept the existing content-sync behavior covered by the editor tests and public API. | Changed-scope React Doctor still reports this residual finding; no suppression or config change was added. |

Changed-scope command after Batch 123: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `90 / 100 Great`
- Total diagnostics in changed files: `6`
- Summary: `Bugs 6 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-bd060271-c44b-4b75-9dad-e0e16c5b6a2f`
- Note: all remaining changed-scope diagnostics are the Tiptap `useEditor` residuals logged above as invalid/needs-upstream, with no suppression added.

Full command after Batch 123: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `69 / 100 Needs work`
- Total diagnostics: `360`
- Summary: `Bugs 135 warnings`, `Performance 24 warnings`, `Accessibility 21 warnings`, `Maintainability 180 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-fe47629e-bf83-4119-ba62-f97e91d9e9e5`

## Batch 124

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/surrogates/SurrogatesFloatingScrollbar.tsx` | Valid scanner finding: the file used 15 React `useMemo` / `useCallback` wrappers even though React Compiler is enabled in `next.config.js`. The derived scrollbar geometry and event handlers did not require preserve-manual-memoization semantics. | High | Moved pointer detection, timer clearing, table-container lookup, scroll-source lookup, and metrics measurement into module-scope helpers; replaced memoized values and callbacks with plain render-time derivations/functions; used `useEffectEvent` only for effect-owned scroll listeners that need latest render state. Added a source guard to keep this scrollbar free of manual React memoization. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "floating scrollbar free"` failed on the old `useMemo` / `useCallback` source. GREEN: the same guard passed; `pnpm test --run tests/surrogates-floating-scrollbar.test.tsx` passed with `8` behavior tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Full redundant manual memoization dropped from `68` to `53`. |
| `react-doctor/prefer-use-effect-event` / `react-doctor/exhaustive-deps` | `components/surrogates/SurrogatesFloatingScrollbar.tsx` | Valid follow-on finding during implementation: removing manual callbacks naively made the subscription effect depend on fresh render functions, which resubscribed timers/listeners and broke idle hiding behavior. | High | Reworked the effect-owned scroll/mouse/resize listeners to call a `useEffectEvent` wrapper and moved effect-local sync/metric work inside the effect. Removed the effect-event function from the dependency list after React Doctor correctly flagged it. | The focused scrollbar behavior tests caught the idle-hide regression during the first implementation attempt. Final changed-scope React Doctor has no errors and no effect-event dependency findings. |
| `react-doctor/no-cascading-set-state`, `react-doctor/no-initialize-state`, `react-doctor/prefer-useReducer`, `react-doctor/no-giant-component` | `components/surrogates/SurrogatesFloatingScrollbar.tsx` | Valid residual warnings, but not part of this manual-memoization batch. They imply a broader reducer/external-store and component-splitting refactor that should be handled as a separate TDD slice because it touches timer, pointer, and visibility behavior. | Medium-high | Logged as next-batch candidates. No suppression or config change was added. | Changed-scope React Doctor after this batch scores `89 / 100` with these four residual warnings only. |

Changed-scope command after Batch 124: `cd apps/web && npx -y react-doctor@latest --verbose --scope changed`

- Score: `89 / 100 Great`
- Total diagnostics in changed files: `4`
- Summary: `Bugs 3 warnings`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-bfb00731-fff3-4177-92ab-98874f98485b`
- Note: remaining changed-scope diagnostics are the broader reducer/initialization/component-size warnings logged above as a separate future batch.

Full command after Batch 124: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `69 / 100 Needs work`
- Total diagnostics: `344`
- Summary: `Bugs 134 warnings`, `Performance 24 warnings`, `Accessibility 21 warnings`, `Maintainability 165 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1b0c528a-2c72-4fd3-a0b4-080aa8cf3f24`

## Batch 125

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `tests/date-range-picker.test.tsx` | Valid scanner finding in the date-range picker URL harness: the test harness used one `useMemo` and three `useCallback` wrappers around plain query-string derivations and handlers. React Compiler is enabled in `next.config.js`, and no preserve-manual-memoization behavior was needed in this harness. | High | Removed the manual memoization import and wrappers, derived `URLSearchParams` directly from the current query string, and kept the effect dependent on `query` by constructing fresh params inside the effect body. Extended the existing source guard so the harness stays free of `useMemo` and `useCallback`. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "date-range picker URL harness"` failed on the old `useMemo` / `useCallback` source. GREEN: the same guard passed; `pnpm test --run tests/date-range-picker.test.tsx` passed with `3` behavior tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`; changed-scope React Doctor scored `100 / 100`. Full redundant manual memoization dropped from `53` to `49`. |

Changed-scope command after Batch 125: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: no issues found

Full command after Batch 125: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `69 / 100 Needs work`
- Total diagnostics: `340`
- Summary: `Bugs 134 warnings`, `Performance 24 warnings`, `Accessibility 21 warnings`, `Maintainability 161 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1020440c-841b-422f-99b5-63103a735eb9`

## Batch 126

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `app/ops/templates/workflows/[id]/page.client.tsx` | Valid scanner finding: the workflow template editor wrapped trigger setters, option derivations, trigger payload building, and save persistence in `useMemo` / `useCallback`, even though React Compiler is enabled and none of these wrappers needed preserve-manual-memoization semantics. | High | Removed `useMemo` and `useCallback`; derived option lists directly; kept trigger-config updates reducer-backed; converted trigger payload and persistence helpers to plain functions. Extended the source guard so the page stays free of manual React memoization. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "platform workflow save and publish"` failed on the old `useMemo` / `useCallback` source. GREEN: the same guard passed; `pnpm test --run tests/react-regressions-source.test.ts -t "workflow"` passed with `7` source guards; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`; changed-scope React Doctor scored `100 / 100`. Full redundant manual memoization dropped from `49` to `38`. |
| `react-doctor/exhaustive-deps` | `app/ops/templates/workflows/[id]/page.client.tsx` | Valid follow-on finding after removing `useMemo`: `statusOptions` fell back to a fresh empty array, making the hydrate effect dependency unstable when workflow options were not loaded. | High | Added a module-level empty status-options array and reused it as the fallback dependency value. | Path-scope React Doctor no longer reports the missing-dependency warning. |
| `react-doctor/prefer-module-scope-pure-function` | `app/ops/templates/workflows/[id]/page.client.tsx` | Valid scanner finding: `getActionValidationError` used no hook-local state and was rebuilt in `useWorkflowTemplatePageState`. | High | Moved `getActionValidationError` to module scope. | Path-scope React Doctor no longer reports the pure-function warning. |
| `react-doctor/no-many-boolean-props` | `app/ops/templates/workflows/[id]/page.client.tsx` | Valid scanner finding: `WorkflowTemplateHeader` accepted five boolean flags, making header states harder to reason about. | High | Replaced the boolean-heavy header API with named `mode`, `publicationStatus`, and `busyAction` props. Added source guard coverage for the named-state API. | RED: the source guard failed on the old boolean prop API. GREEN: the same guard passed; path-scope React Doctor scored `100 / 100`; changed-scope React Doctor scored `100 / 100`. |

Changed-scope command after Batch 126: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100 Great`
- Total diagnostics in changed files: `0`
- Summary: no issues found

Path-scope command after Batch 126: `cd apps/web && npx -y react-doctor@latest 'app/ops/templates/workflows/[id]' --verbose`

- Score: `100 / 100 Great`
- Total diagnostics in workflow template page: `0`
- Summary: no issues found

Full command after Batch 126: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `69 / 100 Needs work`
- Total diagnostics: `327`
- Summary: `Bugs 134 warnings`, `Performance 24 warnings`, `Accessibility 21 warnings`, `Maintainability 148 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-6e217e4f-3cf8-4864-9040-181e0cb0d429`

## Batch 127

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/appointments/PublicBookingPage.tsx` | Valid scanner finding: the nine flagged calls resolved to React's named `useMemo` import. React Compiler is enabled, and the React Doctor rule docs say to replace React `useMemo` wrappers with plain values/functions when no preserve-manual-memoization case applies. | High | Removed the manual memoization import and wrappers from public booking date-time formatters, calendar-day derivation, timezone options, selected meeting modes, available dates, and date-filtered slots. Moved block-style derivations into pure helpers and preserved the original mount-time slot range with a lazy `useState` initializer. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "keeps production date-time formatters"` failed on the old source. GREEN: the same guard passed; `pnpm test --run tests/appointments-google-meet.test.tsx` passed with `15` behavior tests; `pnpm test --run tests/react-regressions-source.test.ts tests/appointments-google-meet.test.tsx` passed with `233` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Changed-scope React Doctor no longer reports manual memoization in `PublicBookingPage.tsx`. |
| `react-doctor/no-event-handler`, `react-doctor/prefer-useReducer`, `react-doctor/no-giant-component` | `components/appointments/PublicBookingPage.tsx` | Valid residual findings, but outside this manual-memoization batch. Fixing them implies a reducer-backed page-state refactor and/or page split that changes event/state ownership and should be handled as a separate TDD slice. | Medium-high | Logged as next-batch candidates. No suppression or config change was added. | Changed-scope React Doctor after this batch scored `91 / 100` with these five residual warnings only. |

Changed-scope command after Batch 127: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `91 / 100 Great`
- Total diagnostics in changed files: `5`
- Summary: `Bugs 4 warnings`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-006cf555-ca61-473f-b045-134ff981091a`
- Note: remaining changed-scope diagnostics are the broader page-state and component-size warnings logged above as a separate future batch.

Full command after Batch 127: not rerun. The required network escalation for `npx -y react-doctor@latest . --verbose` was rejected by the environment usage limit after the local test/lint checks passed.

## Batch 128

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/jsx-key` | `app/(app)/dashboard/components/attention-needed-panel.tsx`, `components/appointments/AppointmentsList.tsx`, `components/appointments/UnifiedCalendar.tsx`, `components/surrogates/CombinedMedicalInsuranceCard.tsx`, `components/surrogates/interviews/CommentCard.tsx` | Valid scanner finding in React Doctor `v0.6.0`: each flagged element is produced by a rendered `.map()` / array literal sibling list and placed its stable `key` before optional prop spreads, so a spread could shadow the list key. | High | Moved each stable list key after the optional spreads so the intended identity wins, without changing the rendered component props otherwise. Added a source guard across the five affected files. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "rendered list keys"` failed on the old key-before-spread order. GREEN: the same guard passed; `pnpm test --run tests/appointments-google-meet.test.tsx tests/unified-calendar-reschedule-dnd.test.tsx tests/surrogate-interview-accessibility.test.tsx` passed with `26` behavior tests; `pnpm test --run tests/dashboard.test.tsx -t "limits upcoming list|attention"` passed with `2` behavior tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Changed-scope React Doctor no longer reports `react-doctor/jsx-key`. |
| `react-doctor/react-compiler-no-manual-memoization`, `react-doctor/prefer-tag-over-role`, `react-doctor/rerender-state-only-in-handlers`, `react-doctor/prefer-module-scope-pure-function`, `react-doctor/no-giant-component`, `react-doctor/prefer-explicit-variants`, `react-doctor/prefer-useReducer` | Touched changed-scope files | Valid residual findings, but outside this JSX key error batch. The largest residual cluster remains `UnifiedCalendar` manual memoization and structural appointment calendar warnings. | Medium-high | Logged as next-batch candidates. No suppression or config change was added. | Changed-scope React Doctor after this batch scored `89 / 100` with `45` warnings and no errors. |

Changed-scope command after Batch 128: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `89 / 100 Great`
- Total diagnostics in changed files: `45`
- Summary: `Bugs 2 warnings`, `Performance 3 warnings`, `Accessibility 5 warnings`, `Maintainability 35 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-d4f4a50a-c457-4de4-83e3-48e457fece86`
- Note: `react-doctor/jsx-key` no longer appears in changed-scope diagnostics.

Full command after Batch 128: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics: `269`
- Summary: `Bugs 95 warnings`, `Performance 21 warnings`, `Accessibility 14 warnings`, `Maintainability 139 warnings`
- Removed globally: `react-doctor/jsx-key` (`11` errors)
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-3dca72fa-9bde-42cf-bad0-7bc564287c97`

## Batch 129

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/react-compiler-no-manual-memoization` | `components/appointments/UnifiedCalendar.tsx` | Valid scanner finding: all 29 flagged calls resolved to React's `memo`, `useMemo`, or `useCallback` import in a file covered by React Compiler (`reactCompiler: true`, `babel-plugin-react-compiler@1.0.0`). The wrapped component outputs, date-range derivations, formatter objects, grouped calendar maps, agenda lists, and event handlers did not need preserve-manual-memoization semantics. | High | Removed the React `memo`, `useMemo`, and `useCallback` import and wrappers; converted the memoized item components to plain function components; derived calendar maps, agenda lists, date-range params, timezone formatters, and handlers directly during render so React Compiler can cache them. Added/updated source guards to keep UnifiedCalendar free of manual React memoization while preserving direct `Intl.DateTimeFormat` construction without `new`. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "unified calendar manual memoization\|production date-time formatters"` failed on the old `memo(function`, `useMemo`, and formatter expectations. GREEN: the same guard passed; `pnpm test --run tests/unified-calendar-reschedule-dnd.test.tsx` passed with `4` behavior tests; `pnpm test --run tests/appointments-google-meet.test.tsx -t "appointment details\|reschedule\|Google Meet join link"` passed with `4` behavior tests; `pnpm test --run tests/react-regressions-source.test.ts -t "immutable sorting in unified calendar\|resets unified calendar\|subtle calendar accents\|rendered list keys"` passed with `4` guards; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Changed-scope React Doctor no longer reports manual memoization in `UnifiedCalendar.tsx`. |
| `react-doctor/prefer-tag-over-role`, `react-doctor/rerender-state-only-in-handlers`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `components/appointments/UnifiedCalendar.tsx` | Valid residual findings surfaced in the changed file, but outside this manual-memoization batch. The role-to-button fixes affect interactive element semantics; the drag-state refactor changes drag state ownership; the giant-component/useReducer warnings imply a broader calendar split/state-machine refactor. | Medium-high | Logged as next-batch candidates. No suppression or config change was added. | Changed-scope React Doctor after this batch scored `90 / 100` with `8` warnings: `4` accessibility, `1` performance, `1` bug, `2` maintainability. |

Changed-scope command after Batch 129: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `90 / 100 Great`
- Total diagnostics in changed files: `8`
- Summary: `Bugs 1 warning`, `Performance 1 warning`, `Accessibility 4 warnings`, `Maintainability 2 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-844f2939-f581-458d-b2a9-ea9fc5e01308`
- Note: `react-doctor/react-compiler-no-manual-memoization` no longer appears in changed-scope diagnostics.

Full command after Batch 129: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics: `240`
- Summary: `Bugs 95 warnings`, `Performance 21 warnings`, `Accessibility 14 warnings`, `Maintainability 110 warnings`
- Removed globally: `react-doctor/react-compiler-no-manual-memoization` in `UnifiedCalendar.tsx` (`29` warnings)
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-914b4e93-e94e-4f81-9347-4a08681cd550`

## Batch 130

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/rerender-state-only-in-handlers` | `components/surrogates/interviews/SelectionPopover.tsx`, `components/ai/ScheduleParserDialog.tsx` | Valid scanner finding: selected transcript text/range and the schedule parser bulk request id are handler-only instance values. They do not feed rendered output, and updating them with `useState` caused avoidable rerenders. | High | Replaced selected transcript payload state with refs, replaced the schedule parser idempotency key state with a ref, and added a source guard to keep these handler-only values out of render state. Added behavior coverage that clicking the selection popover still passes the selected transcript text/range to the comment flow. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "handler-only transcript and schedule values"` failed on the old `useState` values. GREEN: the same guard passed; `pnpm test --run tests/selection-popover-listeners.test.tsx` passed with `3` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Full React Doctor state-only handler warnings dropped from `15` to `12`. |
| `react-doctor/prefer-module-scope-pure-function` | `components/ai/ScheduleParserDialog.tsx` | Valid follow-on finding in changed scope: `makeId` and `getConfidenceBadge` used only globals/imports/params and did not close over component state or props. | High | Hoisted them to module scope as `makeScheduleParserId` and `getConfidenceBadge`, with the same source guard covering the helper shape. | RED: the focused source guard failed on the nested `makeId`. GREEN: the guard passed; changed-scope React Doctor no longer reports pure-function warnings. Full React Doctor pure-function warnings dropped from `16` to `14`. |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `components/ai/ScheduleParserDialog.tsx` | Valid residual findings, but outside this handler-only state and pure-helper batch. Fixing them implies a reducer-backed dialog state transition and component split that should be a separate TDD slice. | Medium-high | Logged as next-batch candidates. No suppression or config change was added. | Changed-scope React Doctor after this batch scored `92 / 100` with these `2` residual warnings only. |

Changed-scope command after Batch 130: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4939db9a-08d2-4960-bcce-c2a0daebe3bf`

Full command after Batch 130: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics: `235`
- Summary: `Bugs 95 warnings`, `Performance 18 warnings`, `Accessibility 14 warnings`, `Maintainability 108 warnings`
- Removed globally: `react-doctor/rerender-state-only-in-handlers` (`3` warnings) and `react-doctor/prefer-module-scope-pure-function` (`2` warnings)
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-aa4677f1-4835-475a-837c-6788ca9f1776`

## Batch 131

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/rerender-state-only-in-handlers` | `app/(app)/automation/email-templates/page.tsx` | Valid scanner finding: `templateBodyModeTouched`, `activeInsertionTarget`, `copyShareTarget`, `testSendTouched`, and `libraryCopyTarget` were bookkeeping values read only by effects or event handlers. They do not feed JSX or rendered derivations, so `useState` rerendered the email template page without changing visible UI. | High | Replaced those values with refs, kept UI-driven values like `copyShareName` and `testSendVariables` in state, and captured ref targets in local constants before mutation calls. Added a source guard so these handler-only values stay out of render state. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "email template handler bookkeeping"` failed on the old `useState` declarations, then failed again when `testSendTouched` was added to the guard. GREEN: the same guard passed; `pnpm test --run tests/email-templates-page.test.tsx` passed with `16` behavior tests; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor no longer reports state-only handler warnings for `email-templates`. |
| `react-doctor/rerender-state-only-in-handlers` | `app/(app)/settings/queues/page.tsx` | False positive: the flagged `selectedUserId` state is render-reachable. It drives the queue member `Select` value and disables/enables the Add button in JSX, so changing it to a ref would break the visible selection flow. | High | No code change. Logged as invalid after source validation. | Source evidence: `selectedUserId` is used in `<Select value={selectedUserId}>` and `disabled={!selectedUserId || addMemberMutation.isPending}`. |
| `react-doctor/no-event-handler`, `react-doctor/no-giant-component`, `react-doctor/prefer-explicit-variants`, `react-doctor/no-many-boolean-props`, `react-doctor/prefer-useReducer` | `app/(app)/automation/email-templates/page.tsx` | Valid residual findings, but outside this handler-only state batch. Fixing them implies moving effect-triggered event logic into originating handlers and splitting/reducing the large email-template page, which should be handled as separate TDD slices. | Medium-high | Logged as next-batch candidates. No suppression or config change was added. | Changed-scope React Doctor after this batch scored `90 / 100` with these `7` residual warnings only. |

Changed-scope command after Batch 131: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `90 / 100 Great`
- Total diagnostics in changed files: `7`
- Summary: `Bugs 4 warnings`, `Maintainability 3 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1492b521-368e-49ad-b5d8-e95fa008a4d1`
- Note: `react-doctor/rerender-state-only-in-handlers` no longer appears in changed-scope diagnostics.

Full command after Batch 131: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics: `229`
- Summary: `Bugs 94 warnings`, `Performance 13 warnings`, `Accessibility 14 warnings`, `Maintainability 108 warnings`
- Removed globally: `react-doctor/rerender-state-only-in-handlers` in `email-templates` (`5` warnings) and one follow-on `react-doctor/no-event-handler` warning tied to the touched-state effect dependency.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-08d481f1-e652-43d7-8491-0acc525f4743`

## Batch 132

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/rerender-state-only-in-handlers` | `app/(app)/settings/integrations/meta/forms/[id]/page.tsx` | Valid scanner finding: `touchedColumns` is bookkeeping for handler logic and save-payload construction. It is not rendered in JSX and does not feed render-derived locals, so state updates caused avoidable rerenders while editing mappings. | High | Replaced `touchedColumns` render state with a ref while keeping rendered mapping data and unknown-column behavior in state. Added behavior coverage that a manually touched unknown Meta column is saved under `warn` behavior while an untouched unknown column is omitted. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "Meta form mapping touched columns"` failed on the old `useState` shape. GREEN: the same guard passed; `pnpm test --run tests/meta-form-mapping-page.test.tsx` passed with `4` behavior tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. Full React Doctor state-only handler warnings dropped from `7` to `6`. |
| `react-doctor/rerender-lazy-ref-init` | `app/(app)/settings/integrations/meta/forms/[id]/page.tsx` | Valid follow-on finding after the first ref conversion: `useRef(new Set())` allocates a fresh `Set` every render even though React only uses the initial ref value once. The rule docs recommend `useRef(null)` plus a guarded assignment. | High | Switched the touched-column ref to lazy initialization with `useRef<Set<string> | null>(null)` and a `current === null` guard. Updated the source guard to keep the lazy-ref shape. | RED: the focused source guard failed on `useRef<Set<string>>(new Set())`. GREEN: the guard passed, and changed-scope React Doctor no longer reports `rerender-lazy-ref-init`. |
| `react-doctor/rerender-state-only-in-handlers` | `components/intended-parents/IntendedParentClinicCard.tsx`, `components/surrogates/CombinedMedicalInsuranceCard.tsx` | False positives: `manuallyAddedSections`, `optimisticallyHiddenSections`, `manuallyAdded`, and `optimisticallyHiddenSections` are render-reachable. They feed `visibleKeys`, `hiddenKeys`, and ultimately `visibleSections`, which controls which medical/insurance sections render. | High | No code change. Logged as invalid after source validation. | Source evidence: both cards build `visibleKeys` from the flagged state values and then derive rendered `visibleSections`. |
| `react-doctor/rerender-state-only-in-handlers`, `react-doctor/no-giant-component` | `app/(app)/settings/queues/page.tsx`, `components/appointments/UnifiedCalendar.tsx`, `app/(app)/settings/integrations/meta/forms/[id]/page.tsx` | Valid residual findings, but outside this Meta form touched-column batch. `editingQueue` and `draggedAppointment` are handler-only instance values that can be refactored separately; `MetaFormMappingPage` remains a large component split candidate. | Medium-high | Logged as next-batch candidates. No suppression or config change was added. | Changed-scope React Doctor after this batch scored `98 / 100` with only the `no-giant-component` warning in `MetaFormMappingPage`. |

Changed-scope command after Batch 132: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100 Great`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8518ee0d-1fe9-4568-a16f-98cb15e235ff`
- Note: `react-doctor/rerender-state-only-in-handlers` and `react-doctor/rerender-lazy-ref-init` no longer appear in changed-scope diagnostics.

Full command after Batch 132: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `76 / 100 Needs work`
- Total diagnostics: `228`
- Summary: `Bugs 94 warnings`, `Performance 12 warnings`, `Accessibility 14 warnings`, `Maintainability 108 warnings`
- Removed globally: `react-doctor/rerender-state-only-in-handlers` in the Meta form mapping page (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ff118b54-4eda-4c39-bd0f-b69fdde01d9a`

## Batch 133

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/rerender-state-only-in-handlers` | `app/(app)/settings/queues/page.tsx` | Valid scanner finding in React Doctor `v0.6.0`: `editingQueue` is only read in submit/cancel/edit handlers. It does not feed JSX or render-derived locals, so updating it as state caused an avoidable rerender. | High | Replaced `editingQueue` state with `editingQueueRef`, kept dialog open state and form data in render state, and added edit-save behavior coverage so the selected queue id is still submitted. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "queue edit target"` failed on the old `useState` shape. GREEN: the same guard passed; `pnpm test --run tests/queues-settings-page.test.tsx` passed with `3` behavior tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run`; `git diff --check`. |
| `react-doctor/prefer-module-scope-pure-function` | `app/(app)/settings/queues/page.tsx` | Valid follow-on finding in changed scope: `resolveErrorMessage` only uses its parameters and `Error`, so it does not need to be rebuilt inside `QueuesSettingsPage`. | High | Hoisted `resolveErrorMessage` to module scope and extended the source guard to keep it above the component. | RED: the focused source guard failed while the helper remained nested. GREEN: the guard passed after the hoist; local TypeScript/lint/full tests passed. |
| `react-doctor/no-giant-component` | `app/(app)/settings/queues/page.tsx` | Valid residual finding, but outside this handler-only queue target batch. Splitting the queue settings page is a larger component-structure refactor and should be handled separately. | Medium-high | Logged as a next-batch candidate. No suppression or config change was added. | Changed-scope React Doctor before the helper hoist scored `93 / 100` with `prefer-module-scope-pure-function` and `no-giant-component`; final React Doctor rerun was blocked by the environment usage limit. |

Changed-scope command after the first Batch 133 edit: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `93 / 100 Great`
- Total diagnostics in changed files: `2`
- Summary: `Maintainability 2 warnings`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-95ed5b45-eee0-441b-8d4b-9c17418b843d`
- Note: `react-doctor/rerender-state-only-in-handlers` no longer appeared in changed-scope diagnostics.

Changed-scope command after the helper hoist: not rerun. The required escalation for `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed` was rejected by the approval reviewer because the Codex account hit its usage limit.

Full command after Batch 133: not rerun for the same usage-limit reason. The latest full scan before this batch remained `76 / 100`, `228` issues, with diagnostics at `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-083eca4f-3cfb-45f4-be16-537f9206fb5c`.

## Batch 134

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-module-scope-pure-function` | `app/(app)/dashboard/components/attention-needed-panel.tsx`, `app/(app)/intended-parents/matches/[id]/page.client.tsx`, `app/login/LoginPageClient.tsx`, `app/ops/layout.tsx`, `components/appointments/AppointmentSettings.tsx`, `components/ops/agencies/AgencyInvitesTab.tsx`, `components/session-expired-dialog.tsx`, `components/surrogates/SurrogateApplicationTab.tsx`, `components/surrogates/tabs/SurrogateNotesTab.tsx`, `components/ui/sonner.tsx`, `components/version-history-modal.tsx` | Valid scanner findings in the latest full diagnostics, except `resolveErrorMessage` in `settings/queues` which Batch 133 had already fixed. The remaining helpers did not close over component state; where they needed inputs, the inputs were already explicit call arguments or module imports. | High | Hoisted the render-local helpers to module scope: upcoming time formatting, match date/date-time formatting, login return target detection, ops logout redirect, booking preview/error formatting, invite cooldown formatting, login redirect, submission field-value rendering, note initials, toaster theme resolution, and version-history date formatting. Added a source guard that failed before the hoists and prevents the nested helper shapes from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "remaining pure render helpers"` failed on the old nested helpers. GREEN: the same guard passed; `pnpm test --run tests/react-regressions-source.test.ts tests/surrogate-application-tab.test.tsx tests/surrogate-notes-tab.test.tsx tests/version-history-modal.test.tsx tests/appointments-google-meet.test.tsx tests/agency-time-rendering.test.tsx tests/ops-layout.test.tsx tests/match-detail.test.tsx tests/match-detail-overview-tabs.test.tsx` passed with `274` tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run` passed with `1085` tests; `git diff --check`. |

Changed-scope command after Batch 134: not rerun. `npx react-doctor@latest . --verbose` failed in the sandbox with DNS `ENOTFOUND registry.npmjs.org`; network escalation for downloading and executing `react-doctor@latest` was rejected by the approval reviewer; `npx --offline -y react-doctor@latest . --verbose --scope changed` failed with `ENOTCACHED`.

Full command after Batch 134: not rerun for the same tool-availability reason. The latest full React Doctor evidence remains the pre-Batch-134 scan at `76 / 100`, `228` issues, with diagnostics at `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-083eca4f-3cfb-45f4-be16-537f9206fb5c`.

## Batch 135

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/rerender-state-only-in-handlers` | `components/appointments/UnifiedCalendar.tsx` | Valid scanner finding: `draggedAppointment` was only written in `handleDragStart`, read in `handleDrop`, and cleared in drop paths. It did not feed JSX or render-derived locals; `dragOverDate` is the render-visible drag highlight and remains state. | High | Replaced `draggedAppointment` state with `draggedAppointmentRef`, kept `dragOverDate` as render state, and added a source guard so the drag payload does not return to `useState`. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "unified calendar drag payload"` failed on the old `useState` shape. GREEN: the same guard passed; `pnpm test --run tests/unified-calendar-reschedule-dnd.test.tsx` passed with `4` drag/reschedule tests; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run` passed with `1086` tests. |
| `react-doctor/rerender-state-only-in-handlers` | `components/intended-parents/IntendedParentClinicCard.tsx`, `components/surrogates/CombinedMedicalInsuranceCard.tsx` | False positives after current-source validation: `manuallyAddedSections`, `optimisticallyHiddenSections`, `manuallyAdded`, and `optimisticallyHiddenSections` remain render-reachable because they feed visible section key derivation and control which medical/insurance sections render. | High | No code change. Kept these as state and logged the evidence instead of converting render-affecting values to refs. | Source validation by read-only subagent and prior Batch 132 evidence agree that these values feed `visibleSections`. |
| `react-doctor/rerender-state-only-in-handlers` | `app/(app)/settings/queues/page.tsx` | Stale in the latest full diagnostics: Batch 133 had already replaced `editingQueue` state with `editingQueueRef`. | High | No code change. | Current source uses `editingQueueRef`; no `editingQueue` state remains. |

Changed-scope command after Batch 135: not rerun. React Doctor remains unavailable in this environment for the same reason as Batch 134 (`npx` network blocked/rejected; offline cache missing).

Full command after Batch 135: not rerun for the same tool-availability reason. The latest full React Doctor evidence remains the pre-Batch-134 scan at `76 / 100`, `228` issues, with diagnostics at `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-083eca4f-3cfb-45f4-be16-537f9206fb5c`.

## Batch 136

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-tag-over-role` | `components/inline-edit-field.tsx` | Valid scanner finding: display mode was a clickable `div role="button"` with custom keyboard emulation, and it has no nested interactive children. A native button preserves the edit-trigger behavior with better browser/assistive-tech semantics. | High | Replaced the faux button with `<button type="button">`, removed `role`, `tabIndex`, and the display-only keydown handler, and updated tests to assert the native button shape. | RED: `pnpm test --run tests/inline-fields-accessibility.test.tsx tests/react-regressions-source.test.ts -t "InlineEditField"` failed on the old `div` trigger. GREEN: the same focused command passed; `pnpm test --run tests/inline-fields-accessibility.test.tsx tests/surrogates-accessibility.test.tsx tests/react-regressions-source.test.ts`; `pnpm test --run tests/surrogate-detail.test.tsx -t "renders surrogate header"`; `pnpm tsc --noEmit`; `pnpm lint`; `pnpm test --run` passed with `1085` tests; `git diff --check`. |
| Test selector hardening | `tests/surrogate-detail.test.tsx` | Valid follow-on: after inline display triggers became native buttons, the surrogate-detail copy-email test's `querySelector('button')` clicked the first inline edit trigger instead of the labeled copy button. | High | Updated the test to select `role="button"` with name `/copy email/i`, matching the existing `aria-label` in the component. | The focused surrogate-detail test and full test suite passed. |

Changed-scope command after Batch 136: not rerun. React Doctor remains unavailable in this environment for the same reason as Batch 134 (`npx` network blocked/rejected; offline cache missing).

Full command after Batch 136: not rerun for the same tool-availability reason. The latest full React Doctor evidence remains the pre-Batch-134 scan at `76 / 100`, `228` issues, with diagnostics at `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-083eca4f-3cfb-45f4-be16-537f9206fb5c`.

## Batch 137

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-tag-over-role` | `components/appointments/UnifiedCalendar.tsx` | Valid scanner findings: Google Calendar events navigate to `event.html_link`, so they should be anchors, and clickable appointment event tiles should be native buttons instead of `div role="button"` plus custom keyboard emulation. | High | Replaced Google event wrappers with external `<a>` links, replaced clickable appointment event wrappers with `<button type="button">` while preserving drag behavior, and left non-clickable event render paths as static `<div>` elements. Removed the custom `activateWithKeyboard` helper from this component. | RED: `pnpm test --run tests/unified-calendar-reschedule-dnd.test.tsx -t "Google Calendar events"` failed because no native link existed; `pnpm test --run tests/unified-calendar-reschedule-dnd.test.tsx -t "native draggable buttons"` failed because the appointment tile was a `DIV`. GREEN: both focused tests passed after the fixes; `pnpm test --run tests/unified-calendar-reschedule-dnd.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "uses subtle calendar accents|unified calendar drag payload"`; changed-scope React Doctor no longer reports `prefer-tag-over-role` for `UnifiedCalendar`. |
| `react-doctor/prefer-tag-over-role` | `components/appointments/AppointmentsList.tsx`, `components/email/EmailComposeDialog.tsx`, `components/surrogates/interviews/InterviewComments/TranscriptPane.tsx` | Current residual findings are not safe one-line native-element swaps. `AppointmentsList` needs the selectable card area split away from nested approve/decline buttons; the email composer is a `contentEditable` rich textbox; the transcript pane is selectable rich transcript content with delegated comment targeting. | Medium-high | No code change. Logged as separate follow-up candidates or false positives instead of converting them blindly. | Read-only validation against current source and existing source guards. Full React Doctor now reports `prefer-tag-over-role` only for these three files. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-profile.ts`, `lib/hooks/use-forms.ts`, `lib/hooks/use-user-integrations.ts`, `lib/hooks/use-mfa.ts`, `lib/hooks/use-platform-templates.ts` | Sampled diagnostics are false positives or no-ops for cache invalidation today: profile sync returns staged data rather than persisted profile detail; form logo upload patches local builder state before save; OAuth/Duo hooks fetch redirect URLs or set callback state outside React Query; platform test/campaign sends do not update template queries and no query-backed log key exists here. | High for sampled hooks | No code change. Do not add noisy invalidations to redirect/setup hooks. If callback or log flows become React Query-backed later, invalidate the dedicated status/list/log keys then. | Read-only subagent validation plus `pnpm test --run tests/use-mutation-invalidations.test.ts` passed with `25/25` in the subagent workspace. |

Changed-scope command after Batch 137: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `2`
- Summary: `Maintainability 2 warnings`
- Remaining changed-scope diagnostics: `react-doctor/no-giant-component` for `components/appointments/UnifiedCalendar.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1e100e01-9116-4d49-aa7e-3bcedc236384`

Full command after Batch 137: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `206`
- Summary: `Bugs 93 warnings`, `Performance 10 warnings`, `Accessibility 9 warnings`, `Maintainability 94 warnings`
- Removed globally since the fresh Batch 137 starting scan: `react-doctor/prefer-tag-over-role` in `UnifiedCalendar` (`4` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-42fec818-763b-4bd1-931e-27fdb62685db`

## Batch 138

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `deslop/unused-export` | `lib/api/matches.ts`, `lib/hooks/use-surrogate-emails.ts`, `lib/intended-parent-stage-utils.ts`, `lib/api/surrogate-emails.ts`, `lib/hooks/use-tickets.ts`, `lib/api/tickets.ts` | Valid unused public surface after `rg` validation. `getMatchEvent`, match event color maps, `usePatchSurrogateEmailContact`, the backing surrogate email patch API, `useTicketSendIdentities`, and the backing ticket send-identities API had no callers. The intended-parent fallback stage list and value lookup are still used internally, but did not need to be exported. | High | Deleted unused functions/constants/types where they had no internal use, made the intended-parent fallback stage list and value lookup private, and kept `usePatchTicket` exported because `app/(app)/tickets/[ticketId]/page.tsx` imports it. Added a source guard for the public-surface shape. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "unused library helpers"` failed on the old exports, then failed again on follow-on unused surrogate/ticket identity APIs. GREEN: the same guard passed after pruning; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues. |
| `react-doctor/async-defer-await` | `app/mfa/page.client.tsx`, `app/ops/agencies/page.client.tsx` | Not edited. The ops agencies await is followed by the stale-response guard that must run after the request resolves. The MFA challenge flow intentionally awaits `refetch()` before route replacement after completing MFA. Moving either await ahead of current guards would be product-dependent and not a safe mechanical fix. | Medium-high | Logged as deferred or likely false-positive/product-dependent. No suppression or config change was added. | Source inspection only. |
| `react-doctor/rendering-usetransition-loading` | `app/login/LoginPageClient.tsx`, `app/ops/login/page.client.tsx` | Not edited. The loading state is set immediately before `window.location.assign`, so replacing it with `useTransition` is not a clear user-visible improvement and could make disabled-button feedback less deterministic during navigation handoff. | Medium | Logged as deferred or likely low-value. No code change. | Source inspection only. |

Changed-scope command after Batch 138: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 138: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `199`
- Summary: `Bugs 93 warnings`, `Performance 10 warnings`, `Accessibility 9 warnings`, `Maintainability 87 warnings`
- Removed globally since Batch 137: `deslop/unused-export` (`7` initial warnings plus `2` follow-on unused exports exposed by the first cleanup).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-347e5069-a47a-404f-a505-3339fc17ead3`

## Batch 139

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-attachments.ts` | Valid for `useDownloadAttachment` and `useAttachmentDownloadUrl`: signed download URL generation records server-side attachment download / PHI audit events, so `useAuditLogs(...)` list caches can become stale even though attachment lists do not change. | High | Added `useQueryClient()` to both download URL mutations and invalidated the audit list prefix `['audit', 'list']` on success. Did not invalidate attachment lists because URL generation does not modify attachment records. | RED: `pnpm test --run tests/use-mutation-invalidations.test.ts -t "attachment download"` failed with no audit invalidation. GREEN: the same focused test passed; `pnpm test --run tests/use-mutation-invalidations.test.ts`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-ai.ts`, `lib/hooks/use-campaigns.ts`, `lib/hooks/use-email-templates.ts`, `lib/hooks/use-import.ts`, `lib/hooks/use-meta-oauth.ts`, `lib/hooks/use-pipelines.ts`, `lib/hooks/use-resend.ts`, `lib/hooks/use-schedule-parser.ts`, `lib/hooks/use-surrogates.ts`, `lib/hooks/use-workflows.ts` | Read-only validation did not identify more safe true positives in this sampled subset. These hooks are validation-only, preview-only, dry-run, redirect setup, or return proposed data before persistence; several would need a future query-backed log/status surface before invalidation is meaningful. | Medium-high to high by hook | No code change for these sampled diagnostics. Avoided dummy invalidations such as invalidating a query key that no hook owns. | Subagent validation; no tests needed for no-op/preview/redirect findings. |

Changed-scope command after Batch 139: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 139: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `197`
- Summary: `Bugs 91 warnings`, `Performance 10 warnings`, `Accessibility 9 warnings`, `Maintainability 87 warnings`
- Removed globally since Batch 138: `react-doctor/query-mutation-missing-invalidation` in `use-attachments` (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-fd901c9d-40c8-4ba0-b1a4-4d5794bd49ea`

## Batch 140

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-initialize-state` | `components/surrogates/SurrogatesFloatingScrollbar.tsx` | Valid scanner finding: `isDesktopPointer` was initialized to `false`, then corrected in the mount effect with `handleMediaChange()`, causing an avoidable extra render. The existing `detectPointerCapability()` helper is browser-safe and returns a conservative fallback when `window` is unavailable. | High | Initialized `isDesktopPointer` with `useState(detectPointerCapability)` and removed the redundant immediate `handleMediaChange()` call from the effect while keeping media-query change listeners for later device changes. Added a source guard for the initializer shape. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "floating scrollbar"` failed on `useState(false)`. GREEN: the guard passed; `pnpm test --run tests/surrogates-floating-scrollbar.test.tsx`; changed-scope React Doctor no longer reports `no-initialize-state` for the scrollbar. |
| `react-doctor/no-initialize-state` | `components/ui/chart.tsx` | Not edited. The remaining `size` state is derived from `containerRef.current.getBoundingClientRect()` and `ResizeObserver`; there is no DOM element available during render to seed that value safely. Converting it mechanically would require a larger external-store or measurement refactor. | Medium-high | Logged as deferred/likely false positive for direct initialization. No suppression or config change was added. | Source inspection and existing chart-container test context. |

Changed-scope command after Batch 140: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Remaining changed-scope diagnostic: `react-doctor/no-giant-component` for `components/surrogates/SurrogatesFloatingScrollbar.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-26ed4811-2333-4e8a-9e32-790c4ede28e8`

Full command after Batch 140: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `196`
- Summary: `Bugs 90 warnings`, `Performance 10 warnings`, `Accessibility 9 warnings`, `Maintainability 87 warnings`
- Removed globally since Batch 139: `react-doctor/no-initialize-state` in `SurrogatesFloatingScrollbar` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9abeefdd-d180-416c-88c2-e310e9c09ea1`

## Batch 141

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/mouse-events-have-key-events` | `components/surrogates/interviews/InterviewComments/TranscriptPane.tsx` | Valid scanner finding: delegated transcript highlight hover used `onMouseOver` / `onMouseOut` without keyboard-equivalent focus handling, so keyboard users could focus a highlighted transcript span without updating the related hover state. | High | Added delegated `onFocus` and `onBlur` handlers that mirror hover state for `[data-comment-id]` spans. Added behavior coverage for focus setting the hovered comment id and blur clearing it. | RED: `pnpm test --run tests/surrogate-interview-accessibility.test.tsx -t "highlight hover state"` failed because focus did not update hover state. GREEN: the focused transcript tests passed; changed-scope React Doctor no longer reports `mouse-events-have-key-events`. |
| `react-doctor/prefer-tag-over-role` | `components/surrogates/interviews/InterviewComments/TranscriptPane.tsx` | Still not a safe direct swap: the transcript pane is selectable rich transcript content with delegated comment targeting and embedded sanitized HTML, not a normal button. | Medium-high | Left unchanged and continued logging as a false-positive/product-dependent finding rather than converting rich content to a native button. | Changed-scope React Doctor reports only this residual transcript-pane accessibility warning. |

Changed-scope command after Batch 141: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `1`
- Summary: `Accessibility 1 warning`
- Remaining changed-scope diagnostic: `react-doctor/prefer-tag-over-role` for `components/surrogates/interviews/InterviewComments/TranscriptPane.tsx`
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-701f3771-b3a4-4537-ac13-7cfbf230ddaa`

Full command after Batch 141: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `194`
- Summary: `Bugs 90 warnings`, `Performance 10 warnings`, `Accessibility 7 warnings`, `Maintainability 87 warnings`
- Removed globally since Batch 140: `react-doctor/mouse-events-have-key-events` in `TranscriptPane` (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-95be52f6-c2bf-4b67-8ff3-3b23a2abcfd6`

## Batch 142

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/dialog-has-accessible-name`, `react-doctor/prefer-html-dialog` | `tests/integrations-page.test.tsx`, `tests/surrogates.test.tsx` | Valid scanner findings in test mocks: both mocked dialogs used `div role="dialog"` without an accessible name. Since these are local test doubles, swapping to native `<dialog open>` is low risk and better matches the dialog semantics being queried. | High | Replaced the mock dialog wrappers with native `<dialog open aria-label="...">` elements while preserving existing className usage and test query behavior. | `pnpm test --run tests/integrations-page.test.tsx tests/surrogates.test.tsx`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 142: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 142: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `190`
- Summary: `Bugs 90 warnings`, `Performance 10 warnings`, `Accessibility 3 warnings`, `Maintainability 87 warnings`
- Removed globally since Batch 141: test-file `dialog-has-accessible-name` (`2` warnings) and `prefer-html-dialog` (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-c73b9ee7-939f-43ce-9156-c2e5c4ab86ca`

## Batch 143

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `deslop/unused-dependency` | `package.json`, `pnpm-lock.yaml` | Valid scanner findings after `rg` validation: `@tiptap/extension-underline`, `html-to-image`, `input-otp`, `react-resizable-panels`, and `vaul` had no source imports or component usage. | High | Removed the unused dependencies with `pnpm remove`, allowing the package manager to update `package.json` and `pnpm-lock.yaml`. Added a manifest source guard so these packages do not return unnoticed. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "unused dependencies"` failed while the dependencies remained. GREEN: the same guard passed after `pnpm remove`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 143: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 143: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `185`
- Summary: `Bugs 90 warnings`, `Performance 10 warnings`, `Accessibility 3 warnings`, `Maintainability 82 warnings`
- Removed globally since Batch 142: `deslop/unused-dependency` (`5` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-2cb2d81a-ce94-4ea6-b56f-ab14bfda5e82`

## Batch 144

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-multi-comp` | `components/ui/avatar.tsx`, `components/ui/collapsible.tsx`, `components/ui/popover.tsx` | Valid maintainability findings. These shared UI modules were public import surfaces but still declared multiple wrapper components inline, and React Doctor did not classify them as exempt shadcn-style barrels. | High | Split secondary wrappers into one-component files (`avatar-image`, `avatar-fallback`, `collapsible-trigger`, `collapsible-content`, `popover-trigger`, `popover-content`) and kept the original public exports stable from `avatar`, `collapsible`, and `popover`. Added source guards that prevent secondary declarations from returning to the barrel files. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "unused UI subcomponent"` failed on the inline `AvatarImage` declaration. GREEN: the same focused source guard passed after the split; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues. |
| `react-doctor/async-await-in-loop` | `components/surrogates/interviews/InterviewTab/context.tsx` | Not edited. The rule docs say to parallelize only independent awaits; this upload loop currently stops after the first mutation failure, so a direct `Promise.all` rewrite could upload later files after an earlier upload failed. | Medium-high | Left sequential and logged as product-dependent rather than changing upload failure semantics inside the UI-wrapper batch. | Source inspection of `uploadFiles`; no suppression or config change. |

Changed-scope command after Batch 144: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 144: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `179`
- Summary: `Bugs 90 warnings`, `Performance 10 warnings`, `Accessibility 3 warnings`, `Maintainability 76 warnings`
- Removed globally since Batch 143: `react-doctor/no-multi-comp` (`6` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-6be4ad6a-bc58-4939-8aad-14ba70f34d96`

## Batch 145

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/only-export-components` | `components/ui/button.tsx`, `components/ui/toggle.tsx`, `components/ui/time-display.tsx`, `lib/query-provider.tsx`, `components/surrogates/interviews/TranscriptEditor.tsx` | Valid maintainability findings. These modules mixed component exports with variant helpers, hooks, pure utilities, retry logic, or backward-compatible utility re-exports. | High | Moved `buttonVariants`, `toggleVariants`, `formatUtcDateLabel`, `useCurrentMinuteTimestamp`, and `shouldRetryQuery` into adjacent helper modules. Removed the `TranscriptEditor` utility re-export and deleted now-unused transcript utility exports. Updated all imports to the new helper modules. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "non-component exports"` failed first on `buttonVariants`, then on the transcript re-export and unused transcript utilities. GREEN: the focused guard passed after the split and utility cleanup; `pnpm test --run tests/query-provider.test.ts tests/time-display.test.tsx tests/surrogate-interview-accessibility.test.tsx tests/interview-tab.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor no longer reports these `only-export-components` findings. |
| `react-doctor/rendering-usetransition-loading`, `react-doctor/async-defer-await`, `react-doctor/no-prevent-default`, `react-doctor/prefer-dynamic-import` | `app/login/LoginPageClient.tsx`, `app/ops/login/page.client.tsx`, `app/mfa/page.client.tsx`, `app/ops/agencies/page.client.tsx`, `components/tasks/EditDialog.tsx`, `components/ui/chart.tsx` | Triage only. The transition-loading and submit/default-prevention findings need product-behavior decisions; the async findings rely on sequencing guards; the chart dynamic-import finding is valid but should be handled after reading the local Next.js lazy-loading docs. | Medium | Left unchanged in this batch and logged rather than making speculative behavior changes. | Subagent validation plus source inspection; no suppression or config change. |

Changed-scope command after Batch 145: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `32`
- Summary: residual warnings in touched import-consumer files only: `react-doctor/no-giant-component` (`4`), `react-doctor/prefer-useReducer` (`2`), `react-doctor/no-event-handler` (`21`), `react-doctor/rendering-usetransition-loading` (`1`), `react-doctor/async-defer-await` (`1`), and `react-doctor/jsx-max-depth` (`3`).
- Removed from changed-scope results: the targeted `react-doctor/only-export-components` and transcript helper export warnings.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-bad458d7-9424-40fb-8dfe-75b2f881d6af`

Full command after Batch 145: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `172`
- Summary: `Bugs 90 warnings`, `Performance 10 warnings`, `Accessibility 3 warnings`, `Maintainability 69 warnings`
- Removed globally since Batch 144: `react-doctor/only-export-components` (`7` net warnings); no `deslop/unused-export` warnings remain from the transcript helper cleanup.
- Remaining `react-doctor/only-export-components`: `4` warnings in `components/intended-parents/IntendedParentFormFields.tsx` and `components/surrogates/profile/ProfileCard/context.tsx`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-6d0c9ead-b1ba-49a5-a77e-758908e4a9a6`

## Batch 146

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/only-export-components` | `components/intended-parents/IntendedParentFormFields.tsx`, `components/surrogates/profile/ProfileCard/context.tsx` | Valid maintainability findings, independently confirmed by subagents. The intended-parent component file exported form defaults and payload builders, and the profile-card context exported pure template helpers/keys from a client provider module. | High | Moved intended-parent form values, empty defaults, and payload builders into `components/intended-parents/intended-parent-form-values.ts`. Moved profile-card template keys and `renderProfileTemplate` into `components/surrogates/profile/ProfileCard/profile-template.ts`. Updated the existing import sites and extended the source guard to keep those helpers out of component/context modules. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "non-component exports"` failed on `EMPTY_INTENDED_PARENT_FORM_VALUES`. GREEN: the focused guard passed after the split; `pnpm test --run tests/intended-parents-page.test.tsx tests/intended-parent-detail.test.tsx tests/surrogate-profile-card-accessibility.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor no longer reports `only-export-components`. |

Changed-scope command after Batch 146: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `8`
- Summary: residual pre-existing warnings in touched intended-parent page code only: `react-doctor/no-giant-component` (`1`) and `react-doctor/no-event-handler` (`7`).
- Removed from changed-scope results: the targeted `react-doctor/only-export-components` findings.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9d1aa93a-297d-4453-8300-d2b9bcdb4ed0`

Full command after Batch 146: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `168`
- Summary: `Bugs 90 warnings`, `Performance 10 warnings`, `Accessibility 3 warnings`, `Maintainability 65 warnings`
- Removed globally since Batch 145: remaining `react-doctor/only-export-components` (`4` warnings); that rule is no longer present in the full scan.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-208b470a-6c26-4085-9b3a-ac6ea40b0da3`

## Batch 147

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/rerender-state-only-in-handlers` | `components/intended-parents/IntendedParentClinicCard.tsx`, `components/surrogates/CombinedMedicalInsuranceCard.tsx` | False positives, independently confirmed by subagents. In both components the flagged manually added section state is read during render to build `visibleKeys`, `visibleSections`, `availableSections`, and the rendered add/delete section controls. Replacing it with a ref would prevent the UI from rendering newly added sections. | High | Left unchanged and logged; no suppression or config change. | Source inspection of the render derivation and handlers in both files. Existing behavior tests pass: `pnpm test --run tests/intended-parent-detail.test.tsx -t "adds and removes embryo status from medical information"` and `pnpm test --run tests/surrogate-detail.test.tsx -t "allows deleting a visible section from Edit Info with confirmation"`. |

## Batch 148

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-initialize-state` | `components/ui/chart.tsx` | Valid. `ChartContainer` initialized local size state from a mount effect before rendering `ResponsiveContainer`, while Recharts already owns responsive percentage sizing. A subagent confirmed current app call sites provide concrete height classes plus full width. | High | Removed the manual `useState`/`useEffect`/`ResizeObserver` measurement path and rendered `ResponsiveContainer` with `width="100%"`, `height="100%"`, `minHeight={1}`, and `minWidth={1}`. Tightened the source guard and component test around that contract. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "responsive chart sizing"` failed because the wrapper used manual size state. GREEN: focused source guard passed; `pnpm test --run tests/chart-container.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor no longer reports `no-initialize-state`. |
| `react-doctor/prefer-dynamic-import` | `components/ui/chart.tsx` | Valid but deferred. Production chart surfaces already top-level dynamically import both `recharts` and `@/components/ui/chart`, matching the local Next.js lazy-loading guidance for named exports. Replacing the wrapper import itself safely would require a broader chart API refactor because `ChartTooltip` and `ChartLegend` are Recharts-bound aliases composed by Recharts. | Medium-high | Left unchanged and logged; no suppression or config change. | Source inspection plus subagent validation of local `.next-docs/01-app/02-guides/lazy-loading.mdx` and current dashboard/report chart call sites. |

Changed-scope command after Batch 148: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `1`
- Summary: residual `react-doctor/prefer-dynamic-import` in `components/ui/chart.tsx`.
- Removed from changed-scope results: `react-doctor/no-initialize-state` (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-bed199ed-efd7-4a1b-ba63-3ec4a940e453`

Full command after Batch 148: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `166`
- Summary: `Bugs 88 warnings`, `Performance 10 warnings`, `Accessibility 3 warnings`, `Maintainability 65 warnings`
- Removed globally since Batch 146: `react-doctor/no-initialize-state` (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-681bff24-e2fd-4fdf-a486-a96e9deee0c0`

## Batch 149

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-tag-over-role` | `components/appointments/AppointmentsList.tsx` | Valid, but a direct root `<button>` swap was unsafe because pending cards render nested Approve/Decline buttons. A subagent confirmed the safe shape is a native selectable button for the card content plus sibling action buttons. | High | Replaced the outer synthetic `div role="button"` with an inner `<button type="button">` for appointment selection. Kept pending approval actions as siblings. Added a source guard rejecting `role="button"`, `tabIndex={0}`, and manual card key handling, plus a DOM test that pending action buttons are not descendants of the selectable appointment button. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "appointment cards on native button semantics"` failed on the old synthetic role. GREEN: focused source guard passed; `pnpm test --run tests/appointments-google-meet.test.tsx -t "pending appointment selection"`; full `pnpm test --run tests/appointments-google-meet.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor no longer reports this accessibility warning. |
| `react-doctor/prefer-tag-over-role` | `components/email/EmailComposeDialog.tsx`, `components/surrogates/interviews/InterviewComments/TranscriptPane.tsx` | Valid scanner hypotheses but unsafe direct swaps. The email preview is a `contentEditable` rich HTML textbox that reads `innerHTML`; an input/textarea would expose markup text and lose rich editing. The transcript pane wraps selectable sanitized rich transcript HTML with delegated comment targeting, so a native button would be invalid for its contents. | High | Left unchanged and logged; no suppression or config change. | Subagent source validation plus existing email preview-edit/send tests and transcript hover/focus tests. |

Changed-scope command after Batch 149: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `3`
- Summary: residual pre-existing warnings in `components/appointments/AppointmentsList.tsx`: `react-doctor/prefer-explicit-variants`, `react-doctor/no-giant-component`, and `react-doctor/prefer-useReducer`.
- Removed from changed-scope results: `react-doctor/prefer-tag-over-role` for the appointment card.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4a0e8928-5602-464d-b171-b3c0034ac63d`

Full command after Batch 149: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `165`
- Summary: `Bugs 88 warnings`, `Performance 10 warnings`, `Accessibility 2 warnings`, `Maintainability 65 warnings`
- Removed globally since Batch 148: `react-doctor/prefer-tag-over-role` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-31e13bf6-cf56-4f4a-9c79-8a6c33123c18`

## Batch 150

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-explicit-variants` | `components/appointments/AppointmentsList.tsx` | Valid, independently confirmed by subagent. After Batch 149, `AppointmentCard` still owned the pending-card variant through `onApprove`, `onCancel`, `isApproving`, and `isCancelling` boolean/optional props. | High | Refactored `AppointmentCard` to accept a `trailingActions` slot. The parent now renders the pending Approve/Decline buttons with the same handlers, loading icons, disabled states, and classes; non-pending cards still render the chevron inside the selectable button. Added a source guard that keeps pending action props out of `AppointmentCard`. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "pending actions out"` failed on missing `trailingActions`. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "appointment card"`; `pnpm test --run tests/appointments-google-meet.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor no longer reports `prefer-explicit-variants`. |

Changed-scope command after Batch 150: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `2`
- Summary: residual pre-existing warnings in `components/appointments/AppointmentsList.tsx`: `react-doctor/no-giant-component` and `react-doctor/prefer-useReducer`.
- Removed from changed-scope results: `react-doctor/prefer-explicit-variants` for `AppointmentCard`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-180ad583-d47a-4021-86aa-373da8ab2441`

Full command after Batch 150: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `164`
- Summary: `Bugs 88 warnings`, `Performance 10 warnings`, `Accessibility 2 warnings`, `Maintainability 64 warnings`
- Removed globally since Batch 149: `react-doctor/prefer-explicit-variants` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4fd29131-91ca-48ed-b992-ec0a3faffb43`

## Batch 151

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-explicit-variants` | `app/(app)/automation/email-templates/page.tsx`, `components/surrogates/detail/SurrogateAiTab.tsx` | Valid, independently confirmed by subagents. `SignaturePhotoField` mixed upload/delete pending states into its presentational photo layout, and `SurrogateAiTab` exposed action loading variants as boolean props. | High | Converted `SignaturePhotoField` to accept explicit action slots (`avatarAction`, `customPhotoAction`) so the page owns upload/delete controls and pending states. Replaced `SurrogateAiTab` boolean loading props with explicit status props (`summaryStatus`, `draftEmailStatus`). Added a source guard for the prop API and behavior tests for summary/draft loading and disabled states. | GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "small loading variants"`; `pnpm test --run tests/surrogate-ai-tab.test.tsx tests/email-templates-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor no longer reports `prefer-explicit-variants`. |

Changed-scope command after Batch 151: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `6`
- Summary: residual pre-existing warnings in `app/(app)/automation/email-templates/page.tsx`: `react-doctor/no-many-boolean-props` (`1`), `react-doctor/no-giant-component` (`1`), `react-doctor/prefer-useReducer` (`1`), and `react-doctor/no-event-handler` (`3`).
- Removed from changed-scope results: the targeted `react-doctor/prefer-explicit-variants` findings in `SignaturePhotoField` and `SurrogateAiTab`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-73da46c3-855f-4912-b3b3-c623ad6784a9`

Full command after Batch 151: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `162`
- Summary: `Bugs 88 warnings`, `Performance 10 warnings`, `Accessibility 2 warnings`, `Maintainability 62 warnings`
- Removed globally since Batch 150: remaining `react-doctor/prefer-explicit-variants` (`2` warnings); that rule is no longer present in the full scan.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-2d5b636b-4b2d-4a41-8810-b75111cb9365`

## Batch 152

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-many-boolean-props` | `app/(app)/automation/email-templates/page.tsx`, `app/(app)/settings/pipelines/page.tsx`, `components/surrogates/profile/ProfileCard/FieldRow.tsx` | Valid. Subagents confirmed the `TemplateCard` and `DraftActionsCard` findings; local inspection confirmed `FieldRowValue` received related edit/visibility/change booleans from a single caller. | High | Replaced `TemplateCard` capability booleans with a discriminated controls model using pure action IDs plus one action dispatcher, avoiding the callback-object shape that initially triggered a React Compiler ref diagnostic. Collapsed `DraftActionsCard` booleans into a single `DraftSaveState` enum. Grouped `FieldRowValue` props into `valueMode`, `visibility`, and `changeState`. Added a source guard for all three component APIs. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "boolean-heavy action"` failed on the old `TemplateCard` API. GREEN: the same guard passed after the refactor; `pnpm test --run tests/email-templates-page.test.tsx tests/pipelines-settings-page.test.tsx tests/surrogate-profile-card-accessibility.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor no longer reports `no-many-boolean-props`. |

Changed-scope command after Batch 152: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `5`
- Summary: residual pre-existing warnings in `app/(app)/automation/email-templates/page.tsx`: `react-doctor/no-giant-component` (`1`), `react-doctor/prefer-useReducer` (`1`), and `react-doctor/no-event-handler` (`3`).
- Removed from changed-scope results: the targeted `react-doctor/no-many-boolean-props` findings in `TemplateCard`, `DraftActionsCard`, and `FieldRowValue`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4c00184c-25ac-4204-a8d8-220f8d953157`

Full command after Batch 152: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `159`
- Summary: `Bugs 88 warnings`, `Performance 10 warnings`, `Accessibility 2 warnings`, `Maintainability 59 warnings`
- Removed globally since Batch 151: `react-doctor/no-many-boolean-props` (`3` warnings); that rule is no longer present in the full scan.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8240b56d-b53c-4d2c-936f-5e60428b02da`

## Batch 153

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/async-defer-await` | `app/mfa/page.client.tsx`, `app/ops/agencies/page.client.tsx` | Unsafe mechanical fixes / product-dependent false positives. Subagents independently confirmed the MFA path must complete the challenge and refresh auth before routing, and the ops agencies post-await guard prevents stale in-flight list responses from overwriting newer results because `listOrganizations` has no abort signal support. | High for agencies; medium-high for MFA auth-refresh sequencing | Reverted the experimental code change that skipped MFA auth refresh for ops return. Left both production flows unchanged and added an MFA ops-return test that asserts redirect waits for both challenge completion and auth refresh. Kept the existing agencies race test as evidence for the required post-await stale-response guard. No suppression or config change. | RED: a speculative source guard and MFA test failed against the existing code; changed-scope React Doctor still reported both warnings after the unsafe mechanical rewrite, confirming it did not resolve the scanner hypothesis safely. GREEN: `pnpm test --run tests/mfa-page.test.tsx tests/ops-agencies-page-race.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; production diff is intentionally empty for both flagged files. |

Full command after Batch 153: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `159`
- Summary: `Bugs 88 warnings`, `Performance 10 warnings`, `Accessibility 2 warnings`, `Maintainability 59 warnings`
- Unchanged from Batch 152 except for test coverage; `react-doctor/async-defer-await` remains as `2` warnings by design.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e8f88199-f85e-45ca-bfa6-21e64d6697dc`

## Batch 154

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/rendering-usetransition-loading` | `app/login/LoginPageClient.tsx`, `app/ops/login/page.client.tsx` | Valid scanner hit on `isLoading`, but both subagents confirmed the mechanical `useTransition` recipe is the wrong semantic fit for an external OAuth handoff. The state is urgent redirect feedback and double-click prevention, not background UI rendering. | High | Kept deterministic local state but renamed the model to `redirectStatus: "idle" | "redirecting"` and derived `isRedirecting`. Added ops-login behavior coverage and a source guard rejecting `isLoading` / `setIsLoading` in both login clients. No `useTransition`/`startTransition` added. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "login navigation"` failed on the old `isLoading` API. GREEN: focused source guard passed; `pnpm test --run tests/login.test.tsx tests/ops-login-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 154: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 154: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `157`
- Summary: `Bugs 88 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 59 warnings`
- Removed globally since Batch 153: `react-doctor/rendering-usetransition-loading` (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-b9b74af0-bc91-4325-a053-4440b90cf376`

## Batch 155

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-prevent-default` | `components/surrogates/detail/SurrogateDetailLayout/dialogs/EditDialog.tsx` | Valid. The edit dialog used a submit handler only to intercept the browser form submission and run the save mutation. The dialog already has an explicit Save control, so the clearer model is button-driven save with native validity reporting before mutation. | High | Moved save logic into `handleSave`, attached a `formRef`, and used `form.reportValidity()` before collecting `FormData`. Changed Save to `type="button"` with `onClick={() => void handleSave()}` and left the form as a field container. Added a source guard rejecting `onSubmit`, `preventDefault`, and submit buttons in this dialog, plus behavior coverage that an invalid form blocks the mutation. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "edit dialog saves"` failed on the missing button-driven save guard. GREEN: focused source guard passed; `pnpm test --run tests/surrogate-detail.test.tsx -t "edit dialog save\|Journey Timing\|height"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 155: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 155: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `156`
- Summary: `Bugs 87 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 59 warnings`
- Removed globally since Batch 154: `react-doctor/no-prevent-default` (`1` warning); that rule is no longer present in the full scan.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7431179f-eeaf-4579-aa94-00134f07c038`

## Batch 156

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `components/forms/builder/ShareApplicationDialog.tsx` | Valid. The share dialog mixed state wiring, hosted-link display, QR copy, embed diagnostics, embed settings, snippet copy, and footer actions in one large component. | High | Split hosted-link, QR, embed tab, embed settings, snippet, health-check, and footer rendering into focused local components while keeping the parent state and handlers unchanged. Added a source guard requiring the split helper structure. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "share application dialog tabs"` failed on the monolithic component. GREEN: focused source guard passed; `pnpm test --run tests/share-application-dialog.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-user-integrations.ts`, `lib/hooks/use-meta-oauth.ts`, `lib/hooks/use-mfa.ts`, `lib/hooks/use-campaigns.ts`, `lib/hooks/use-profile.ts`, `lib/hooks/use-import.ts`, `lib/hooks/use-forms.ts`, `lib/hooks/use-platform-templates.ts`, `lib/hooks/use-workflows.ts`, `lib/hooks/use-ai.ts`, `lib/hooks/use-resend.ts` | Sampled false positives / product-dependent command mutations. The React Doctor rule docs confirm this is a structural TanStack Query heuristic, and the validated hooks fetch OAuth URLs, initiate external auth redirects, preview/filter/test data, upload transient assets, compute AI/import mappings, or stage profile diffs without persisting cached entities. | Medium-high | Left unchanged and logged instead of adding misleading invalidations to command-style mutations. Continue to validate individual hooks before editing if any later call site proves a real stale-cache path. | Source inspection plus React Doctor rule docs. No suppression or config change. |

Changed-scope command after Batch 156: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 156: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `155`
- Summary: `Bugs 87 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 58 warnings`
- Removed globally since Batch 155: `react-doctor/no-giant-component` for `ShareApplicationDialog` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7e0ca27d-8fc5-4c1e-b7c9-b20171203450`

## Batch 157

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `components/reports/TeamPerformanceTable.tsx` | Valid. The team performance table mixed sort state, status shells, mobile summary cards, sortable headers, data rows, and unassigned rows in one large component. | High | Split status, data-card shell, mobile summary, metric tiles, sortable headers, desktop table, desktop data rows, and unassigned row rendering into focused local components while preserving the public component API and sorting behavior. Added a source guard requiring the split helper structure and keeping the exported component free of the direct table/mobile markup. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "team performance table sections"` failed on the monolithic component. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "team performance"`; `pnpm test --run tests/team-performance-table.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 157: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 157: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `154`
- Summary: `Bugs 87 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 57 warnings`
- Removed globally since Batch 156: `react-doctor/no-giant-component` for `TeamPerformanceTable` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-f2d15a21-2f79-4753-94d5-b90cfd41c755`

## Batch 158

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `components/forms/builder/AutomationFormSubmissionsPanel.tsx` | Valid. The submissions panel mixed approval summary, metrics, ambiguous queue, lead promotion queue, submission history, retry actions, manual linking, and candidate resolution in one large render body. | High | Split the panel into local presentation helpers for workflow approvals, metrics, review queues, history filters/entries/actions, and candidate review while preserving the public prop surface and callback payloads. Added a source guard for the helper split plus direct render coverage for queue/history/candidate actions. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "automation form submissions panel"` failed on the monolithic component. GREEN: `pnpm test --run tests/automation-form-submissions-panel.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "automation form submissions panel\|typographic ellipses in user-facing"`; `pnpm test --run tests/form-builder-page.test.tsx -t "uses design-system tab controls for workspace sections and a dedicated settings tab"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 158: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 158: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `153`
- Summary: `Bugs 87 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 56 warnings`
- Removed globally since Batch 157: `react-doctor/no-giant-component` for `AutomationFormSubmissionsPanel` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-35243218-fc9f-4612-8da6-7be9c0df6b6a`

## Batch 159

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `components/automation/workflow-templates-panel.tsx` | Valid. The workflow templates panel mixed query state, category controls, template sections, form-scoped template resolution, email-template override selection, and create-dialog rendering in one large component. | High | Kept query/mutation/state ownership in the parent, split header, category filter, template sections, dialog body, workflow scope, published-form selector, missing-email selector, and footer into local helpers. Preserved form-scoped auto-selection order, create payloads, workflow invalidation, and added a Cancel regression test. Also gave workflow-scope `SelectValue` a friendly label renderer and replaced the extracted missing-email field key with action-derived metadata. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "workflow templates panel derivations"` failed on the monolithic panel; `pnpm test --run tests/templates-page.test.tsx -t "closes the use-template dialog"` failed after the initial split exposed a Cancel regression. GREEN: `pnpm test --run tests/templates-page.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "workflow templates panel derivations"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 159: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 159: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `152`
- Summary: `Bugs 87 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 55 warnings`
- Removed globally since Batch 158: `react-doctor/no-giant-component` for `WorkflowTemplatesPanel` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4c7e1894-8295-44e3-8f1c-702874bb3ec2`

## Batch 160

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `components/surrogates/ChangeStageModal.tsx` | Valid. The change-stage dialog mixed stage selection, effective scheduling, on-hold follow-up reminders, interview scheduling, delivery details, warnings, reason capture, and footer actions in one component. The interview appointment fields also changed together and were a better fit for a reducer action model. | High | Split the modal body into focused local helpers for stage selection, effective schedule, on-hold follow-up, interview appointment, delivery details, warning banners, reason capture, and actions. Kept state ownership and payload assembly in `ChangeStageModalContent`, then grouped the interview appointment state into `interviewStateReducer`. Added a source guard requiring the split helper structure. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "change stage modal sections"` failed on the monolithic component. GREEN: `pnpm test --run tests/change-stage-modal.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "change stage modal\|stage modals"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 160: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 160: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `150`
- Summary: `Bugs 86 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 54 warnings`
- Removed globally since Batch 159: `react-doctor/no-giant-component` and `react-doctor/prefer-useReducer` for `ChangeStageModal` (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-96846a68-8659-4d3f-9d7e-9524744c4ae4`

## Batch 161

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `components/surrogates/MassEditStageModal.tsx` | Valid. The mass edit modal mixed reducer/model setup, filter derivation, base-filter display, extra filters, action controls, preview rendering, and footer actions in one large component. The split initially surfaced a changed-scope `no-many-boolean-props` warning in the extra-filters helper, so the helper API needed grouped state/errors instead of many individual `is*`/`has*` props. | High | Kept reducer state, one-reset-per-open behavior, late default-stage loading, preview signature, and mutation payload construction intact. Extracted render helpers for base filters, extra filters, action controls, preview, and footer; moved model/derivation/mutation wiring into `useMassEditStageModel`; grouped extra-filter state/errors; added source guard coverage and tri-state trigger label coverage so `any` does not leak into the UI. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "mass edit stage modal sections"` failed on the missing helper split; `pnpm test --run tests/mass-edit-stage-modal.test.tsx -t "friendly labels"` failed on raw tri-state trigger labels. GREEN: `pnpm test --run tests/mass-edit-stage-modal.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "MassEditStageModal\|mass edit stage modal\|immutable sorting in report chart and stage modals"`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues. Full `pnpm test --run` was attempted and is currently blocked by unrelated uncommitted AI source-guard tests in `tests/ai-chat-panel.test.tsx` and `tests/ai-studio-page.test.tsx`. |

Changed-scope command after Batch 161: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 161: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `149`
- Summary: `Bugs 86 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 53 warnings`
- Removed globally since Batch 160: `react-doctor/no-giant-component` for `MassEditStageModal` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-401df0f1-90bd-4bd7-94e1-5cafc090d0d3`

## Batch 162

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `components/ai/AIChatPanel.tsx` | Valid. The AI chat panel mixed stream state, scroll refs, context tracking, message rendering, action approval cards, quick actions, composer controls, and schedule parser mounting in one component. | High | Kept conversation state, streaming handlers, abort/stop behavior, scroll stickiness, approval gating, and schedule-parser state in `AIChatPanel`. Extracted presentational helpers for header, context bar, messages, quick actions, composer, and schedule parser mounting. Preserved the existing decorative close-icon fix and added a source guard requiring the split helpers. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "AI chat panel rendering"` failed on the missing helper split. GREEN: `pnpm test --run tests/ai-chat-panel.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "AI chat"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 162: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 162: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `148`
- Summary: `Bugs 86 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 52 warnings`
- Removed globally since Batch 161: `react-doctor/no-giant-component` for `AIChatPanel` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e449de73-e7e6-467c-b847-9109c8e0b2a3`

## Batch 163

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-useReducer` | `components/surrogates/AddSurrogateTaskDialog.tsx` | Valid. The surrogate task dialog kept title, description, task type, due date/time, recurrence, repeat-until, and validation error as separate state values even though submit and close reset them together. | High | Replaced the individual form setters with `surrogateTaskFormReducer`, preserving the existing required-title, recurring-task validation, trimmed payload, successful-submit reset, and close reset behavior. Added behavior coverage for recurring-task due-date validation and trimmed submit payloads, plus a source guard requiring the reducer shape. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate task form"` failed on the separate `useState` calls. GREEN: `pnpm test --run tests/add-surrogate-task-dialog.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate task form"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 163: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 163: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `147`
- Summary: `Bugs 85 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 52 warnings`
- Removed globally since Batch 162: `react-doctor/prefer-useReducer` for `AddSurrogateTaskDialog` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-db99a808-3f8e-44ba-9019-c834071ef74d`

## Batch 164

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-useReducer` | `components/tasks/AddTaskDialog.tsx` | Valid. The general task dialog mirrored the surrogate task form: title, description, task type, due date/time, recurrence, repeat-until, and validation error reset together on submit and close. | High | Replaced the individual state setters with `taskDialogFormReducer`, preserving recurring-task validation, trimmed optional description, optional due date/time fields, submit reset, and close reset behavior. Added behavior coverage for recurring validation and submit payloads, plus a source guard requiring the reducer shape. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "task dialog form"` failed on the separate `useState` calls. GREEN: `pnpm test --run tests/add-task-dialog.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "task dialog form"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 164: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 164: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `146`
- Summary: `Bugs 84 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 52 warnings`
- Removed globally since Batch 163: `react-doctor/prefer-useReducer` for `AddTaskDialog` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-34762cf0-1649-4ffb-8ad7-c022985c5a23`

## Batch 165

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-useReducer` | `components/surrogates/LogContactAttemptDialog.tsx` | Valid. The contact attempt draft fields (`selectedMethods`, `outcome`, `notes`, `attemptedAt`, and `isBackdating`) reset together, validate together, and submit as one payload. | High | Moved the contact attempt draft into `contactAttemptFormReducer`, preserving multi-method toggles, required method/outcome validation, backdate datetime gating, stale datetime suppression when backdating is off, success toast/tracking, close reset, and mutation-failure draft preservation. Added behavior coverage for those payload and side-effect paths plus a source guard requiring the reducer shape. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "contact attempt form"` failed on the separate `useState` calls. GREEN: `pnpm test --run tests/log-contact-attempt-dialog.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "contact attempt form"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 165: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 165: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `145`
- Summary: `Bugs 83 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 52 warnings`
- Removed globally since Batch 164: `react-doctor/prefer-useReducer` for `LogContactAttemptDialog` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-6829ec0c-0bad-4ef3-95ff-53c28135badf`

## Batch 166

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-useReducer`, `react-doctor/no-giant-component` | `components/ai/ScheduleParserDialog.tsx` | Valid. The parser workflow state changed as a single input/review/success flow, and the same component owned parser input, warnings, editable task table rows, success state, and footer actions. | High | Moved workflow state into `scheduleParserStateReducer`, kept the bulk idempotency key as a handler-only ref, and split input, review, task table, task row, success, and footer rendering into focused helpers. Added behavior coverage for warning-only parse, parse-to-review/create payloads, and cancel reset, plus source guards for reducer state and helper splits. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "schedule parser workflow"` failed on the separate `useState` calls; `pnpm test --run tests/react-regressions-source.test.ts -t "schedule parser rendering"` failed on the monolithic render. GREEN: `pnpm test --run tests/schedule-parser-dialog.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "schedule parser"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 166: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 166: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `143`
- Summary: `Bugs 82 warnings`, `Performance 8 warnings`, `Accessibility 2 warnings`, `Maintainability 51 warnings`
- Removed globally since Batch 165: `react-doctor/prefer-useReducer` and `react-doctor/no-giant-component` for `ScheduleParserDialog` (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-cc88c40e-8ad0-4730-9577-49830898e024`

## Batch 167

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/async-defer-await` | `app/mfa/page.client.tsx` | Valid, with a behavior constraint. The return-target decision does not depend on the completed challenge result, but both redirect branches must still wait for MFA completion and auth refresh before navigation. | High | Created the MFA completion promise, branched on the stored return target, and awaited the challenge plus auth refresh inside each branch before redirecting. This keeps the existing ops invariant covered by tests while moving the early-return guard before the await. | GREEN: `pnpm test --run tests/mfa-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |
| `react-doctor/async-defer-await` | `app/ops/agencies/page.client.tsx` | Needs human review / likely false positive. The post-fetch `isCurrent` guard is the stale-response protection verified by `ops-agencies-page-race.test.tsx`; moving it before the awaited request would not protect late responses. | Medium | Left unchanged and documented. A future cleanup should preserve the existing stale-response test and only change this if the loading model moves to an abortable request or a query library. | Existing coverage: `pnpm test --run tests/ops-agencies-page-race.test.tsx` exercises stale in-flight responses. Not rerun in this batch because no code changed in that file. |

Changed-scope command after Batch 167: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 167: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `142`
- Summary: `Bugs 82 warnings`, `Performance 7 warnings`, `Accessibility 2 warnings`, `Maintainability 51 warnings`
- Removed globally since Batch 166: `react-doctor/async-defer-await` for `MFAPageClient` (`1` warning).
- Remaining reviewed but unchanged: `react-doctor/async-defer-await` for `AgenciesPage` stale-response guard.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-0c2896ba-8066-4dd2-ba9a-733da00ae685`

## Batch 168

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/(app)/dashboard/components/attention-needed-panel.tsx` | Valid. The dashboard attention panel mixed attention data states, view-all popover links, upcoming grouping, loading/empty/error branches, and section rendering inside one component. | High | Kept data fetching and active-section state in `AttentionNeededPanel`, extracted attention/upcoming section headers and content helpers, and moved upcoming section assembly into `buildUpcomingSections`. Reworked the split helper API to use a named upcoming status instead of several boolean props so changed-scope React Doctor stays clean. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "attention needed panel sections"` failed on the monolithic render. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "attention needed panel\\|rendered list keys"`; `pnpm test --run tests/dashboard.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |
| `react-doctor/no-event-handler` | `app/(app)/surrogates/page.client.tsx` | Valid but deferred. Read-only sidecar audit found the search/filter URL effects are true positives, but they share a mirrored URL/filter state model and must not be fixed by blindly moving setters into handlers. | High | Left unchanged for a dedicated future batch. The safe boundary is the surrogates list URL/filter state model plus `apps/web/tests/surrogates.test.tsx` coverage for debounced search, direct-link/back-forward hydration, date filters, chips, fetch params, sorting, page, and priority. | Read-only audit only; no files changed for this finding. |

Changed-scope command after Batch 168: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 168: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `141`
- Summary: `Bugs 82 warnings`, `Performance 7 warnings`, `Accessibility 2 warnings`, `Maintainability 50 warnings`
- Removed globally since Batch 167: `react-doctor/no-giant-component` for `AttentionNeededPanel` (`1` warning).
- Deferred reviewed cluster: `react-doctor/no-event-handler` for `SurrogatesPage` URL/filter state model.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e8865237-1df6-48c9-aff6-eb5e55a516a0`

## Batch 169

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `components/surrogates/SurrogatesFloatingScrollbar.tsx` | Valid. The floating scrollbar component mixed portal markup, thumb rendering, pointer handlers, scroll synchronization, pointer/media detection, metrics calculation, and lifecycle listeners in one component. | High | Extracted the portal, shell, and track rendering helpers, then moved the scroll/listener/controller logic into `useSurrogatesFloatingScrollbarController` so the exported component only renders children and the portal. Existing behavior tests cover active scroll display, parent scrolling, hover activation, idle fade-out, no-overflow/no-fine-pointer suppression, two-way horizontal sync, and native-scrollbar suppression. Added a source guard for the rendering split. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogates floating scrollbar rendering"` failed on the monolithic render. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogates floating scrollbar"`; `pnpm test --run tests/surrogates-floating-scrollbar.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |
| `react-doctor/no-event-handler` | `components/rich-text-editor.tsx` | False positive. The reported lines are Tiptap `useEditor` options for placeholder configuration, optional image extension, initial content/editor attributes, and Tiptap `onUpdate`, not a state-plus-effect event-handler hop. | High | Left unchanged after read-only audit. Any redesign would need editor-specific coverage for placeholder, image enablement, initial content, attributes/min-height, and `onUpdate -> onChange`. | Read-only audit only; no files changed for this finding. |
| `react-doctor/no-event-handler` | `components/ui/calendar.tsx` | Needs human review. The finding matches the rule shape because prop-driven focus is performed in an effect, but the shared calendar focus behavior mirrors the local `react-day-picker@10.0.1` default `DayButton` pattern. Mechanical removal risks keyboard focus and date-picker navigation. | Medium-high | Left unchanged after read-only audit. A future batch should start with keyboard-focus behavior coverage asserting focused-day movement and selection after arrow/month navigation before deciding whether to keep, suppress, or redesign this focus handoff. | Read-only audit only; no files changed for this finding. |

Changed-scope command after Batch 169: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 169: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `140`
- Summary: `Bugs 82 warnings`, `Performance 7 warnings`, `Accessibility 2 warnings`, `Maintainability 49 warnings`
- Removed globally since Batch 168: `react-doctor/no-giant-component` for `SurrogatesFloatingScrollbar` (`1` warning).
- Reviewed but unchanged: `react-doctor/no-event-handler` for `RichTextEditor` Tiptap options, and `Calendar` shared focus management.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-62bd86e4-d81c-434a-a0df-c065e500cdf1`

## Batch 170

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `components/forms/builder/AutomationFormSettingsPanel.tsx` | Valid. The settings panel was a presentational component that owned internal identity fields, logo controls, shared delivery defaults, applicant-facing header copy, QR/share controls, and upload rules in one JSX body. | High | Split the card into focused section helpers: `FormIdentitySection`, `LogoSettingsSection`, `SharedDeliverySection`, `PublicHeaderSection`, `ShareQrSection`, and `UploadRulesSection`. Kept the public prop contract, labels, ids, select label mapping, disabled conditions, QR markup, and file input accessibility unchanged. Added a source guard for the section split. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "automation form settings panel sections"` failed on the monolithic render. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "automation form settings panel sections"`; `pnpm test --run tests/automation-form-settings-panel-accessibility.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 170: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 170: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `139`
- Summary: `Bugs 82 warnings`, `Performance 7 warnings`, `Accessibility 2 warnings`, `Maintainability 48 warnings`
- Removed globally since Batch 169: `react-doctor/no-giant-component` for `AutomationFormSettingsPanel` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-073cb45c-5b72-4329-8a78-4d5c70607666`

## Batch 171

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/(app)/settings/compliance/page.tsx` | Valid. The compliance settings page mixed the page frame, retention policy table, legal hold form/table/pagination, and developer purge card in one component. | High | Kept auth, query, mutation, and local form state ownership in `ComplianceSettingsPage`, and split the markup into same-file helpers for `CompliancePageHeader`, `RetentionPoliciesCard`, `LegalHoldsCard`, and `RetentionPurgeCard`. Added a source guard so the page component stays focused. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "compliance settings page sections"` failed on the monolithic render. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "compliance settings page sections"`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; full React Doctor dropped to `138` issues. |
| `react-doctor/no-event-handler` | `app/(app)/settings/compliance/page.tsx:537` | Needs human review. The effect clamps `holdsPage` after `legalHolds.pages` changes. Normal UI pagination already clamps page changes, but the effect is defensive against external/server-side list shrink. Removing it is product-sensitive and not required for this structural split. | Medium | Left unchanged after read-only audit. A future behavior-changing batch should start with focused compliance page tests for legal hold pagination, shrinking page counts, create-hold reset, release clicks, and policy save payloads. | Changed-scope React Doctor still reports this one existing finding in the changed file. |

Changed-scope command after Batch 171: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `1`
- Summary: `Bugs 1 warning`
- Remaining reviewed but unchanged: `react-doctor/no-event-handler` for the compliance legal-holds page clamp.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-44c1b93e-2e75-4f10-afb0-18eac12f0464`

Full command after Batch 171: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `138`
- Summary: `Bugs 82 warnings`, `Performance 7 warnings`, `Accessibility 2 warnings`, `Maintainability 47 warnings`
- Removed globally since Batch 170: `react-doctor/no-giant-component` for `ComplianceSettingsPage` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-b91cb783-30cd-4d5f-a011-02e5a6369618`

## Batch 172

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/rerender-state-only-in-handlers` | `components/intended-parents/IntendedParentClinicCard.tsx`, `components/surrogates/CombinedMedicalInsuranceCard.tsx` | False positives reconfirmed. Both cards read the flagged section-visibility state during render to build `visibleKeys`, `hiddenKeys`, and rendered section lists. A local ref rewrite attempt for `CombinedMedicalInsuranceCard` proved invalid because React Compiler correctly rejected reading `ref.current` during render. | High | Kept the visibility values in state and added a source guard for `CombinedMedicalInsuranceCard` so future cleanup does not convert render-driving section visibility into refs. No suppression or config change. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate medical hidden-section"` failed against the current state shape when the guard expected a ref, and changed-scope React Doctor then reported a React Compiler ref-read error after the attempted rewrite. GREEN: reverted the invalid rewrite and changed the guard to preserve render state; `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate medical section visibility\|surrogate card, task calendar"`; `pnpm test --run tests/surrogate-detail.test.tsx -t "saves PCP name\|allows deleting a visible section"`. |
| `react-doctor/no-giant-component` | `app/(app)/tasks/page.client.tsx` | Valid. `TasksPage` owned route param parsing, task queries, approval queries, modal state, selection handlers, recurrence creation, focus coordination, and the full page render in one component body. | High | Moved hook/query/effect/handler ownership into `useTasksPageController`, then split rendering into `TasksPageHeader`, `TasksPageControls`, `TasksPageContent`, and `TasksPageDialogs`. Left the existing focus coordination effect unchanged because it remains a separate URL/focus state-model warning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "Tasks page rendering split"` failed on the monolithic page. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "Tasks page"`; `pnpm test --run tests/tasks-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full `pnpm test --run`; full React Doctor dropped to `137` issues. |
| `react-doctor/prefer-tag-over-role`, `react-doctor/async-await-in-loop`, `react-doctor/query-mutation-missing-invalidation` | `components/email/EmailComposeDialog.tsx`, `components/surrogates/interviews/InterviewComments/TranscriptPane.tsx`, `components/surrogates/interviews/InterviewTab/context.tsx`, sampled hooks | Reviewed but unchanged. The email and transcript surfaces are rich editable/selectable HTML rather than safe native input/button swaps; the interview upload loop stops on the first failed upload; sampled remaining mutation warnings are preview/test/redirect/staged-data mutations already logged as no-ops or false positives. | Medium-high | Left unchanged and continued with the higher-confidence tasks-page split instead of adding noisy invalidations or changing product semantics for score. | Source and triage validation only; no files changed for these findings. |

Changed-scope command after Batch 172: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `1`
- Summary: `Bugs 1 warning`
- Remaining reviewed but unchanged: `react-doctor/no-event-handler` for `TasksPage` focus/list-view coordination.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e454aa3f-6c4e-465c-91d7-65cea13fccf6`

Full command after Batch 172: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `137`
- Summary: `Bugs 82 warnings`, `Performance 7 warnings`, `Accessibility 2 warnings`, `Maintainability 46 warnings`
- Removed globally since Batch 171: `react-doctor/no-giant-component` for `TasksPage` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4beed628-f38d-4174-bd6f-9b9dcc4425da`

## Batch 173

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/(app)/settings/queues/page.tsx` | Valid. `QueuesSettingsPage` owned admin redirect, queue/member hooks, create/edit/member dialog state, table rendering, empty/loading/error states, form markup, and member-management markup in one component body. | High | Kept hook ownership and all mutations in `QueuesSettingsPage`, then split rendering into `QueuesPageHeader`, `QueuesStatusContent`, `QueuesTable`, `QueueFormDialog`, and `QueueMembersDialog`. Added a source guard requiring the split and keeping table/dialog JSX out of the page component body. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "queues settings rendering"` failed on the monolithic page. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "queue edit target\|queues settings rendering"`; `pnpm test --run tests/queues-settings-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues; full React Doctor dropped to `136` issues. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-user-integrations.ts`, sampled mutation hooks | Reviewed but unchanged. The sampled warnings were OAuth URL fetches followed by redirect, test/preview/dry-run mutations, staged profile sync, parser preview, and test-send calls. Adding unrelated invalidations would hide warnings without proving stale-cache behavior. | Medium-high | Left unchanged. Future fixes should target a persisted mutation with a concrete stale query key, not validation/auth-url/preview calls. | Read-only source audit only; no files changed for these findings. |
| `react-doctor/no-event-handler`, `react-doctor/prefer-tag-over-role`, `react-doctor/async-await-in-loop` | `app/(app)/automation/email-templates/page.tsx`, URL-sync pages, rich-text/transcript/calendar integrations, `components/surrogates/interviews/InterviewTab/context.tsx` | Mixed. One email-template preview close handler looks like a safe future event-handler fix, but most reviewed findings are URL/back-forward sync, fetched-data hydration, DOM/editor integration, rich contenteditable/transcript semantics, or sequential upload behavior that need dedicated behavior coverage. | Medium | Left unchanged in this queue-structure batch. Use a separate focused batch for the email-template preview close handler or the appointment-dialog reducer candidate. | Read-only sidecar audit only; no files changed for these findings. |

Changed-scope command after Batch 173: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 173: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `136`
- Summary: `Bugs 82 warnings`, `Performance 7 warnings`, `Accessibility 2 warnings`, `Maintainability 45 warnings`
- Removed globally since Batch 172: `react-doctor/no-giant-component` for `QueuesSettingsPage` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-2d2fe314-52bb-4d67-befa-62629f6ea110`

## Batch 174

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-event-handler` | `app/(app)/automation/email-templates/page.tsx:824` | Valid. Closing the email preview used `onOpenChange={setShowPreview}` and a `useEffect` watching `showPreview` to clear `libraryPreviewId`, so library-preview cleanup ran one render late. | High | Added `handlePreviewOpenChange`, moved `setLibraryPreviewId(null)` into the preview close handler, and removed the close-cleanup effect. Added behavior coverage that closes a platform-library preview and then opens a personal-template preview without reusing library content, plus a source guard preventing the effect pattern from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "email library preview"` failed on the effect-driven cleanup. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "email library preview"`; `pnpm test --run tests/email-templates-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full React Doctor dropped to `135` issues. |
| `react-doctor/no-event-handler`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/automation/email-templates/page.tsx` | Valid but broader than this batch. Changed-scope still reports the page-level structural/reducer warnings and two other effect-driven paths for test-send defaults/template variable hydration, which require a separate state-model pass. | Medium-high | Left unchanged to keep this commit focused on the preview-close event path. | Changed-scope React Doctor after the fix reports `4` existing warnings in the changed file: `no-giant-component`, `prefer-useReducer`, and `no-event-handler` at the remaining effect paths. |

Changed-scope command after Batch 174: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `4`
- Summary: `Bugs 3 warnings`, `Maintainability 1 warning`
- Remaining reviewed but unchanged: `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer`, and two existing `react-doctor/no-event-handler` warnings in `EmailTemplatesPage`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-735ed8ba-73cb-4610-a77a-2ef1d2843d34`

Full command after Batch 174: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `135`
- Summary: `Bugs 81 warnings`, `Performance 7 warnings`, `Accessibility 2 warnings`, `Maintainability 45 warnings`
- Removed globally since Batch 173: `react-doctor/no-event-handler` for the email library preview close cleanup (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-fdbd55de-2ad9-4e1f-99f3-9afd226f0143`

## Batch 175

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-useReducer`, `react-doctor/no-giant-component` | `components/appointments/AppointmentsList.tsx` | Valid. `AppointmentDetailDialog` reset six related draft fields together on open, then also owned detail status/date/format/client rendering, cancel form, reschedule slot picker, and action footer in one component body. | High | Added `appointmentDetailDialogReducer` for cancel/reschedule draft state and split rendering into `AppointmentStatusSummary`, `AppointmentTimeSummary`, `AppointmentFormatSummary`, `AppointmentClientInfo`, `AppointmentCancelForm`, `AppointmentRescheduleForm`, and `AppointmentDetailActions`. Kept appointment data fetching and mutations in the exported dialog. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "appointment detail dialog state"` failed on the separate state fields and missing helpers. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "appointment detail dialog state"`; `pnpm test --run tests/appointments-google-meet.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues; full React Doctor dropped to `133` issues. |

Changed-scope command after Batch 175: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 175: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `133`
- Summary: `Bugs 80 warnings`, `Performance 7 warnings`, `Accessibility 2 warnings`, `Maintainability 44 warnings`
- Removed globally since Batch 174: `react-doctor/prefer-useReducer` and `react-doctor/no-giant-component` for `AppointmentDetailDialog` (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-dc75d3ef-9558-4cf2-bf0c-4d473536a0f6`

## Batch 176

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-dynamic-import` | `components/ui/chart.tsx` | Valid. The shared chart wrapper eagerly imported all of `recharts`, even though chart-heavy dashboard and reporting surfaces already load their canvases dynamically. | High | Replaced the static `RechartsPrimitive` import with a dynamic `ChartResponsiveContainer`. Kept Recharts `Tooltip` and `Legend` as direct children inside each already-dynamic chart canvas so Recharts child detection remains intact, and removed the shared eager tooltip/legend exports. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "Recharts own responsive chart sizing"` failed on the static import. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "Recharts own responsive chart sizing"`; `pnpm test --run tests/chart-container.test.tsx`; `pnpm test --run tests/dashboard.test.tsx tests/reports-page.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "chart"`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues; full React Doctor dropped to `132` issues. |

Changed-scope command after Batch 176: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 176: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `132`
- Summary: `Bugs 80 warnings`, `Performance 6 warnings`, `Accessibility 2 warnings`, `Maintainability 44 warnings`
- Removed globally since Batch 175: `react-doctor/prefer-dynamic-import` for `components/ui/chart.tsx` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4c9894e0-70a0-4e24-ad8e-3f679e6c4bae`

## Batch 177

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-event-handler` | `app/(app)/automation/email-templates/page.tsx:833` | Valid but redundant with the open handler. `handleOpenTestDialog` already set `testSendToEmail` from `user?.email`, while a later effect watched dialog state and set the same field one render late when empty. | High | Strengthened the send-test dialog test to assert the visible `To email` default, added a source guard requiring the default to stay in `handleOpenTestDialog`, and removed the redundant effect. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "email test recipient"` failed on `setTestSendToEmail(user.email)` in the effect. GREEN: `pnpm test --run tests/email-templates-page.test.tsx -t "shows send test email action"`; `pnpm test --run tests/react-regressions-source.test.ts -t "email test recipient"`; `pnpm test --run tests/email-templates-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full React Doctor dropped to `131` issues. |
| `react-doctor/no-event-handler`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/automation/email-templates/page.tsx` | Valid but separate. Changed-scope still reports the template variable hydration effect and the page-level structure/reducer warnings, which need a broader state-model split. | Medium-high | Left unchanged to keep this commit scoped to the visible test-recipient default. | Changed-scope React Doctor after the fix reports `3` existing warnings in the changed file: `no-giant-component`, `prefer-useReducer`, and `no-event-handler` at the variable hydration effect. |

Changed-scope command after Batch 177: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `3`
- Summary: `Bugs 2 warnings`, `Maintainability 1 warning`
- Remaining reviewed but unchanged: `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer`, and the separate `react-doctor/no-event-handler` warning for test variable hydration.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-485a49a9-025c-4944-ab94-faaae73a5bff`

Full command after Batch 177: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `131`
- Summary: `Bugs 79 warnings`, `Performance 6 warnings`, `Accessibility 2 warnings`, `Maintainability 44 warnings`
- Removed globally since Batch 176: `react-doctor/no-event-handler` for send-test recipient defaulting (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1856141c-cfab-4576-8494-7952a6309d72`

## Batch 178

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/async-defer-await` | `app/ops/agencies/page.client.tsx:90` | Valid. The stale-response guard ran only after awaiting `listOrganizations`, so React Doctor saw an avoidable await before the early-return path. The guard still must run after the request resolves to protect search races. | High | Replaced the inner `async function fetchAgencies` with a direct `void listOrganizations(...).then(...).catch(...)` continuation. Kept the existing `isCurrent` checks before success/error dispatches. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "smaller ops pages"` failed on `const data = await listOrganizations`. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "smaller ops pages"`; `pnpm test --run tests/ops-agencies-page-race.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues; full React Doctor dropped to `130` issues. |
| `react-doctor/rerender-state-only-in-handlers` | `components/intended-parents/IntendedParentClinicCard.tsx:278-279` | False positive. `manuallyAddedSections` and `optimisticallyHiddenSections` are render-driving state: they feed `visibleKeys`/`hiddenKeys`, and `visibleSections` controls which clinic sections render. | High | Left unchanged. Do not convert these values to refs. | Sidecar read-only inspection plus existing coverage: source guard `uses single-pass intended-parent clinic section derivation`; behavior test `adds an IVF clinic section even when no IVF clinic data exists`. |
| `react-doctor/rerender-state-only-in-handlers` | `components/surrogates/CombinedMedicalInsuranceCard.tsx:191-192` | False positive. `manuallyAdded` and `optimisticallyHiddenSections` are render-driving state: they feed `visibleKeys`/`hiddenKeys`, and `visibleSections` controls which medical/insurance sections render. | High | Left unchanged. A prior ref conversion was invalid because this visibility is read during render. | Sidecar read-only inspection plus existing source guard `keeps surrogate medical section visibility in render state` and behavior coverage for adding/deleting medical sections. |
| `react-doctor/prefer-tag-over-role` | `components/email/EmailComposeDialog.tsx:898` | False positive for direct tag replacement. The `div role="textbox"` is a real `contentEditable` rich preview editor backed by an `HTMLDivElement` ref and `innerHTML` sync; the native `<textarea>` is the separate HTML edit mode. | High | Left unchanged. Replacing this with `<input>` or `<textarea>` would break preview-mode rich HTML editing. | Sidecar read-only inspection plus existing coverage: `allows customizing message directly in preview mode without toggling to html editor` and source guard `keeps email compose dialog derived state compiler-friendly`, which intentionally preserves `role="textbox"` and `contentEditable`. |
| `react-doctor/prefer-tag-over-role` | `components/surrogates/interviews/InterviewComments/TranscriptPane.tsx:106` | Needs human review. The warning is on a transcript wrapper with `role="button"`, not `role="textbox"`. It wraps sanitized rich transcript HTML and drives click, hover, keyboard, and selection-popover behavior; a native `<button>` wrapper would be invalid for paragraphs/lists/code blocks and could harm text selection. | Medium-high | Left unchanged. If product wants different semantics, define whether this is a selectable region or per-highlight keyboard controls first, then update tests and implementation together. | Sidecar read-only inspection plus existing coverage: `adds an aria-label to the interview transcript pane` currently expects the button role, and selection-popover tests cover selected transcript text handling. |

Changed-scope command after Batch 178: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 178: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `130`
- Summary: `Bugs 79 warnings`, `Performance 5 warnings`, `Accessibility 2 warnings`, `Maintainability 44 warnings`
- Removed globally since Batch 177: `react-doctor/async-defer-await` for the ops agencies list loader (`1` warning).
- Invalid findings logged: `react-doctor/rerender-state-only-in-handlers` for intended-parent clinic and surrogate medical section visibility, and `react-doctor/prefer-tag-over-role` for rich email preview/transcript interaction surfaces (`4` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4c220fc0-58f1-4c43-9205-9173caeb69ad`

## Batch 179

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/async-await-in-loop` | `components/surrogates/interviews/InterviewTab/context.tsx:340` | Valid. Valid attachment uploads are independent, but the provider awaited each upload before starting the next one. | High | Added a behavior test proving two valid uploads start before the first promise resolves. Changed `uploadFiles` to validate files first, then start valid uploads together with `Promise.all`. Kept the existing upload input reset behavior. | RED: `pnpm test --run tests/interview-tab.test.tsx -t "starts valid attachment uploads"` failed with only one upload call while the first promise was pending. GREEN: `pnpm test --run tests/interview-tab.test.tsx -t "starts valid attachment uploads"`; `pnpm test --run tests/react-regressions-source.test.ts -t "interview tab context"`; `pnpm test --run tests/interview-tab.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; full React Doctor dropped to `129` issues. |
| `react-doctor/no-giant-component` | `components/surrogates/interviews/InterviewTab/context.tsx:164` | Valid but separate. The provider still owns selection, dialogs, form state, mutations, uploads, notes, and transcription in one context component. | Medium-high | Left unchanged to keep this commit focused on upload concurrency. | Changed-scope React Doctor after the fix reports only this existing maintainability warning in the changed file. |

Changed-scope command after Batch 179: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Remaining reviewed but unchanged: `react-doctor/no-giant-component` for `InterviewTabProvider`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-7bf29161-b649-4f77-b2d1-07cdb01f81a8`

Full command after Batch 179: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `129`
- Summary: `Bugs 79 warnings`, `Performance 4 warnings`, `Accessibility 2 warnings`, `Maintainability 44 warnings`
- Removed globally since Batch 178: `react-doctor/async-await-in-loop` for interview attachment uploads (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-5cec0925-f83e-4055-a430-0b95e89c2189`

## Batch 180

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/(app)/tickets/[ticketId]/page.tsx` | Valid. `TicketDetailPage` owned developer gating, data/mutations, status/priority/link state, reply form, notes form/list, and message attachment rendering in one component body. | High | Kept data loading, state, and mutation handlers in `TicketDetailPage`, then split rendering into `TicketOverviewCard`, `TicketReplyCard`, `TicketNotesCard`, and `TicketMessagesCard`. Added a source guard keeping the section JSX out of the page body. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "ticket detail page rendering"` failed on the monolithic page. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "ticket detail page rendering"`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor reported no issues; full React Doctor dropped to `128` issues. |

Changed-scope command after Batch 180: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose --scope changed`

- Score: unavailable because the score API was unreachable.
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 180: `cd apps/web && node /Users/chason/.npm/_npx/81e833f6d16d6127/node_modules/react-doctor/bin/react-doctor.js . --verbose`

- Score: unavailable because the score API was unreachable.
- Total diagnostics: `128`
- Summary: `Bugs 79 warnings`, `Performance 4 warnings`, `Accessibility 2 warnings`, `Maintainability 43 warnings`
- Removed globally since Batch 179: `react-doctor/no-giant-component` for `TicketDetailPage` (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-791514f6-5775-4322-a096-69d538f2641a`

## Batch 181

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/js-set-map-lookups` | `app/(app)/settings/team/members/[id]/page.client.tsx:62`, `:68`, `:71`, `:268` | Valid. The add-override dialog checked the same override/effective-permission arrays while filtering permissions, and the page checked pending removals while deriving displayed overrides. | High | Converted membership checks to `Set.has` via `existingOverrideKeys`, `effectivePermissionKeys`, and `pendingOverrideRemovals`. Added a source guard preventing the old `includes` calls from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "team member permission membership"` failed on missing Set derivations. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "team member"`; `pnpm tsc --noEmit`; combined changed-scope React Doctor after Batch 183 reported no issues. |
| `react-doctor/no-giant-component` | `app/(app)/settings/team/members/[id]/page.client.tsx:173` | Valid. `MemberDetailPage` owned route params, member mutations, pending role/override state, profile rendering, permission override rendering, and danger-zone rendering in one component body. | High | Kept route/data/mutation state in `MemberDetailPage`, then split rendering into `MemberDetailToolbar`, `MemberProfileCard`, `PermissionOverridesCard`, and `DangerZoneCard`. Added a source guard keeping section JSX out of the page body. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "team member detail rendering"` failed on the monolithic render. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "team member"`; `pnpm tsc --noEmit`; combined changed-scope React Doctor after Batch 183 reported no issues. |

Commit: `f7c9d16d refactor: Split team member detail`

## Batch 182

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-array-index-as-key` | `components/email/EmailComposeDialog.tsx:199`, `:203` | Valid. Template-highlight spans were keyed with `${index}:${part}`, so repeated template fragments could still depend on list position. | High | Replaced split/map rendering with `getHighlightedTemplateParts`, which tokenizes variable and text spans with source-position keys such as `text:0:12` and `variable:12:26`. Added a source guard preventing index-key rendering from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "keeps email compose dialog derived state compiler-friendly"` failed before the fix. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "email compose dialog"`; `pnpm test --run tests/email-compose-dialog.test.tsx`; `pnpm tsc --noEmit`; combined changed-scope React Doctor after Batch 183 reported no issues. |

Commit: `d59e6446 fix: Stabilize email template highlight keys`

## Batch 183

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/control-has-associated-label` | `components/forms/PublicFormFieldRenderer.tsx:369` | Valid. Fixed-table select controls had visible column text, but the label was not associated with the native `select`. | High | Added stable `fieldInputId`/`fieldInputLabelId`, wired `Label htmlFor`, `select id`, and `aria-labelledby`, and gave sibling text inputs the same id for consistency. Added a behavior test that finds the select by its visible `Response` label and changes it. | GREEN: `pnpm test --run tests/public-form-field-renderer.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "React Doctor-reported select controls"`; `pnpm tsc --noEmit`; combined changed-scope React Doctor reported no issues. |
| `react-doctor/control-has-associated-label` | `app/intake/[slug]/page.client.tsx:1298` | False positive. The hosted intake fixed-table select already has `Label htmlFor={fieldInputId}` and `<select id={fieldInputId} name={fieldInputName}>`. | High | Left unchanged and added a source guard documenting the existing label association. | Verified by source inspection and `pnpm test --run tests/react-regressions-source.test.ts -t "React Doctor-reported select controls"`. |
| `react-doctor/control-has-associated-label` | `components/intended-parents/IntendedParentFormFields.tsx:38`, `:69` | False positive. Both select wrappers render `<Label htmlFor={id}>` with a matching `<select id={id}>`. | High | Left unchanged and added a source guard documenting the existing label association. | Verified by source inspection and `pnpm test --run tests/react-regressions-source.test.ts -t "React Doctor-reported select controls"`. |
| `react-doctor/js-set-map-lookups` | `components/forms/PublicFormFieldRenderer.tsx:718` | Valid. Multiselect options checked `selectedValues.includes(option.value)` inside the options loop. | High | Added `selectedValueSet` and switched the loop membership check to `selectedValueSet.has(option.value)`. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "React Doctor-reported select controls"` failed on the old `includes` path. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "React Doctor-reported select controls"`; `pnpm test --run tests/public-form-field-renderer.test.tsx`; combined changed-scope React Doctor reported no issues. |

Commit: `8488e393 fix: Label public form table selects`

Changed-scope command after Batch 183: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 183: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `84 / 100`
- Total diagnostics: `108`
- Summary: `Bugs 50 warnings`, `Performance 15 warnings`, `Accessibility 4 warnings`, `Maintainability 39 warnings`
- Removed globally since the current-pass baseline: `react-doctor/no-array-index-as-key` for email template highlights (`2` warnings), `react-doctor/control-has-associated-label` for public fixed-table selects (`1` warning), `react-doctor/js-set-map-lookups` for team-member/public-form membership checks (`5` warnings), and `react-doctor/no-giant-component` for `MemberDetailPage` (`1` warning).
- Invalid findings logged: hosted intake fixed-table select label, intended-parent role/state select labels (`3` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-098bcf65-385f-4202-a662-3e072d5971bb`

## Batch 184

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/js-set-map-lookups` | `app/ops/templates/system/new/page.client.tsx:239` | Valid. Template validation derived `usedVariableNames` once, then checked every variable with `includes` while rendering unknown-variable warnings. | High | Added `usedVariableNamesSet` and switched variable membership checks to `Set.has`. Added a source guard preventing the old `includes` path from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "platform template variable validation"` failed before the Set conversion. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "platform"`; `pnpm test --run tests/platform-system-email-template-new-page.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor after Batch 185 reported no issues. |
| `react-doctor/no-giant-component` | `app/ops/templates/system/new/page.client.tsx:186` | Valid. `PlatformSystemEmailTemplateNewPage` owned system-key validation, form state, variable selection, validation warnings, preview rendering, and save flow in one component body. | High | Kept page-level state and mutation handling in `PlatformSystemEmailTemplateNewPage`, then split rendering into `TemplateCreateHeader`, `TemplateSettingsCard`, `TemplateContentCard`, `TemplateVariableWarnings`, and `TemplatePreviewCard`. Added a source guard keeping section JSX out of the page body. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "platform system template creation rendering"` failed on the monolithic render. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "platform"`; `pnpm test --run tests/platform-system-email-template-new-page.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor after Batch 185 reported no issues. |

## Batch 185

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/js-set-map-lookups` | `app/(app)/settings/integrations/meta/page.client.tsx:199`, `:205`, `:269`, `:301` | Valid. Asset selection checked selected ad-account/page id arrays repeatedly while deriving conflicts and checkbox state. | High | Added `selectedAdAccountIds` and `selectedPageIds` Sets, then switched conflict checks and checkbox state to `Set.has`. Added a source guard preventing the old `includes` calls from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "Meta asset selection membership"` failed before the Set conversion. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "Meta integration page state\|Meta asset selection membership"`; `pnpm test --run tests/meta-integrations-page.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor reported no issues. |
| `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer` | `app/(app)/settings/integrations/meta/page.client.tsx:392` | Valid. `MetaIntegrationPage` owned OAuth connection actions, reauth/error alerts, asset-selection routing, ad-account table rendering, edit-dialog draft fields, and disconnect confirmation in one component body. The edit dialog reset five related draft fields together. | High | Added `metaAccountEditReducer` for edit-dialog state and split rendering into `MetaIntegrationHeader`, `MetaConnectionsCard`, `MetaConnectionAlerts`, `MetaAdAccountsCard`, `EditAdAccountDialog`, and `DisconnectMetaConnectionDialog`. Added a source guard keeping section JSX and field setters out of the page body. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "Meta integration page state"` failed on the missing reducer/helpers. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "Meta integration page state\|Meta asset selection membership"`; `pnpm test --run tests/meta-integrations-page.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "platform\|Meta"`; `pnpm test --run tests/platform-system-email-template-new-page.test.tsx tests/meta-integrations-page.test.tsx`; `pnpm tsc --noEmit`; `git diff --check`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 185: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 185: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `84 / 100`
- Total diagnostics: `100`
- Summary: `Bugs 49 warnings`, `Performance 10 warnings`, `Accessibility 4 warnings`, `Maintainability 37 warnings`
- Removed globally since Batch 183: system template variable Set and page split (`2` warnings), Meta asset Sets (`4` warnings), and Meta page reducer/render split (`2` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a5b3ed21-b1a0-4a49-bf44-dede907d1e0d`

## Batch 186

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-forms.ts:518` | False positive. `useUploadFormLogo` uploads an asset and returns a URL for the draft editor; the persisted form cache changes only on a later save mutation. | High | Left unchanged. Do not add a dummy invalidation. | Read-only hook/source inspection by sidecar agent. Suggested regression surface if edited later: `pnpm test --run tests/form-builder-page.test.tsx tests/use-mutation-invalidations.test.ts`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-import.ts:198` | False positive. `useAiMapImport` returns one-shot AI mapping suggestions and does not mutate persisted import state. | High | Left unchanged. | Read-only hook/source inspection by sidecar agent. Suggested regression surface if edited later: `pnpm test --run tests/csv-upload-created-at.test.tsx tests/meta-form-mapping-page.test.tsx`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-meta-oauth.ts:38` | False positive. `useMetaConnectUrl` fetches an OAuth URL and sets redirect state; durable connection state changes on callback, not in this mutation. | High | Left unchanged. | Read-only hook/source inspection by sidecar agent. Suggested regression surface if edited later: `pnpm test --run tests/integrations-page.test.tsx tests/meta-integrations-page.test.tsx`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-mfa.ts:91` | False positive. `useInitiateDuoAuth` starts a Duo redirect flow; MFA/Duo status changes on callback. | High | Left unchanged. | Read-only hook/source inspection by sidecar agent. Suggested regression surface if edited later: `pnpm test --run tests/security-settings-page.test.tsx tests/mfa-page.test.tsx tests/duo-callback-page.test.tsx`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-pipelines.ts:200` | False positive. `useRecommendedPipelineDraft` lazily fetches a recommended draft and the consumer stores it in local editor state. | High | Left unchanged. | Read-only hook/source inspection by sidecar agent. Suggested regression surface if edited later: `pnpm test --run tests/pipelines-settings-page.test.tsx`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-platform-templates.ts:348` | False positive. `useSendPlatformSystemEmailCampaign` sends an email/log action but does not mutate template/detail/branding caches, and there is no owned query-backed campaign/log cache here. | Medium-high | Left unchanged. | Read-only hook/source inspection by sidecar agent. Suggested regression surface if edited later: `pnpm test --run tests/platform-system-email-template-page.test.tsx`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-profile.ts:29` | False positive. `useSyncProfile` returns a staged diff only; the later save mutation persists and invalidates `profileKeys.detail`. | High | Left unchanged. | Read-only hook/source inspection by sidecar agent. Suggested regression surface if edited later: `pnpm test --run tests/use-mutation-invalidations.test.ts tests/react-regressions-source.test.ts`. |
| `react-doctor/query-mutation-missing-invalidation` | `lib/hooks/use-schedule-parser.ts:17` | False positive. `useParseSchedule` parses text into proposed tasks; `useCreateBulkTasks` is the actual write and already invalidates task/surrogate caches. | High | Left unchanged. | Read-only hook/source inspection by sidecar agent. Suggested regression surface if edited later: `pnpm test --run tests/schedule-parser-dialog.test.tsx tests/use-mutation-invalidations.test.ts`. |

## Batch 187

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/js-set-map-lookups` | `app/(app)/automation/ai-builder/page.client.tsx:208` | Valid. Required template variables were filtered against `templateVariables.includes(required)` while validating generated template output. | High | Added `templateVariableNameSet` and switched the membership check to `Set.has`. Extended the AI builder source guard to keep the Set conversion. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "AI builder template derivations"` failed before the Set conversion. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "AI builder"`; `pnpm test --run tests/ai-builder-page.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor reported no issues after the full split. |
| `react-doctor/prefer-useReducer`, `react-doctor/no-giant-component` | `app/(app)/automation/ai-builder/page.client.tsx:131` | Valid. `AIWorkflowBuilderPage` reset and populated workflow/template generation fields in related setter clusters, then rendered the header, prompt card, alerts, workflow preview, template preview, and empty-state guidance in one component body. | High | Added `workflowGenerationReducer` and `templateGenerationReducer`; split rendering into `AIBuilderHeader`, `PromptComposerCard`, `GenerationAlerts`, `WorkflowPreviewCard`, `EmailTemplatePreviewCard`, and `AIBuilderInfoCard`; then moved shell wiring to `AIBuilderPageShell`. Updated source guards for the reducer split and stable-key assertions after the alert helper renamed local arrays. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "AI builder"` failed on missing reducer/helper boundaries. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "AI builder"`; `pnpm test --run tests/ai-builder-page.test.tsx`; `pnpm tsc --noEmit`; `git diff --check`; changed-scope React Doctor reported no issues. |
| `react-doctor/no-many-boolean-props` | `app/(app)/automation/ai-builder/page.client.tsx:538` | Valid transient finding introduced during the shell extraction. `AIBuilderPageShell` initially received separate permission, loading, saving, and validation booleans. | High | Grouped those flags into named `permissions`, `status`, `templateValidation`, and `templateCatalog` objects. | Changed-scope React Doctor went from `1` boolean-props warning to no issues after grouping. |

Changed-scope command after Batch 187: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 187: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `84 / 100`
- Total diagnostics: `97`
- Summary: `Bugs 48 warnings`, `Performance 9 warnings`, `Accessibility 4 warnings`, `Maintainability 36 warnings`
- Removed globally since Batch 185: AI builder template variable Set conversion (`1` warning), AI builder reducer split (`1` warning), and AI builder page split (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-78b1f227-8f0f-4469-a484-b4cc2229896e`

## Batch 188

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/js-set-map-lookups` | `app/(app)/automation/email-templates/page.tsx:870` | Valid. Required template variables were filtered with `usedVariableNames.includes(variable)` while validating the email template modal. | High | Added `usedVariableNamesSet` and switched required-variable membership checks to `Set.has`. Extended the automation derived-list source guard. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "platform template variable validation\|automation and AI derived lists\|platform email-template edit"` failed before the Set conversion. GREEN: same source guard command; `pnpm test --run tests/email-templates-page.test.tsx tests/platform-system-email-template-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`. |
| `react-doctor/js-set-map-lookups` | `app/ops/templates/system/[systemKey]/page.client.tsx:433` | Valid. Required system-template variables were filtered with `usedVariableNames.includes(variable)`, the same pattern already fixed in the system-template create page. | High | Added `usedVariableNamesSet` and switched required-variable membership checks to `Set.has`. Extended the platform template source guard. | GREEN: source guards, platform system template page tests, TypeScript, lint, and diff check as above. |
| `react-doctor/js-set-map-lookups` | `app/ops/templates/email/[id]/page.client.tsx:602` | False positive in the current tree. Required-variable validation already used `usedVariableNamesSet.has(variable)`; the remaining `usedVariableNames.includes("unsubscribe_url")` is a single standalone check, not a lookup inside a loop. | High | Left unchanged and kept the existing source guard preserving the Set conversion while allowing the standalone unsubscribe check. | Full React Doctor after the batch no longer listed this file under `js-set-map-lookups`. |

Changed-scope command after Batch 188: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `91 / 100`
- Total diagnostics in changed files: `5`
- Summary: `Bugs 2 warnings`, `Maintainability 3 warnings`
- Remaining valid but separate in touched files: `react-doctor/no-event-handler`, `react-doctor/no-giant-component`, `react-doctor/prefer-useReducer`, and `react-doctor/jsx-max-depth` in the broader email-template/system-template pages.

Full command after Batch 188: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `84 / 100`
- Total diagnostics: `94`
- Summary: `Bugs 48 warnings`, `Performance 6 warnings`, `Accessibility 4 warnings`, `Maintainability 36 warnings`
- Removed globally since Batch 187: required-variable Set conversions for automation email templates and system-template detail, plus the now-cleared platform email-template detail Set false positive (`3` warnings).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-df39d82f-7cd4-41cf-b479-05508486796e`

## Batch 188

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/js-set-map-lookups` | `app/ops/templates/email/[id]/page.client.tsx:602` | Valid. Required platform email-template variables were filtered against `usedVariableNames.includes(variable)`. The adjacent `unsubscribe_url` membership check is not inside a loop and remains appropriate as an ordinary one-off lookup. | High | Added `usedVariableNamesSet` and switched the required-variable check to `Set.has`. Added a source guard that keeps the Set conversion while explicitly preserving the one-off `unsubscribe_url` includes check. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "platform email-template edit page"` failed before the Set conversion. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "platform email-template edit page"`; `pnpm test --run tests/platform-email-template-page.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor reported no issues. |

Changed-scope command after Batch 188: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 188: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `84 / 100`
- Total diagnostics: `96`
- Summary: `Bugs 48 warnings`, `Performance 8 warnings`, `Accessibility 4 warnings`, `Maintainability 36 warnings`
- Removed globally since Batch 187: ops platform email template required-variable Set conversion (`1` warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-beff8aae-eab2-4bf9-9fd6-5de7fd4481c3`

## Batch 189

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/js-set-map-lookups` | `app/(app)/automation/campaigns/page.tsx:877`, `app/(app)/automation/campaigns/page.tsx:994` | Valid. The campaign create wizard rendered stage and state checkbox lists while checking selected array membership inside each loop. | High | Added `selectedStageIdSet` and `selectedStateCodeSet`, then switched the checkbox checked state to `Set.has`. Added a source guard preventing the old `includes` checks from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "campaign selection checkbox"` failed before the Set conversion. GREEN: same source guard command; `pnpm test --run tests/campaign-detail-page.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor no longer reported the Set warnings. |
| `react-doctor/js-set-map-lookups` | `app/(app)/automation/campaigns/[id]/page.client.tsx:822` | Valid. The campaign edit dialog rendered stage checkboxes while checking `editStages.includes(stage.id)` inside the loop; sibling state checkbox membership used the same pattern. | High | Added `editStageIdSet` and `editStateCodeSet`, then switched edit stage and state checkbox checked state to `Set.has`. Added a source guard covering both loops. | GREEN: source guard, campaign detail page test, TypeScript, and changed-scope React Doctor as above. |

Changed-scope command after Batch 189: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100`
- Total diagnostics in changed files: `3`
- Summary: `Bugs 1 warning`, `Maintainability 2 warnings`
- Remaining valid but separate in touched files: `react-doctor/no-giant-component` and `react-doctor/prefer-useReducer` in the broader campaign pages.

Full command after Batch 189: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `84 / 100`
- Total diagnostics: `91`
- Summary: `Bugs 48 warnings`, `Performance 3 warnings`, `Accessibility 4 warnings`, `Maintainability 36 warnings`
- Removed globally since Batch 188: campaign create/edit checkbox Set conversions (`3` warnings), leaving one `js-set-map-lookups` warning in `components/surrogates/SurrogateApplicationTab.tsx`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-987d450a-3cd8-4f62-9b80-89f99957dfd7`

## Batch 190

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/js-set-map-lookups` | `components/surrogates/SurrogateApplicationTab.tsx:834` | Valid. The editable multiselect/checkbox renderer mapped field options while checking every option against `selectedValues.includes(option.value)`. | High | Added `selectedValueSet` next to the existing selected-values array and switched checked-state membership to `Set.has`, while preserving array payload updates. Added a source guard preventing the old `includes` path from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate application multiselect"` failed before the Set conversion. GREEN: same source guard command; `pnpm test --run tests/surrogate-application-tab.test.tsx`; `pnpm tsc --noEmit`; changed-scope React Doctor no longer reported the Set warning. |

Changed-scope command after Batch 190: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Remaining valid but separate in touched files: `react-doctor/no-giant-component` in `components/surrogates/SurrogateApplicationTab.tsx`.

Full command after Batch 190: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `85 / 100`
- Total diagnostics: `90`
- Summary: `Bugs 48 warnings`, `Performance 2 warnings`, `Accessibility 4 warnings`, `Maintainability 36 warnings`
- Removed globally since Batch 189: the final `js-set-map-lookups` warning in `components/surrogates/SurrogateApplicationTab.tsx`. No `js-set-map-lookups` diagnostics remain in the full scan.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-6dd62997-5f38-492a-be77-126f381a63b2`

## Batch 191

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-event-handler` | `app/(app)/intended-parents/page.client.tsx:251`, `:276`, `:279`, `:282`, `:285`, `:288`, `:292` | Valid. The list page mirrored URL params into local filter/page/search state through effects, and a second effect committed debounced search to the URL one render late. | High | Added `readIntendedParentListUrlState`, keyed draft state, and handler-owned debounced URL replacement. Committed filters now derive from URL state; draft UI values reset naturally when the query changes. Added behavior tests for URL-derived filters and debounced URL replacement, plus a source guard preventing the mirror effects from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "intended parent list filters"` failed before the refactor. GREEN: same source guard; `pnpm test --run tests/intended-parents-page.test.tsx tests/matches-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor no longer reported these list-page `no-event-handler` warnings. |
| `react-doctor/no-event-handler` | `app/(app)/intended-parents/matches/page.client.tsx:139`, `:154`, `:157`, `:160`, `:163` | Valid. The matches page used the same debounced-search effect plus URL mirror effect pattern for status/search/page state. | High | Added `readMatchListUrlState`, keyed draft state, and handler-owned debounced URL replacement. Added matching behavior tests and source guard coverage. | GREEN: source guard, matches page tests, TypeScript, lint, and changed-scope React Doctor as above. |

Changed-scope command after Batch 191: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `91 / 100`
- Total diagnostics in changed files: `5`
- Summary: `Bugs 3 warnings`, `Maintainability 2 warnings`
- Remaining changed-scope findings are from other already-ahead local commits (`app/intake/[slug]/page.client.tsx`) plus the valid broader `no-giant-component` warning in `app/(app)/intended-parents/page.client.tsx`.

Full command after Batch 191: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `86 / 100`
- Total diagnostics: `74`
- Summary: `Bugs 36 warnings`, `Performance 2 warnings`, `Maintainability 36 warnings`
- Removed globally since Batch 190: intended-parent list and match list URL mirror effects (`12` `no-event-handler` warnings). The current full scan also no longer shows the prior accessibility cluster, but this batch only changed URL/filter state flow.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-92f6bbdf-2d63-470e-a242-d48a3a4aed6a`

## Batch 192

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/control-has-associated-label` | `app/intake/[slug]/page.client.tsx:1298`, `components/intended-parents/IntendedParentFormFields.tsx:38`, `components/intended-parents/IntendedParentFormFields.tsx:69` | Valid. React Doctor did not associate the plain HTML selects with their visible labels in the fixed-table intake fields and intended-parent pronoun/state controls. | High | Added stable label ids and `aria-labelledby` on the matching selects. Updated source guards to keep the explicit label association. | GREEN: `pnpm test --run tests/react-regressions-source.test.ts`; `pnpm test --run tests/forms-shared-intake.test.tsx`; `pnpm test --run tests/intended-parents-page.test.tsx tests/matches-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor no longer reported these label findings. |
| `react-doctor/prefer-tag-over-role` | `components/surrogates/interviews/InterviewComments/TranscriptPane.tsx:106` | Valid, but a region with JSX click/keyboard handlers introduced `react-doctor/no-noninteractive-element-interactions`. | High | Replaced the role-based container with a native labeled `<section>` and moved delegated transcript highlight listeners into DOM listeners registered with cleanup, so JSX no longer presents a faux button or handler-bearing non-interactive element. Kept the transcript ref typed as `HTMLElement`. Updated interaction/accessibility tests and source guards to reject role-based and JSX-handler variants. | GREEN: `pnpm test --run tests/surrogate-interview-accessibility.test.tsx tests/selection-popover-listeners.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts`; `pnpm tsc --noEmit`; `pnpm lint`; changed-scope React Doctor no longer reported `prefer-tag-over-role` or the transient non-interactive handler warning. |

Changed-scope command after Batch 192: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `91 / 100`
- Total diagnostics in changed files: `4`
- Summary: `Bugs 3 warnings`, `Maintainability 1 warning`
- Remaining changed-scope findings are unrelated pre-existing intake page warnings from earlier local commits.

Full command after Batch 192: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `86 / 100`
- Total diagnostics: `74`
- Summary: `Bugs 36 warnings`, `Performance 2 warnings`, `Maintainability 36 warnings`
- Full diagnostics remain dominated by `query-mutation-missing-invalidation`, `no-event-handler`, `no-giant-component`, and `prefer-useReducer`; no accessibility diagnostics remain in the current full scan.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-39d2fcab-f7ac-44ba-8c05-74d751e4f24e`

## Batch 193

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-event-handler` | `components/appointments/PublicBookingPage.tsx:1001`, `components/appointments/PublicBookingPage.tsx:1034` | Valid. Public booking set timezone defaults from browser and org data through effects, adding extra renders and effect-driven state mirroring for a value that can be derived at render time. | High | Added `getInitialClientTimezone` with `useSyncExternalStore`, kept a `timezoneOverride` only for user selection, and derived `timezone` from override, org timezone when the detected/default timezone is still Pacific, otherwise the detected timezone. Updated the timezone select to set only the override. Added behavior and source guards preventing the effect-driven `setTimezone` path from returning. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "public booking timezone defaults"` failed before the refactor. GREEN: same source guard; `pnpm test --run tests/react-regressions-source.test.ts`; `pnpm test --run tests/appointments-google-meet.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor no longer reports these `no-event-handler` findings. |

Changed-scope command after Batch 193: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `97 / 100`
- Total diagnostics in changed files: `1`
- Summary: `Bugs 1 warning`
- Remaining valid but separate in touched files: pre-existing `react-doctor/prefer-useReducer` in `components/appointments/PublicBookingPage.tsx:1028`.

Full command after Batch 193: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `86 / 100`
- Total diagnostics: `71`
- Summary: `Bugs 34 warnings`, `Performance 2 warnings`, `Maintainability 35 warnings`
- Removed globally since Batch 192: public booking timezone effect warnings (`2` `no-event-handler` warnings) and the broader public booking giant-component diagnostic. The public booking reducer diagnostic remains valid but separate.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-cba3c2aa-1800-4758-8978-74167d277c3d`

## Batch 194

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-event-handler` | `app/(app)/surrogates/page.client.tsx:855`, `app/(app)/surrogates/page.client.tsx:913-931`, `app/(app)/surrogates/page.client.tsx:934-946`, `app/(app)/surrogates/page.client.tsx:950` | Valid. The surrogate list mirrored URL params into local filter/search/page/sort state through effects, then pushed debounced search back to the URL from another effect. | High | Added `readSurrogateListUrlState` and canonical search-param normalization, derived committed filter state from the current URL, kept only keyed draft search state, and moved debounced search URL replacement into the search input handler. Removed the old exhaustive-deps suppression because the URL mirror effect is gone. Follow-up: canceled pending debounced search commits when `currentQuery` changes so browser back/forward cannot be clobbered by stale filter closures. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "surrogate list filters"` failed before the refactor. RED follow-up: `pnpm test --run tests/surrogates.test.tsx -t "cancels pending search"` reproduced stale `/surrogates?stage=s1&q=draft` replacement before the cleanup. GREEN: `pnpm test --run tests/surrogates.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor no longer reports these `no-event-handler` findings. |

Changed-scope command after Batch 194: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Remaining valid but separate in touched files: pre-existing `react-doctor/no-giant-component` in `app/(app)/surrogates/page.client.tsx:546`.

Full command after Batch 194: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `87 / 100`
- Total diagnostics: `56`
- Summary: `Bugs 19 warnings`, `Performance 2 warnings`, `Maintainability 35 warnings`
- Removed globally since Batch 193: surrogate list URL/search mirror effects and the surrogate page `prefer-useReducer` warning (`15` total diagnostics removed). Remaining `no-event-handler` diagnostics are now limited to email templates, tasks focus view, and intake draft loading.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-1b2bdf1e-9578-4463-b7ae-e26e4a7cf095`

## Batch 195

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-event-handler` | `app/(app)/automation/email-templates/page.tsx:914` | Valid. The email template modal copied the fetched full template body and body-mode into draft state through an effect, adding an extra render and delaying modal body hydration behind state synchronization. | High | Derived the modal body and editor mode from `fullTemplate` while the user has not edited them, then kept explicit body/body-mode overrides only after user interaction. Modal open now resets those overrides instead of clearing and rehydrating state through an effect. Added behavior coverage for complex fetched template bodies opening directly in HTML mode, plus a source guard preventing the hydration effect from returning. | GREEN: `pnpm test --run tests/email-templates-page.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor no longer reports this `no-event-handler` finding. |

Changed-scope command after Batch 195: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `92 / 100`
- Total diagnostics in changed files: `2`
- Summary: `Bugs 1 warning`, `Maintainability 1 warning`
- Remaining valid but separate in touched files: pre-existing `react-doctor/no-giant-component` and `react-doctor/prefer-useReducer` in `app/(app)/automation/email-templates/page.tsx:720`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-41ae2b89-f452-4084-aaf8-8319240177df`

Full command after Batch 195: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `87 / 100`
- Total diagnostics: `55`
- Summary: `Bugs 18 warnings`, `Performance 2 warnings`, `Maintainability 35 warnings`
- Removed globally since Batch 194: email-template full-body hydration effect (`1` `no-event-handler` warning). Remaining `no-event-handler` diagnostics are now limited to the tasks focus view and intake draft loading.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-8f1dd3b9-7f1d-4cb1-b5b5-e18ffe590bc2`

## Batch 196

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-event-handler` | `app/(app)/tasks/page.client.tsx:326` | Valid. A focused Tasks URL rendered the saved calendar view first, then an effect changed `view` to `list` and persisted the list preference before a second effect could scroll to the target. That was event-style focus routing expressed as state plus effects. | High | Added render-time `activeView` derivation for non-approval focus targets so focused task URLs render the list immediately. Kept the imperative scroll in the existing effect, retained user view-toggle control with explicit `manualViewFocusTarget` state, and preserved the list preference after the focused target is handled. Added first-render behavior coverage and a source guard rejecting the old `setView("list")` focus effect. | RED: `pnpm test --run tests/tasks-page.test.tsx -t "focused task URLs"` and `pnpm test --run tests/react-regressions-source.test.ts -t "Tasks page focus coordination"` failed before the refactor. GREEN: `pnpm test --run tests/tasks-page.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. |

Changed-scope command after Batch 196: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 196: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `87 / 100`
- Total diagnostics: `54`
- Summary: `Bugs 17 warnings`, `Performance 2 warnings`, `Maintainability 35 warnings`
- Removed globally since Batch 195: Tasks page focus-view state effect (`1` `no-event-handler` warning). Remaining `no-event-handler` diagnostics are now limited to intake draft loading.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-e379beed-736e-4752-924a-c864a495bd61`

## Batch 197

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-event-handler`, `react-doctor/prefer-useReducer` | `app/intake/[slug]/page.client.tsx:839`, `app/intake/[slug]/page.client.tsx:809` | Valid. Hosted intake bootstrap loaded the public schema, draft payload, loading/error state, restored answers, and draft-save metadata through several local setters from the mount effect. The draft session was also separate from the bootstrap transition, which made same-instance slug changes and stale saved draft IDs harder to handle consistently. | High | Moved form/draft bootstrap into `loadHostedIntakeBootstrap` plus `hostedIntakeReducer`, made the reducer own the active `DraftSessionState`, replaced stale saved draft IDs with a fresh draft session on 404, and changed autosave to skip only restored draft payloads rather than the first manual answer. Added shared-intake coverage for saved draft answer restore, stale saved-session replacement before autosave, and same-instance slug changes. No inline suppression is used. | GREEN: `pnpm test --run tests/forms-shared-intake.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports only the pre-existing giant-component finding in the touched file. |

Changed-scope command after Batch 197: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Remaining valid but separate in touched files: pre-existing `react-doctor/no-giant-component` in `app/intake/[slug]/page.client.tsx:993`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-4de295c3-2a58-45a0-89d1-3fa0fee73dbe`

Full command after Batch 197: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `88 / 100`
- Total diagnostics: `51`
- Summary: `Bugs 14 warnings`, `Performance 2 warnings`, `Maintainability 35 warnings`
- Removed globally since Batch 196: hosted-intake bootstrap state/effect findings (`2` `no-event-handler` warnings from the same line and `1` `prefer-useReducer` warning). No `no-event-handler` diagnostics remain in the current full scan.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a53a9af9-809d-4763-bb9b-7edc61f41bde`

## Batch 198

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-useReducer` | `app/(app)/ai-studio/page.tsx:540` | Valid. Opening and saving Studio settings updated dialog visibility, secret-key input, guidance textareas, and saved-state as one settings-dialog transition, but those values were split across five separate `useState` calls. | High | Added `AIStudioSettingsDialogState` plus `aiStudioSettingsDialogReducer`, routed open/close/edit/save transitions through dispatch actions, and kept the API key write-only by clearing the input after save. Extended AI Studio behavior coverage for saving an entered API key, closing after save, and reopening with a blank secret field. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "AI Studio settings"` failed before the reducer. GREEN: `pnpm test --run tests/ai-studio-page.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "AI Studio settings"`; `pnpm tsc --noEmit`; changed-scope React Doctor reports only the pre-existing giant-component finding in the touched file. |

Changed-scope command after Batch 198: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Remaining valid but separate in touched files: pre-existing `react-doctor/no-giant-component` in `app/(app)/ai-studio/page.tsx:582`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-509ea0c0-fdf6-404c-9a8c-d012f1c913f2`

Full command after Batch 198: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `88 / 100`
- Total diagnostics: `50`
- Summary: `Bugs 13 warnings`, `Performance 2 warnings`, `Maintainability 35 warnings`
- Removed globally since Batch 197: AI Studio settings dialog `prefer-useReducer` warning (`1` bug warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-9829acd9-d964-49d0-9b25-e1d003aca0e9`

## Batch 199

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/jsx-max-depth` | `app/(app)/automation/executions/page.tsx:519` | Valid. The expanded workflow execution row rendered the action timeline, skip reason, error/retry panel, and trigger event map inline inside the table body, producing deeply nested JSX that was hard to scan and change. | High | Extracted focused helpers for `ExecutionDetailsRow`, `ExecutionActionsTimeline`, `ExecutionErrorPanel`, and `ExecutionTriggerEventDetails`, while preserving the existing retry callback and action detail rendering. Added a source guard requiring the split helpers. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "workflow execution details"` failed before the split. GREEN: `pnpm test --run tests/automation-executions-page.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "workflow execution details"`; `pnpm tsc --noEmit`; changed-scope React Doctor reports only the pre-existing giant-component finding in the touched file. |

Changed-scope command after Batch 199: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Remaining valid but separate in touched files: pre-existing `react-doctor/no-giant-component` in `app/(app)/automation/executions/page.tsx:327`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-6e1f2f1a-1def-4cb4-9fd1-b202dec65970`

Full command after Batch 199: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `88 / 100`
- Total diagnostics: `49`
- Summary: `Bugs 13 warnings`, `Performance 2 warnings`, `Maintainability 34 warnings`
- Removed globally since Batch 198: workflow execution details `jsx-max-depth` warning (`1` maintainability warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-d46b05fe-a7d8-42eb-aab7-7f7e29a813a3`

## Batch 200

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/prefer-useReducer` | `components/appointments/PublicBookingPage.tsx:1028` | Valid. Public booking selection behaves as one state machine: selecting an appointment type resets date/slot/form visibility and chooses a meeting mode only when there is a single format; selecting a date clears stale slots; selecting a slot enables the contact form. The previous implementation split those transitions across five `useState` calls plus a meeting-mode sync effect. | High | Added `BookingSelectionState` plus `bookingSelectionReducer`, replaced the sync effect with explicit type/mode/date/slot/form actions, and preserved existing Google Meet, calendar, timezone, and booking idempotency behavior. Added a source guard rejecting the separate selection setters. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "public booking selection"` failed before the reducer. GREEN: `pnpm test --run tests/appointments-google-meet.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "public booking selection"`; `pnpm tsc --noEmit`; changed-scope React Doctor reports no issues. |

Changed-scope command after Batch 200: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 200: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `88 / 100`
- Total diagnostics: `48`
- Summary: `Bugs 12 warnings`, `Performance 2 warnings`, `Maintainability 34 warnings`
- Removed globally since Batch 199: public booking selection `prefer-useReducer` warning (`1` bug warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-99f0eba9-0b1f-4047-ba3b-b18a3263e72a`

## Batch 201

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/jsx-max-depth` | `app/ops/templates/system/[systemKey]/page.client.tsx:989` | Valid. The system-template campaign dialog rendered organization selection, selected-org recipient cards, per-member checkboxes, loading states, and inactive badges inline in the page body. | High | Extracted `SystemTemplateCampaignRecipients` and `SystemTemplateCampaignRecipientCard`, preserving active-member auto-selection and selected-recipient campaign payloads. Added behavior coverage for sending to selected active organization members and a source guard requiring the split. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "platform system campaign"` failed before the split. GREEN: `pnpm test --run tests/platform-system-email-template-page.test.tsx`; `pnpm test --run tests/react-regressions-source.test.ts -t "platform system campaign"`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports only the pre-existing giant-component finding in the touched file. |

Changed-scope command after Batch 201: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `98 / 100`
- Total diagnostics in changed files: `1`
- Summary: `Maintainability 1 warning`
- Remaining valid but separate in touched files: pre-existing `react-doctor/no-giant-component` in `app/ops/templates/system/[systemKey]/page.client.tsx:466`.
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-88a45883-27af-4e72-a01c-9c56c9a00de4`

Full command after Batch 201: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `89 / 100`
- Total diagnostics: `47`
- Summary: `Bugs 12 warnings`, `Performance 2 warnings`, `Maintainability 33 warnings`
- Removed globally since Batch 200: platform system template campaign recipient `jsx-max-depth` warning (`1` maintainability warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-aea09741-5a1e-4452-91a3-949c96bdd42a`

## Batch 202

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/(app)/reports/page.tsx:238` | Valid. `ReportsPage` owned date/campaign controls, export controls, summary cards, AI insight cards, chart composition, Meta spend, and individual performance rendering in one large component. | High | Extracted `ReportsPageHeader`, `ReportsQuickStatsGrid`, `ReportsAiSummaryCard`, and `ReportsPerformanceSection` while leaving data fetching, export behavior, and chart transforms in the page controller. Added a source guard requiring the split and fixed the adjacent performance-mode `SelectValue` so the trigger renders friendly labels instead of raw enum values. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "reports page rendering"` failed before the split. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "reports page rendering\|report summary\|reports PDF"`; `pnpm test --run tests/reports-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. |

Changed-scope command after Batch 202: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 202: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `89 / 100`
- Total diagnostics: `46`
- Summary: `Bugs 12 warnings`, `Performance 2 warnings`, `Maintainability 32 warnings`
- Removed globally since Batch 201: reports page `no-giant-component` warning (`1` maintainability warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ab32c910-3af6-4016-a10a-9e870e840c96`

## Batch 203

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/(app)/automation/executions/page.tsx:327` | Valid. `WorkflowExecutionsPage` owned the header, stats cards, filters, execution table, pagination, expanded rows, and retry confirmation dialog in one component. | High | Extracted `WorkflowExecutionsHeader`, `WorkflowExecutionStatsGrid`, `WorkflowExecutionFilters`, `WorkflowExecutionsTable`, and `WorkflowExecutionRetryDialog` while keeping query state, pagination state, expansion state, and retry mutation behavior in the page controller. Extended the source guard that already covered execution detail helpers. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "workflow execution details"` failed before the split. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "workflow execution details"`; `pnpm test --run tests/automation-executions-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. |

Changed-scope command after Batch 203: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 203: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `89 / 100`
- Total diagnostics: `45`
- Summary: `Bugs 12 warnings`, `Performance 2 warnings`, `Maintainability 31 warnings`
- Removed globally since Batch 202: workflow executions page `no-giant-component` warning (`1` maintainability warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-a7bc7840-8fce-4026-878d-4acafd43458f`

## Batch 204

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/(app)/ai-studio/page.tsx:582` | Valid. `AIStudioPage` owned the header, alerts, loading shell, draft generator, create/gallery tabs, preview composition, and settings dialog rendering in one component. | High | Extracted `AIStudioHeader`, `AIStudioAlerts`, `AIStudioLoadingShell`, `DraftGeneratorCard`, `AIStudioCreateTab`, `AIStudioGalleryTab`, and `AIStudioSettingsDialog` while keeping query state, draft state, reference-image state, and mutation handlers in the page controller. Extended the existing source guard to require the split. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "AI Studio settings"` failed before the split. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "AI Studio settings"`; `pnpm test --run tests/ai-studio-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. |

Changed-scope command after Batch 204: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 204: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `89 / 100`
- Total diagnostics: `44`
- Summary: `Bugs 12 warnings`, `Performance 2 warnings`, `Maintainability 30 warnings`
- Removed globally since Batch 203: AI Studio page `no-giant-component` warning (`1` maintainability warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-c5160557-f656-4de8-8b0e-8dedb839b3e7`

## Batch 205

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/(app)/settings/audit/page.tsx:77` | Valid. `AuditLogPage` owned the page header, export controls, export job list, AI activity summary, event filter, audit entries, and pagination in one component. | High | Extracted `AuditPageHeader`, `AuditExportCard`, `AuditActivityCard`, `AuditLogEntriesList`, and `AuditPagination` while keeping filters, query state, export mutation state, and polling in the page controller. Added a source guard requiring the split. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "audit settings page sections"` failed before the split. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "audit settings page sections"`; `pnpm test --run tests/audit-log-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. |
| `react-doctor/rerender-state-only-in-handlers` | `components/intended-parents/IntendedParentClinicCard.tsx:278-279` | False positive. `manuallyAddedSections` and `optimisticallyHiddenSections` are read during render to derive `visibleKeys`, `hiddenKeys`, and `visibleSections`; that render-derived list controls which clinic/embryo sections are visible. | High | No code change. Switching these sets to refs would not preserve behavior because adding/removing a section must rerender the card. Existing focused coverage protects the add/remove flows. | READ-ONLY: subagent validation confirmed render-time reads and existing coverage in `tests/intended-parent-detail.test.tsx` plus `tests/react-regressions-source.test.ts`. |

Changed-scope command after Batch 205: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 205: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `89 / 100`
- Total diagnostics: `43`
- Summary: `Bugs 12 warnings`, `Performance 2 warnings`, `Maintainability 29 warnings`
- Removed globally since Batch 204: audit settings page `no-giant-component` warning (`1` maintainability warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-ebb9c679-f297-4c19-8db0-4b21ef7ebcd7`

## Batch 206

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/(app)/automation/forms/page.tsx:144` | Valid. `FormsListPage` owned the page header, form tab, template tab, form/template cards, create dialog, delete confirmations, and share dialog in one component. | High | Extracted `FormsPageHeader`, `FormsPageTabs`, `FormsGrid`, `FormCard`, `FormTemplatesGrid`, `FormTemplateCard`, `CreateFormDialog`, `DeleteFormDialog`, and `ShareFormDialog` while keeping query/mutation state, navigation, and share/download handlers in the page controller. Added a source guard requiring the split. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "forms list page sections"` failed before the split. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "forms list page sections"`; `pnpm test --run tests/forms-delete.test.tsx`; `pnpm test --run tests/forms-builder-template.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. |

Changed-scope command after Batch 206: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 206: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `89 / 100`
- Total diagnostics: `42`
- Summary: `Bugs 12 warnings`, `Performance 2 warnings`, `Maintainability 28 warnings`
- Removed globally since Batch 205: forms list page `no-giant-component` warning (`1` maintainability warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-fee734b7-75be-423c-b65c-3882d0546f7d`

## Batch 207

| Rule | Files | Verdict | Confidence | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| `react-doctor/no-giant-component` | `app/book/self-service/[orgId]/manage/[token]/page.tsx:126` | Valid. `ManageAppointmentPage` owned loading/error/success states, appointment summary, action toggle, timezone selector, calendar grid, time-slot grid, and cancellation form in one component. | High | Extracted `ManageLoadingState`, `ManageErrorState`, `ManageSuccessState`, `AppointmentSummary`, `AppointmentActionToggle`, `ReschedulePanel`, `ManageCalendarGrid`, `ManageSlotsGrid`, and `CancelPanel` while keeping route parsing, API calls, timezone derivation, slot loading, and submit handlers in the page controller. Added a source guard requiring the split. | RED: `pnpm test --run tests/react-regressions-source.test.ts -t "self-service manage appointment rendering"` failed before the split. GREEN: `pnpm test --run tests/react-regressions-source.test.ts -t "self-service manage appointment rendering"`; `pnpm test --run tests/self-service-manage-page.test.tsx`; `pnpm tsc --noEmit`; `pnpm lint`; `git diff --check`; changed-scope React Doctor reports no issues. |

Changed-scope command after Batch 207: `cd apps/web && npx -y react-doctor@latest . --verbose --scope changed`

- Score: `100 / 100`
- Total diagnostics in changed files: `0`
- Summary: no issues found.

Full command after Batch 207: `cd apps/web && npx -y react-doctor@latest . --verbose`

- Score: `89 / 100`
- Total diagnostics: `41`
- Summary: `Bugs 12 warnings`, `Performance 2 warnings`, `Maintainability 27 warnings`
- Removed globally since Batch 206: self-service manage appointment page `no-giant-component` warning (`1` maintainability warning).
- Diagnostics: `/var/folders/c7/6l609_kn28g79m0_9klfr8z80000gn/T/react-doctor-2e26bef8-2211-4201-bcf0-16cccc91755d`
