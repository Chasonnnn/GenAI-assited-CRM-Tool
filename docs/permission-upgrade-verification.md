# Permission upgrade verification

Date: September 12, 2026. The completed upgrade is packaged in draft [PR #691](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/691), based on `codex/platform-upgrades`. No production migration, activation, release, provider send, or deployment occurred.

## PR branch validation

Application code at `bbfd6907055d42a2ce8cc61b012ec20919d84c71` passed validation in an isolated checkout of `codex/permission-v2`:

| Check | Result | Evidence |
|---|---|---|
| Full API suite, excluding serial selections | 3,387 passed | [API log](verification/permissions-2026-09-12/pr691/api-tests.log) |
| Serial migration/outbox suite | 94 passed | [Migration/outbox log](verification/permissions-2026-09-12/pr691/migration-outbox-tests.log) |
| Frontend TypeScript, ESLint, Vitest | 281 files, 1,644 tests passed | [Frontend log](verification/permissions-2026-09-12/pr691/frontend-check.log) |
| Changed Python files | 38 passed Ruff and formatting | [Source manifest](verification/permissions-2026-09-12/pr691/source-sha256.json) |
| Empty-database Alembic upgrade | Passed through `20260907_2220_work_authority` | [Migration log](verification/permissions-2026-09-12/pr691/fresh-migration.log) |

The API selections total 3,481 tests. This run used the PR prerequisite branch's locked Next.js 16.3.4, Vitest 5.0.0, and google-genai 2.22.0. Gemini 3.8 configuration, the Gemini-to-permission migration dependency, and the PR's existing Tasks-independent scope test were preserved. Initial transfer testing caught a model-setting mismatch with the older main checkout; it was corrected before this final run.

The seven application commits cover default access, independent record creation, organization workflows, campaign visibility, manual template delivery, staff AI access, and Permission Studio. Documentation and evidence form a separate commit. Browser screenshots below were captured during the original main-based implementation verification; browser QA was not repeated on the stacked PR branch. The branch validation above supersedes the original automated counts below for this PR.

## Delivered behavior

- The approved option 1 layout groups Surrogates, Donors, Intended Parents, Operations, and Administration. Operations contains workflow, template, campaign, and supporting-tool subpermissions.
- Record scope remains separate from actions. Create and Edit are independent for donors, surrogates, and intended parents, including import and intake-promotion entry points.
- Every active member receives personal workflow, template, and campaign authoring. These defaults appear in the preview and are excluded from role, individual-addition, and carryover editors.
- Organization-enabled AI is available to ordinary staff. Provider configuration remains Admin/Dev-only. AI proposals, approvals, task chat, and linked-record actions recheck current authority; human review remains required for sending.
- Admin and Dev remain protected. Supplied role baselines, individual additions, collaborator access, and role changes use reviewed, organization-scoped administration.
- Surrogate and donor approval handoffs retain Intake collaboration. Shared record filters cover lists, counts, details, linked work, search, and reporting.
- Personal execution rechecks current owner authority. Organization workflow/campaign execution survives proposer departure and retains contributor credit.
- Campaign previews, recipient pagination, and visible run counts follow the viewer's record scope. Durable organization execution keeps its separately authorized audience.
- Platform-template copies require organization-template management. New manual template email jobs recheck active membership, Send permission, template access, and linked surrogate scope before delivery. Revoked retries with uncertain provider outcomes require reconciliation.
- Existing organizations remain on version 1 until their exact reviewed activation. Default-feature revokes require explicit removal; they cannot become role denials. Version 1 compatibility remains covered.

## Original implementation automated results

| Check | Final result | Evidence |
|---|---|---|
| Full API suite, excluding serial migration/outbox selection | 3,373 passed | [API log](verification/permissions-2026-09-12/api-tests.log) |
| Migration and delivery-outbox suite | 93 passed | [Serial log](verification/permissions-2026-09-12/migration-outbox-tests.log) |
| Frontend check: TypeScript, ESLint, Vitest | 281 files, 1,644 tests passed | [Frontend log](verification/permissions-2026-09-12/frontend-check.log) |
| Ruff on all changed Python files | Passed | 138 files checked; formatting passed |
| Stage and surrogate contract generators | Completed | Generated outputs synchronized |
| OpenAPI path/method/status contract | Passed within API suite | Includes safe AI availability endpoint |
| Full fresh migration chain in two isolated databases | Passed to `20260907_2220_work_authority` | [Test database](verification/permissions-2026-09-12/fresh-migration.log), [QA database](verification/permissions-2026-09-12/qa-fresh-migration.log) |
| Diff whitespace and source manifest | Passed | [Application SHA-256 manifest](verification/permissions-2026-09-12/source-sha256.json) |

The non-overlapping API selections total 3,466 tests. Focused agent runs overlap these suites and are not added to this total. A focused permission run briefly overlapped the migration suite; both completed without failure. The final full API run started after both finished.

Regressions were reproduced before fixing unauthorized library copies, inaccessible template recipients, campaign viewer-scope leaks, queued manual-send revocation, and task-chat ownership. The first full API run exposed a version 1 Dev-bypass regression; the final run passes after restoring only the version 1 behavior and preserving version 2 membership checks.

## Browser verification

The browser used a separate local QA database with synthetic users and records. No external provider request was made.

| Journey | Observed result |
|---|---|
| Approved desktop layout | Five topics, separate scope controls, short ordered actions, preview, and review footer rendered at the reference viewport |
| Role edit | Donor Create change reviewed, applied, and retained after reload |
| Protected roles | Admin controls disabled; protected baseline explanation displayed |
| Operations | Personal-authoring toggles absent; workflow organization management and separate campaign Send visible |
| Individual additions | Included personal/AI capabilities absent from the picker; inherited defaults displayed separately |
| Ordinary staff | Permission administration unavailable; AI controls enabled after synthetic organization configuration, without provider-setting access |
| AI disabled | Access preview displayed Disabled; AI navigation absent |
| Version 1 activation | Unresolved personal-workflow revoke blocked activation; explicit removal and refreshed preview allowed activation for the synthetic organization |
| Access checker | Assigned pre-approval surrogate visible to Intake; same record denied to the post-approval Case Manager |
| Mobile | 390 × 844 viewport; no document horizontal overflow, scrollable role strip, usable scope controls and review dialog |
| Dark theme | Labels, scope controls, selected role, and preview remained readable |
| Console | No errors captured in the final browser session |

Evidence: [desktop](verification/permissions-2026-09-12/desktop-donors.png), [mobile](verification/permissions-2026-09-12/mobile-top.png), [mobile review](verification/permissions-2026-09-12/mobile-review.png), [dark theme](verification/permissions-2026-09-12/dark-donors.png), [activation](verification/permissions-2026-09-12/activation.png), [staff AI](verification/permissions-2026-09-12/staff-ai.png), [denied access](verification/permissions-2026-09-12/access-denied.png), [console](verification/permissions-2026-09-12/browser-errors.json).

Loading, unavailable, empty-addition, protected, dirty, review, success, and populated states were observed. Detailed request-error, stale-review, revocation, tenant-isolation, CSRF, retry, and linked-record cases are covered by automated tests. Historical approval/handoff migration edge cases were tested automatically; the browser activation used simple synthetic history.

## Delivery boundaries

- The original main-based rehearsal used its existing runtimes and a permission migration following `20260905_1600_record_integrations`. PR #691 instead preserves its prerequisite Gemini migration `20260907_1200`; no dependency manifest or lockfile changes were added by this update.
- The update extends the permission foundation already present in PR #691. Existing prerequisite upgrades remain on its base branch; unrelated donor clinical-record and Google Tasks PRs remain separate.
- Existing generic `organization_email` jobs retain their classification because that source also includes system mail. The explicit manual authority applies to newly queued manual template sends.
- Provider verification, production-shaped activation rehearsal, production release, and each organization's activation remain separate delivery steps. Twilio completion, Meta MCP setup, broader builder redesign, and remaining donor product work are outside this permission milestone.
- Task-owned servers, database container, and temporary QA data are removed after verification. Saved screenshots, logs, and source fingerprints remain in the repository.
