# Validated dependency upgrades

Date: 2026-09-07. Starting revision: `35333b28`. Scope: the audit's Next.js and Google GenAI upgrade candidates, required compatibility changes, and the reusable skill. Earlier Vitest 5 and DOMPurify changes remain in place. Other candidates in REPORT.md remain deferred.

## Changes and adoption

| Dependency | Previous → installed | Local adoption and evidence |
| --- | --- | --- |
| Next.js and bundle analyzer | 16.3.0 → 16.3.4 | Matching framework/plugin versions; current patch fixes. Type checking now generates route types before running the native TypeScript compiler. |
| google-genai | 1.61.0 → 2.22.0 | Replaced the legacy Vertex client flag with `enterprise=True`; real SDK transport tests cover Gemini and all three Vertex configurations. |
| google-auth | 2.48.0 → 2.57.1 | Required by GenAI's newer auth minimum. WIF adapter now supplies naive UTC expiry at the google-auth boundary and converts to aware UTC for its own refresh comparison. |
| grpcio | 1.76.0 → 1.83.1 | Removes the new google-auth PQC compatibility warning. Existing grpcio-status 1.76.0 remains resolver-compatible; local RPC and protobuf status conversion pass. |

Next's patch release notes describe routing, headers, image caching and build corrections. No new application caching semantics are enabled. See [16.3.1](https://github.com/vercel/next.js/releases/tag/v16.3.1), [16.3.2](https://github.com/vercel/next.js/releases/tag/v16.3.2), [16.3.3](https://github.com/vercel/next.js/releases/tag/v16.3.3), and [16.3.4](https://github.com/vercel/next.js/releases/tag/v16.3.4).

The installed Next.js TypeScript CLI integration resolves `typescript/package.json`, which is this repository's TS6 API compatibility alias. Enabling that integration would not select the separate TS7 executable. `next typegen && tsc --noEmit` preserves native type checking with fresh generated routes. `experimental.useTypeScriptCli`, cacheComponents, partial prefetch, offline support and Rust compiler gates remain unchanged. This decision is based on the installed version's docs and `dist/lib/typescript/runTypeScriptCli.js`.

GenAI 2.0's breaking changes affect Interactions, which this application does not use. Existing GenerateContent, streaming and audio-parts paths are exercised through the actual installed library. See [2.0 migration release](https://github.com/googleapis/python-genai/releases/tag/v2.0.0), [2.22 release](https://github.com/googleapis/python-genai/releases/tag/v2.22.0), and [official changelog](https://github.com/googleapis/python-genai/blob/main/CHANGELOG.md). No new agent or Interactions workflow was introduced.

The initial SDK test exposed a real expiry comparison failure in google-auth: its base credentials class compares expiry against naive UTC. The new regression covers `.expired` and WIF request authorization. Application timestamps remain aware outside that library boundary.

Google-auth's new import warning required grpcio >=1.83.0. The runtime upgrade adopts gRPC's default PQC TLS support; the local insecure loopback check verifies runtime compatibility, not a live TLS negotiation. See [gRPC 1.83.0](https://github.com/grpc/grpc/releases/tag/v1.83.0) and [1.83.1](https://github.com/grpc/grpc/releases/tag/v1.83.1). No grpcio-status or protobuf upgrade was necessary to satisfy their declared constraints.

## Validation

- Frontend `pnpm run check`: 266 test files, 1,507 tests passed; native type checking and ESLint passed.
- Next.js 16.3.4 production webpack build: passed.
- `pnpm install --frozen-lockfile` and `pnpm run typecheck:compat`: passed.
- Focused actual-SDK and provider tests: 19 passed, including four actual HTTP transport configurations.
- Backend final full suite: 3,033 passed with no warnings in 125.32 seconds, after migrations on a fresh disposable database.
- `uv sync --frozen --extra test`: passed; obsolete rsa installation removed.
- Ruff for all changed Python files: passed.
- gRPC loopback RPC, existing grpcio-status/protobuf conversion, and google-auth gRPC import with FutureWarning treated as error: passed.
- No live model requests, authenticated browser QA, production deployment, or performance improvement claim. Provider transport fixtures use synthetic data; backend suite uses a disposable local Postgres database.

## Skill

Created `dependency-modernization` in the personal skills repository and linked it for Codex discovery. The audit corrected incomplete rollback guidance and reran structural validation plus static scenario review. See SKILL-AUDIT.md for source hashes, the finding, revision, and evidence limits. The skill has not been behaviorally validated across held-out projects.

## Local delivery

- CRM `45ae8659`: Next.js and route type generation.
- CRM `60e804e5`: Google SDK, authentication/gRPC compatibility, and WIF expiry regression.
- Personal skills `ee7fbdb`: audited dependency-modernization skill and catalog entry.
- Task-owned Postgres container stopped and removal verified. Disposable database was dropped by the test runner.
- No push or deployment performed.
