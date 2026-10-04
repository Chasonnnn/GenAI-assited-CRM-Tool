# Cross-cutting audit evidence

Read-only discovery at `bef1a04161f9d5f78fffe9cc15a0db8143a9995f`. No source, test, or configuration changes and no test execution in this lane.

## Discovery

- Parsed all backend `tests/test*.py` functions with Python AST. Exact body comparison removed docstrings but preserved expressions and literal values. Two duplicate-body pairs appeared; both have distinct parameter tables and remain required.
- Repeated the backend comparison with literal values normalized, to find superficially similar assertions. Largest groups were height parser representations, separate authenticated API endpoints, slug validation, link wrapping, permission variants, and URL validation. Similar bodies do not establish equivalent contracts.
- Parsed all frontend `tests/**/*.{test,spec}.{ts,tsx,js,jsx}` using the installed TypeScript API. Found 2,758 test callbacks and zero identical whitespace-normalized callback bodies. This is a discovery declaration count, not a Vitest collected-case baseline.
- Searched source-reading tests, mock-return echoes, assertion-free bodies, and API wrapper suites. The sole frontend callback without an inline `expect` delegates to `expectHeldCardEntrances`; it is not assertion-free.
- Coordinated ownership: frontend audit owns component/hook duplicate layers; backend audit owns helper normalization and match-lifecycle characterization. This lane owns cross-cutting discovery, frontend static/configuration guards, and frontend API wrappers.

## Deletion-ready candidates: 3 cases

These tests inspect prose only. They do not execute a production owner or enforce the configuration described by their names. They can pass when the documented production configuration is wrong and fail after an equivalent documentation rewrite. Keep all executable/default, dependency, route-validator, and cache configuration tests in the file.

### D1

- Exact test: `apps/web/tests/next-16-3-adoption.test.ts:58`, `records the tenant-safety migration boundary before the feature can be promoted`.
- Actual detection: removal of the literal historical blocker count, environment-variable spelling, promotion warning phrase, or `organization_id` from `docs/next-16-3-adoption.md`.
- Owner/callers: the asserted file is engineering documentation, with no production caller. Next loads `apps/web/next.config.js`; it does not read this Markdown. Read the full test file, full documentation, full Next config, package scripts, workflow routing, and history.
- Retained proof: same file's `keeps experimental profiles off by default and enables each one explicitly` loads the real configuration with environment switches unset/set and checks the safe default and activated values. Repository tenant-negative tests retain actual tenant isolation; this prose grep never established it. The historical number `17` is not a current runtime contract.
- History/reason: introduced by `2406ca917b51743f23c78c2ff61a489792af35a0` (`chore: upgrade frontend to Next.js 16.3 and TypeScript 7`) as adoption-plan documentation protection. `3eb09d16b043af8a740046c2914e6b4bc03b813a` removed two earlier adoption assertions but left these prose checks unchanged. Neither inspected change establishes a behavior regression guarded by the literal count.
- Deletion unlocked: one test callback, nine lines; no production/support deletion.
- Risk: loss of automatic enforcement of exact prose. The docs and executable feature gate remain. Expected production coverage change: none; confirm with parent lane's same-environment coverage comparison.
- Focused validation: `cd apps/web && mise exec -- pnpm test tests/next-16-3-adoption.test.ts tests/dependency-security.test.ts`; run existing `typecheck`, `typecheck:tests`, and production `build` gates as appropriate to the full change.

### D2

- Exact test: `apps/web/tests/next-16-3-adoption.test.ts:67`, `documents the TypeScript 7 split-toolchain boundary`.
- Actual detection: Markdown heading or quoted dependency versions changing, including appropriate future upgrade edits; removal of compiler-command/configuration phrases. It never reads package declarations, installed compiler behavior, or CI execution.
- Owner/callers: documentation has no production callers. Package scripts invoke the TypeScript CLI; Next loads config and the compiler package; ESLint consumes the compatibility compiler API. Full package/config/docs/test and CI surface was read.
- Retained proof: actual `useTypeScriptCli: false` is asserted by the retained runtime-config test; `Dependency security guards > holds React and TypeScript on the validated compatibility line` checks the package manifest; CI executes application and test type checks plus production build. An exact quoted Markdown version is not an independent compiler contract.
- History/reason: same original adoption commit and later cleanup as D1; intended to keep migration guidance present during TS7 adoption. No runtime call depends on the literal heading or quoted prose.
- Deletion unlocked: one callback, eleven lines; no production/support deletion.
- Risk: docs can drift without this phrase-presence alarm, but this alarm already accepts stale documentation (the file still says the test project is not a CI gate while current CI invokes `typecheck:tests`). Parent dependency-upgrade lane should edit relevant factual docs when adopting versions.
- Focused validation: same command as D1 plus existing compiler/lint gates; baseline and candidate production coverage must use the same source universe.

### D3

- Exact test: `apps/web/tests/next-16-3-adoption.test.ts:78`, `documents the production bundler boundary`.
- Actual detection: removal of a heading and the words `next build --webpack`, `React Compiler`, and `Turbopack` from the adoption guide. A wrong package build command leaves this test green.
- Owner/callers: documentation has no production callers. `apps/web/package.json` is the executable build entry point; CI invokes `pnpm run build`, which selects Webpack. Next config controls React Compiler.
- Retained proof: current package build command and the required real production build execute the bundler choice; remaining config tests protect experimental defaults. No replacement prose test is needed.
- History/reason: same original adoption commit and later cleanup as D1; introduced to retain the explanation for the Webpack fallback. The explanation remains in the unchanged documentation.
- Deletion unlocked: one callback, nine lines; no production/support deletion.
- Risk: exact wording can change. No runtime or architecture contract is lost because this callback only tests explanatory prose.
- Focused validation: same as D1; production build is the executable owner gate when bundler/config is changed.

## Retained false positives

| Surface | Decision and contract |
| --- | --- |
| `test_messaging_opt_out_classifier.py` equal bodies for `test_clear_natural_language_revocations_are_global` and `test_explicit_all_channel_revocations_take_priority_over_promotional_terms` | R. Different message tables exercise global revocation versus promotional-term precedence. Equal assertion bodies do not make consent inputs interchangeable. |
| `test_import_transformers.py` equal bodies for unrecognized-inch suffixes and invalid fractions | R. Different parser rejection classes; invalid fractions and accidental suffix-prefix matches are distinct regressions. |
| Backend no-inline-assert scan: fixture functions named `test_workflow`, `test_surrogate`, `test_template`, `test_campaign` | R. Fixtures, not collected tests; do not count them as test removals. |
| `test_websocket_pubsub_no_redis`, `test_notify_revocation_ignores_a_closed_event_loop` | R. No-raise behavior is the contract for absent optional Redis or a closed loop. Removing them solely for no inline assert would lose failure behavior. |
| `test_validate_file_accepts_valid_pdf`, `test_validate_answers_accepts_height_field_values`, `test_legacy_surrogate_outbox_without_source_job_remains_eligible` | R pending stronger owner evidence. No-raise success is meaningful validation/eligibility behavior; lack of inline assertion alone is insufficient. |
| `test_zapier_inbound_webhook_limits_use_direct_count_queries`, `test_create_export_job_uses_direct_count_queries` | R. Monkeypatched SQLAlchemy callback raises an assertion if the disallowed query method is invoked; they are not assertion-free. Their implementation coupling alone does not prove a stronger retained performance guard exists. |
| `test_paused_stage_uses_prior_phase_and_archive_policy_is_shared` | R. Calls `_assert_parity` repeatedly; test has tenancy/access-policy assertions through helper. |
| `reports-page.test.tsx > holds the start state of staggered summary cards through a capped delay` | R. Delegates assertions to `expectHeldCardEntrances`. |
| `dependency-security.test.ts` | R. Manifest overrides and resolved-lockfile floor checks protect separate entry points: future resolution policy and current frozen artifacts. Package/security guards meet the explicit retention bar. Do not delete to meet a case quota. |
| `page-header-adoption.test.tsx` static page table | R. Independent architecture/UI-adoption guard across actual callers. Owner component rendering does not prove each page uses the shared header. It is source-coupled, but no equivalent comprehensive caller-boundary keeper was established. |
| `page-header-adoption.test.tsx` Workflows runtime callback | R after frontend lane review. Checks allowed Execution History and template-tab omission; `automation-page-header.test.tsx` checks denied permission and Create Workflow callback. Distinct props/branches. |
| `ui-description-policy.test.ts`, `motion-class-policy.test.ts`, `no-history-state-clobber.test.ts`, `design-system-primitives.test.ts` | R. UI boundary/recovery copy, observable motion compatibility, Next navigation state, and shared primitive architecture remain independent contracts. No equivalent comprehensive keeper established. |
| `api-ai-contracts.test.ts`, `donors-api.test.ts`, `permissions-api.test.ts`, `twilio-api.test.ts`, `email-template-history-api.test.ts`, `platform-email-readiness-api.test.ts` | R. Mocked transport is the appropriate boundary for endpoint, method, query, body, and routing contracts. Tests assert calls, not merely the mock's result. Nearby UI tests mock the API layer, so cannot establish these contracts. |
| `server-api-headers.test.ts` | R. Forwarded headers and absence handling protect real request-boundary behavior. |

## Follow-ups sent to owner lanes

- Backend: compare unit slug tests with real platform organization endpoint invalid-input tests, while preserving distinct schema/transport rules.
- Frontend: compare `match-query-contract.test.ts` against hydration consumers and actual query integration before treating self-derived key expectations as removable.
- Dependency lane: adoption guide has stale test-typecheck and version statements; exact prose greps fail to establish freshness.

## Scope of evidence

The mechanical discovery covers both test directories. Complete production/history evidence is established for the three proposed deletions, not for every declaration. No deletion count, coverage delta, or CI speedup is claimed from scans. Removal of three prose-only checks is not sufficient for the user's 20% target; the parent audit must reconcile all owner lanes and measured baseline/candidate runs.

## Executed validation

The frozen baseline at `bef1a0416` contained 3,033 passing frontend cases. All 3,017 retained cases passed after the combined 16-case reduction on the original Vitest 5.0.1/jsdom 29.1.1 toolchain. Statements, lines, branches, and functions were unchanged, including every per-file coverage count. Independent preservation review found no gaps. Later tooling and shard validation is reported separately.
