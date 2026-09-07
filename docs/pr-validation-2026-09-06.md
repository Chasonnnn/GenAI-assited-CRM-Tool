# PR validation — September 6, 2026

Base: `origin/main` at `6b617131ba41979c0cf40c2aa4def91b8f76ce15`. Existing local work was committed before implementing PR findings. PR patches were reviewed as findings; bot commits and scratch files were not adopted.

| PR | Finding | Disposition |
| --- | --- | --- |
| [#660](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/660) | Stage reference resolution performs repeated queries | Valid; curated bulk resolver preserves key-before-slug precedence, aliases, ordering, and tenant scope. |
| [#665](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/665) | Campaign explicit-stage validation repeats queries | Valid; consolidated with #668/#675, preserving inactive donor-stage rejection. |
| [#668](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/668) | Campaign queries; dependency updates | Campaign duplicate of #665/#675; dependencies reviewed separately. |
| [#675](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/675) | Campaign queries; dependency updates | Campaign duplicate of #665/#668; dependencies reviewed separately. |
| [#671](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/671) | Default permission seeding queries per permission | Valid; curated bulk lookup preserves explicit denials and idempotence. Scratch scripts and `.orig` files excluded. |
| [#667](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/667) | Add Interview icon button lacks an accessible name | Valid; fixed with a named-button regression that also opens the editor. |
| [#676](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/676) | Booking URL input lacks an accessible name | Valid; fixed with a named, readonly textbox regression. |
| [#678](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/678) | Organization checkboxes lack accessible names | Invalid; wrapping labels already supply names through Base UI. Rendered checks verified the selection and organization labels. |
| [#670](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/670) | Notification menu trigger lacks expanded state; dependency updates | UI claim invalid: Base UI already supplies `aria-expanded`. Dependency updates reviewed separately. |
| [#629](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/629) | Blanket COEP enforcement; dependency update | Dependency fix already present; blanket COEP is unsupported for the current document/resource architecture. |
| [#659](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/659) | Blanket COEP enforcement | Unsupported as a required fix; no demonstrated exploit or resource-compatibility validation. |
| [#664](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/664) | Blanket COEP enforcement | Duplicate unsupported COEP proposal. |
| [#666](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/666) | Blanket COEP enforcement; dependency updates | Dependencies consolidated; blanket COEP excluded. |
| [#669](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/669) | Blanket COEP enforcement; dependency updates | Dependencies consolidated at newer fixed versions; blanket COEP excluded. |
| [#672](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/672) | Blanket COEP enforcement; dependency update | pypdf consolidated at a newer fixed version; blanket COEP excluded. |
| [#674](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/674) | Title claims COEP; actual diff updates dependencies | Browserslist duplicate, covered by exact patched pin. |
| [#677](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/677) | Title claims COEP; actual diff updates dependencies | Browserslist duplicate, covered by exact patched pin rather than floating range. |
| [#673](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/673) | Metrics isolation, dependency updates, and deletion of tracked runbooks | Metrics finding is valid; curated fix committed as `f79a9d8f`. Runbook deletion is excluded. Author-owned mixed PR remains open for the separate documentation decision. |

## Release boundary

Cloud Build deploy triggers were inspected live: API/worker and frontend deploy only on `surrogacy-crm-platform-v*` tags. Pushing `main` starts CI and Release Please; it does not deploy production. Release PRs remain open and no release tag is created by this validation loop.

The production-copy rehearsal verified the prior migration source and preserved all existing rows. Subsequent PR fixes and dependency updates require full local and CI gates. A full service cutover under concurrent traffic remains unrehearsed; this audit does not remove that release gate.

## Verification

- Backend: 2,951 non-migration tests passed after a clean locked dependency sync; no warnings.
- Migrations: 67 tests passed in a separate disposable PostgreSQL 18.1 database.
- Frontend: typecheck, ESLint, and 1,507 tests across 266 files passed after frozen-lockfile installation.
- Ruff and diff checks passed.
- Query regressions measured stage resolution at one SELECT, campaign normalization at no more than three, and permission seeding at one. Ordering, aliases, key/slug collisions, tenant isolation, inactive stages, and existing denials are covered.
- Metrics regressions cover request-pool exhaustion, response and event-loop responsiveness, saturation, immutable tenant metadata, sanitized failures, and bounded shutdown.
- The initial backend run exposed the expected request-pool query reduction (8 to 7) and a missing declared Starlette test transport. Both were corrected and the complete backend suite rerun.
- UI label regressions failed before the fixes. React Doctor noted the unchanged booking-URL hydration fallback; no new issue was introduced by the labels.
- Protected `main` rejected direct push because eight checks are required. The committed work is published through [PR #679](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/679) on `codex/release-readiness-0906`; it has not been merged.
- The first PR CI run passed seven required gates, including security scans and all production image builds. Its backend failure reproduced locally with `ATTACHMENT_SCAN_ENABLED=false`: the case download test depended on local scan configuration. The test now explicitly enables scanning; 34 case/attachment regressions passed under CI defaults. Product behavior is unchanged.
- PRs #629, #659, #664, and #678 were closed with validation evidence. Thirteen valid or mixed PRs are listed for closure after #679 merges; #673 remains open for the separate documentation decision.
- Passing CI on the final PR head remains mandatory before merge or release approval.

## Replacement commits

- `27134f14`: accessibility fixes for #667 and #676.
- `d53ae45a`: query batching and tenant-scoped stage lookups for #660/#665/#668/#675/#671.
- `f79a9d8f`: bounded metrics persistence from the valid #673 finding.
- `afb34645`: pypdf 6.17.0 and Starlette's test-only transport dependency.
- `e4b83241`: exact Browserslist 4.28.7 and security guards.

No bot scratch files, global COEP headers, or runbook deletions were adopted.

## Dependency and COEP evidence

Browserslist 4.28.7 fixes [GHSA-c83g-rgw3-j3cx](https://github.com/advisories/GHSA-c83g-rgw3-j3cx) and [GHSA-73wf-gq98-2v4g](https://github.com/advisories/GHSA-73wf-gq98-2v4g). The old lock resolved 4.28.4. These are build-tool dependencies; production exploitability was not demonstrated.

pypdf 6.17.0 fixes the September 4 [Roman-label advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-qv6h-rv94-w285), beyond the PRs' 6.16.1 target. Current CRM usage merges internally generated exports; no application page-label, outline, or text-extraction calls were found.

The [COEP specification](https://wicg.github.io/cross-origin-embedder-policy/#integration-fetch) governs document resource loading. Adding it only to API responses does not isolate frontend documents. Applying it globally to Next.js documents requires resource-compatibility testing: `PublicFormHeader.tsx` renders remote unoptimized logos without a CORS request attribute, so compatibility depends on remote response headers. An OAuth failure was not demonstrated. These scanner findings do not justify blanket header changes in this release.

Metrics persistence is explicitly best effort: one outstanding write per process, a dedicated connection, bounded database timeouts, and no request delay when saturated. Metrics may be dropped under contention. Authenticated organization metadata is copied before submitting the job; exception text is not logged.
