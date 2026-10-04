# Dependency follow-up — October 1, 2026

## Implemented

- Next and its analyzer: 16.3.7 → 16.3.8. The user approved a release-age exception for exactly eleven matching packages. The 24-hour policy, integrity checks, trust policy and build permissions remain in place. These exceptions can be removed after **October 1 at 12:07:22 EDT**. [Verified package timestamps](next-release-times.json); [security release](https://nextjs.org/blog/september-2026-security-release).
- Native TypeScript 7: **358 test diagnostics across 75 files → zero**. Required fixtures, checked array access and API mocks now match their contracts. `OrgMember.last_login_at` accepts the null values already returned by the API. Test assertions remain intact. `typecheck:tests` now runs in `pnpm run check` and CI. TypeScript 6 remains available for compiler-API consumers.
- FastAPI: 0.136.3 → 0.142.2, with OpenTelemetry SDK/API/protobuf 1.45.0 and instrumentation 0.66b0. Native server, dependency, endpoint, serialization and background-task spans replace contrib FastAPI instrumentation. HTTPX, Requests and SQLAlchemy tracing remain connected. [Architecture decision](../../docs/adr/0007-private-lifespan-owned-tracing.md).

## Telemetry contract

Sanitization occurs before queueing and OTLP transmission. Tests inspect serialized protobuf for synthetic secrets in token routes, queries, SQL, exceptions, scope metadata, headers and tracestate. A temporary sanitizer bypass made the payload privacy assertion fail; the restored implementation passes.

Providers and transports belong to the application lifespan. Tests cover restart, partial startup failure, collector failure, shutdown cancellation, queue saturation and late spans. Exact health paths suppress native and child instrumentation. Native logs, native metrics and environment-driven automatic exporters are disabled on both FastAPI apps. SDK and client-instrumentation metrics use no-op providers.

Existing trace-context propagation is retained. The privacy filter governs exported traces and telemetry logs; it does not rewrite application request headers. Production collector activation remains controlled by `OTEL_ENABLED` and the configured endpoint.

## Verification

Frontend verification passed 2,833 tests, native application/test type checking and lint. macOS and Linux production builds passed, followed by actual HTTP checks against the Linux standalone container. Builds used the stable starting tree plus this task's changes to avoid concurrent workflow-editor edits; the full frontend check also passed on the tree committed as `149a7b8e`.

Backend verification passed 5,047 tests and 503 subtests using the CI file split and disposable databases. Coverage was 77.00%, above the 75.85% gate. Thirty focused health, worker, metrics and telemetry tests passed with resource leaks treated as errors; twelve exercise telemetry directly. A real loopback HTTP collector received eight sanitized spans in two OTLP batches. Both dependency advisory guards and Ruff passed. [Counts and file hashes](validation.json); [HTTP smoke evidence](smoke-results.json).

One existing migration fixture opens an SQLite connection without closing it in `apps/api/tests/test_migration_20260907_gemini_38_flash.py:33`. Its `ResourceWarning` is unrelated to this migration; that fixture predates this task and was left unchanged.

The earlier audit remains historical evidence: [September 30 audit](../dependency-modernization-20260930/audit.md). No push, deployment or production telemetry activation was performed.

Commits: `149a7b8e` — frontend upgrade and type-check gate; `526423df` — native telemetry migration. Fifteen disposable databases were verified removed. No services started by this task remain running.
