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
