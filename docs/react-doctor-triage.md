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
