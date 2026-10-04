# Dependency modernization audit

Baseline: `595bf5b75254783a80e158eb99a6d99a1893e22e`, branch `fix/log-client-error-codes`. Registry snapshot: 2026-10-01 03:51 UTC, September 30 in New York. [Inventory](inventory.json): 76 Python and 56 npm direct declarations, including test/development dependencies; no registry lookup failures. Declared, locked, installed and registry versions are recorded separately. Registry latest versions are candidates, not compatibility decisions.

## Implemented

| Dependency | Baseline → selected | Benefit and adoption |
|---|---|---|
| Next / bundle analyzer | 16.3.4 → 16.3.7 | Includes the September 22 upstream security fix and a Turbopack canceled-task hang fix. Framework, environment and native compiler packages move together. React, Webpack production builds and experimental feature gates stay on their existing configuration. |
| markdown-it | 14.2.0 → 14.3.1 | Fixes quadratic linkification. `AssistantRichText` enables `linkify`, so the affected path is used. Stay on the compatible 14.x line. |
| DOMPurify | locked 3.4.15 → 3.4.16 | Applies the sanitization security patch. The advisory's `IN_PLACE` plus hook combination was not found in this app. |
| brace-expansion override | 5.0.9 → 5.0.12 | Removes two high-severity recursion advisories and one quadratic expansion advisory from the resolved tree. |
| PyJWT | 2.14.0 → 2.15.1 | Applies the new payload-decoding security fix and the follow-up padding compatibility fix. Real session-decoder tests cover malformed registered claims becoming controlled JWT errors. |
| urllib3 | 2.7.0 → 2.8.0 | Applies proxy TLS identity/context, chunk buffering and deflate fixes. Existing Requests/Boto/provider callers retain their APIs. |
| Tiptap React | 3.30.5, unchanged | Both toolbars now use `useEditorState`. Selection, formatting, headings, alignment, Undo/Redo and comment availability update without enabling whole-editor transaction rerenders. |
| OpenAI Python | 2.36.0, unchanged | AI Studio uses the SDK async context manager. Its HTTP transport closes on success, provider error and task cancellation. Existing Responses parsing remains in use. |
| Pydantic | 2.12.5, unchanged | Three template schemas adopt `validate_by_name` and `validate_by_alias`; both input spellings, alias precedence and public serialization are preserved. |
| TypeScript / Vitest integration | native 7.0.2 and compatibility package 6.0.2, unchanged | Use the official jest-dom/Vitest entrypoint and remove duplicate matcher registration. Correct the documented Next compiler selection. |

Security sources: [Next September 22](https://nextjs.org/blog/nextjs-security-update-september-22-2026), [Next 16.3.7](https://github.com/vercel/next.js/releases/tag/v16.3.7), [markdown-it](https://github.com/markdown-it/markdown-it/security/advisories/GHSA-253c-mchw-3w2r), [DOMPurify](https://github.com/cure53/DOMPurify/security/advisories/GHSA-p98j-92pf-mc4p), [brace expansion](https://github.com/juliangruber/brace-expansion/security/advisories/GHSA-q2hr-2g5m-vwhr), [PyJWT changelog](https://pyjwt.readthedocs.io/en/stable/changelog.html), [urllib3 2.8.0](https://github.com/urllib3/urllib3/releases/tag/2.8.0).

Adoption sources: [Tiptap state subscriptions](https://tiptap.dev/docs/guides/performance), [Pydantic version-matched configuration](https://raw.githubusercontent.com/pydantic/pydantic/v2.12.5/pydantic/config.py), [jest-dom Vitest integration](https://github.com/testing-library/jest-dom#with-vitest). OpenAI lifecycle behavior was verified in the installed 2.36.0 SDK and through its actual HTTP transport.

## Next 16.3.8 release-age hold

Next 16.3.8 was published at `2026-09-30T16:07:21.198Z`. Its bundle analyzer was published earlier that day. The family clears the repository's 1,440-minute policy at **October 1, 2026, 12:07:21 EDT**. No new exclusion, trust-policy bypass or runtime change was added.

The [September 30 security release](https://nextjs.org/blog/september-2026-security-release) contains seven more fixes. Local review found no remote image patterns, Pages Router SSG/ISR, root catch-all SSG, metadata-image generator, or enabled Cache Components. The development MCP disclosure does apply to use of `next dev`. The registry audit did not yet report these seven advisories; a clean audit is not proof they are absent.

Upgrade Next and its analyzer to 16.3.8 after maturation, then repeat frontend checks, production build and Linux standalone validation. The current change adopts the eligible 16.3.7 release and does not claim full September 30 remediation.

## Feature decisions

| Family | Current → registry candidate | Decision and required work |
|---|---|---|
| FastAPI / OpenTelemetry | 0.136.3 / 1.39.1 / 0.60b1 → 0.142.2 / 1.45.0 / 0.66b0 | Separate coordinated migration. Native operation spans are useful, but automatic configuration reads endpoint variables independently of `OTEL_ENABLED`. Both FastAPI apps need explicit controls; server/client/database data need redaction and provider shutdown tests. [Concrete adoption plan](fastapi-opentelemetry.md). |
| TypeScript | native 7.0.2, already current | Native CLI is active. Keep TS6 for Next and ESLint compiler-API consumers. Tests are outside the application compiler gate; corrected matcher types remove 5,129 diagnostics, while 358 pre-existing errors remain. No failing test-type gate was added. [Detailed evidence](typescript.md). |
| React / React DOM | 19.2.7 → 19.3.0 | Defer View Transitions, Fragment Refs and related rendering APIs until a product flow needs them. Stable React Compiler is already enabled. [Release](https://react.dev/blog/2026/09/09/react-19-3). |
| TanStack Query | 5.101.2 → 5.104.0 | Existing server state and match-page hydration are adopted. Search cancellation is a concrete follow-up: pass `queryFn`'s signal through `globalSearch` and the existing fetch options; prove obsolete requests abort without error UI. It does not require a version bump. [Cancellation contract](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation). |
| Base UI | 1.6.0 → 1.8.0 | Shared component upgrade needs browser focus, select labels, dialogs, tabs and keyboard checks. Preserve customized primitives. New APIs have no demonstrated caller yet. [Release](https://base-ui.com/react/overview/releases/v1-8-0). |
| Tiptap | 3.30.5 → 3.31.4 | State subscription adoption is implemented independently. Upgrade the full family and menu overrides together in a later batch; validate linked whitespace, text alignment, editor attributes and transcript comments. [Release](https://github.com/ueberdosis/tiptap/releases/tag/v3.31.4). |
| Zod | 4.4.3 → 4.6.5 | Current onboarding uses ordinary string validation. Codecs, metadata, Mini and JSON Schema have no identified need. Avoid schema rewrites for version parity. [Features](https://zod.dev/v4). |
| Pydantic / core | 2.12.5 / 2.41.5 → 2.13.5 / resolver-selected core | Configuration adoption is implemented. A version upgrade must keep core coupled and preserve declared response fields; polymorphic serialization could expose subclass fields. [Release](https://pydantic.dev/articles/pydantic-v2-13-release). |
| SQLAlchemy / psycopg | 2.0.46 / 3.3.2 → 2.1.1 / 3.3.6 | Defer 2.1 until autoflush, loader, streaming-export and PostgreSQL type changes pass tenant and migration suites. Current scoped loader constraints are intentional. [Migration guide](https://docs.sqlalchemy.org/en/21/changelog/migration_21.html). |
| OpenAI Python | 2.36.0 → 3.22.1 | Current feature adoption is lifecycle cleanup. Major 3 brings HTTPX2 migration work; retain the locked 2.x SDK until actual transport, streaming and cancellation contracts pass. |
| Google GenAI / auth | 2.22.0 / 2.57.1 → 2.26.0 / 2.59.1 | Current Gemini/Vertex modes already use the recent SDK. Constructors omit a request timeout; installed SDK defaults HTTPX to no timeout. Choose a request budget, set `HttpOptions.timeout` in milliseconds and close async/sync clients across streaming cancellation in one change. [SDK documentation](https://googleapis.github.io/python-genai/). |
| Twilio | 9.10.9 → 9.11.2 | Sending already uses a bounded 20-second transport. Configuration checks use the default client; reuse the bounded transport and test sanitized timeout errors in a follow-up. |

The remaining direct packages were inventoried and included in ecosystem advisory scans; they were not individually feature-migrated. Major jumps in React Dropzone, react-simple-maps and jsdom need their own caller/test review. Node type definitions should follow the approved Node 24 runtime, not the registry's Node 26 latest tag.

## Additional findings

- `ai_response_validation.py` logs full Pydantic validation exceptions, which may include rejected input. Replace these with controlled error metadata and prove synthetic input is absent from logs.
- `AppLink` accepts plain `string` and casts to `Route`, weakening typed-route checking for its callers. Tightening this shared contract requires a caller migration.
- Python 3.14.6, Node 24.18.0, uv 0.12.0 and pnpm 11.18.0 match the approved global baseline. Application runtimes were not changed. CI Terraform 1.6.6 differs from global 1.15.8; infrastructure tooling is a separate compatibility decision.

## Validation and delivery

| Check | Result |
|---|---|
| Real OpenAI SDK lifecycle regression | All six cases failed before the fix because the HTTP client stayed open; pass after the context-manager change. |
| Real Tiptap state regressions | Two stale-state failures before the fix; both pass after subscription adoption. Six editor/sibling files pass 19 tests. |
| Real JWT error contract | Three invalid time-claim cases escaped `TypeError` before the upgrade; all now raise `InvalidTokenError`. |
| Security version guards | Existing guards failed against the old versions and pass against the new manifest/lockfiles. |
| Backend affected suites | **439 tests passed across 52 files**, using `apps/api/run_tests.sh` and a unique migrated database. Covers auth, sessions, MFA, CSRF, OIDC, exports, SDK transports, provider integrations and templates. Ruff passed. |
| Frontend required gate | `pnpm run check`: application TS7 check, ESLint and **2,814 tests across 365 files passed**. |
| Test-project native compiler | Still 358 pre-existing diagnostics across 75 test files; diagnostic-code counts unchanged after the new editor tests. No new required gate. |
| Dependency advisory scans | CI-equivalent pip-audit guard passed without advisories; pnpm guard reports no known vulnerabilities. The separate Next 16.3.8 hold above remains. |
| Lockfile review | Python: only PyJWT and urllib3 versions changed; 139 packages retained. npm: only selected packages and the coupled Next environment/native compiler family changed. |
| Production builds | macOS Webpack build and Linux amd64 standalone Docker build passed. Frozen installation kept package-age, trust and build-script policies. |
| Local container smoke | `/health` 200, allowed-host `/login` HTML 200, referenced JavaScript asset 200, unknown-host `/automation` 404. Container and image removed. No authenticated browser session was exercised. |
| Independent review | No concrete regression found in the task-owned SDK, schemas, editor subscriptions or Vitest integration. |

[Validation record](validation.json) includes installed versions, affected backend files, frontend snapshot hashes and container smoke responses.

An unrelated workflow refactor appeared during validation and caused two type errors in the shared checkout. Frontend checks and builds therefore used an isolated `git archive` of the baseline plus the 12 explicitly owned web files. Their bytes were verified against the working tree. Concurrent workflow and responsive-hook changes were not edited or included. The initial container smoke used a loopback Host header and correctly received the production tenant rejection; the corrected smoke used the configured allowed host without making external requests.

No services remain running from this task; disposable databases were verified removed. No provider messages, production writes, push, deployment or telemetry activation occurred. Changes are committed locally in separate security, SDK, schema, editor, test-tooling and documentation commits.
