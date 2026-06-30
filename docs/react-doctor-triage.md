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
