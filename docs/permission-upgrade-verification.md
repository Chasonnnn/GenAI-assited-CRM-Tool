# Permission upgrade verification

## September 22 completion

The selected Team/member navigation and the permission-related module refactors are implemented in the isolated completion worktree for draft PR #691. The current draft is stacked on #690 and incorporates main through `a451fefc`. Application validation ends at `93131b86`; subsequent changes in this delivery record are documentation only. This section supersedes the unfinished-work descriptions in older dated entries below. Release, real-organization activation, and eventual v1 retirement remain separate steps.

### Implemented changes

- Workflow dispatch delegates record, task, intake, and communication actions to separate modules. Required approval-task creation fails closed during initial and resumed execution.
- Campaign definition CRUD, audience queries, content snapshots, run scheduling/retry, execution materialization, delivery, and suppression have explicit service owners. Existing consent, authority, locking, and delivery checks remain in those paths.
- Form matching retries now commit or roll back reset, matching, lead creation, and audit together. Automatic donor matching honors current record scope.
- Dashboard attention rows and counts share authorized query builders. Donor drill-downs ignore deleted history stages consistently with dashboard counts.
- AI-approved email delivery serializes with activation and checks current v2 action permissions, record scope, membership, and organization AI availability before provider admission.
- Admin/Dev can manage explicit collaboration for any active staff member from record Actions or the member page. The grant adds record scope only. Donor Assign and Claim are independent from Edit.
- Roles, People, and Check access share navigation. People retains the existing Team list and separate member pages, with search and readable role filters. Defaults remain in preview; record overview collaborator cards and donor header photo controls remain absent.

### Validation

| Check | Result |
|---|---|
| Complete API suite | 3,999 passed in the repository disposable-database runner, including migration and outbox tests |
| Final frontend checks | TypeScript, ESLint, 286 files / 1,758 tests passed |
| Python checks | Ruff passed across application and tests |
| Production web build | Passed with the task's local QA API endpoint |
| Migration history | Single additive head `20260922_1600_permission_heads`; upgrade regressions cover both prior heads and preserve existing policy versions |
| React Doctor | No errors; nine performance suggestions in existing role/member loops. No numeric score requested and no source uploaded |
| Setup portability | All four setup cases pass on macOS with an isolated `dpkg` test double; Linux setup behavior is unchanged |

The API command was `PATH=<task-pg-wrappers>:$PATH TEST_DATABASE_PORT=5558 apps/api/run_tests.sh`. Each invocation created, migrated, and dropped a unique local database in the task-owned PostgreSQL 18.1 container. Frontend validation used the repository-pinned runtime and `pnpm run check`; the production build used `pnpm run build`.

### Browser and activation evidence

Real Chromium journeys used the production frontend and real authenticated API sessions against synthetic data. Intake approved a surrogate, egg donor, and sperm donor; a Case Manager claimed each through the UI. Authenticated reads verified persisted ownership and retained Intake access. A different organization's Admin received 404 for each record. Removing collaboration through record Actions caused 403 on Intake's next request for all three types; the denied donor page exposed neither the record name nor edit controls.

An Admin added an Operations user from the donor Actions dialog, saw the same grant on that member's page, and removed it there. The record endpoint then returned an empty collaboration list. People search/empty results, member navigation, protected Admin controls, reviewed role save/reload/restore, and the visibility-only access checker passed. The role-details error/retry journey exposed a migration-tab display bug; its regression and fix keep upgrade navigation tied to the organization's policy version. The rebuilt standalone frontend passed the final error/retry recheck; the upgraded organization no longer displays Review upgrade during the error. Unit tests cover loading, inactive recipients, mutation errors, and independent collaboration capabilities.

Inspected [desktop Roles](verification/permissions-2026-09-22/roles-desktop.png), [mobile Roles](verification/permissions-2026-09-22/roles-mobile.png), [dark Roles](verification/permissions-2026-09-22/roles-dark.png), [People search](verification/permissions-2026-09-22/people-filtered.png), [collaborators](verification/permissions-2026-09-22/record-collaborators.png), and [access checker](verification/permissions-2026-09-22/access-checker.png) screenshots show readable controls and no page-level horizontal overflow at 390 px. Role buttons scroll within their own row.

The isolated activation rehearsal preserved three historical approved records across two synthetic organizations. Three unresolved handoffs, one individual revoke, and two existing execution items blocked activation. A membership change invalidated an earlier review. The revised review activated Alpha only, retained three verified Intake collaborators, disabled its organization workflow, and canceled its scheduled campaign; Beta stayed on v1. This rehearsal used current-schema synthetic history, not a production data copy, paused workflow execution, or running campaign run. Upgrade and execution-path tests cover those separate boundaries.

Sanitized results are retained in [results.json](verification/permissions-2026-09-22/results.json). Provider delivery was mocked in tests; no real messages, production migration, release, or real-organization activation occurred. Current GitHub checks must be evaluated at the published head; older green checks do not validate this completion.

## September 20 continuation

Draft #690 now incorporates fetched main through #716 and #717 at [the platform integration](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/29ee3fae1876eaaccfe01cf23d82bb00f2a800c3). Draft #691 incorporates that branch, reconciles the new interview-appointment lifecycle with v2 authorization, enables CI for its stacked PR base, and extracts three intake workflow actions without changing behavior. The final application source for the checks below is [the intake extraction](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dd738446083881806fc247e2aab937c17278d565); subsequent workplan edits contain no application changes.

**Permission frontend acceptance and broader modularization remain unfinished.** No new permission screen, record collaborator card, donor photo control, permission default, or production activation was added in this continuation. Donor Owner and member-settings collaboration controls still require review. The workplan identifies the remaining workflow, campaign, intake-transaction, and reporting boundaries.

| Check | Result |
|---|---|
| `uv run -m pytest tests/ -q --tb=short --ignore-glob 'tests/test_migration_*.py' --ignore tests/test_email_delivery_outbox.py -n 2 --dist loadscope` | 3,553 passed on the final application source |
| `uv run -m pytest tests/test_migration_*.py tests/test_email_delivery_outbox.py -q --tb=short` | 98 passed; non-overlapping with the preceding selection |
| `pnpm run check` | TypeScript and ESLint passed; 284 files / 1,703 tests passed |
| `pnpm build` | Production standalone build passed; rendered checks used this output |
| `uv run -m pytest -q` in `apps/ops-cli` | 19 passed |
| Workflow extraction | 117 baseline tests passed before moving code; 245 workflow/intake tests passed afterward, including seven new dispatcher contracts |
| Changed API Python surfaces / new files | Ruff passed; new intake module and tests passed formatting checks |
| Fresh database `alembic upgrade head` and `alembic check` | Single head `20260920_0310_permission_heads`; no new upgrade operations detected |
| Existing permission-schema upgrade | Synthetic activated-v2 and v1 organizations retained their policy versions and configuration revisions (7 and 3); schema check passed |

The final API selections total **3,651 tests**. Focused selections overlap and are not additive. The platform-only pre-integration checks passed 83 focused API tests, two migration upgrade tests, TypeScript, and 149 frontend tests. These do not claim a separate full platform-only suite run.

The first combined API run had four fixture failures because the disposable database role could not disable system triggers or set `session_replication_role`. The local disposable role was configured consistently with CI, and both subsequent full runs passed without test exclusions. The first frontend run retained an obsolete permission assertion for `Log Interview Outcome`; it now asserts that current main's retired control remains absent. CI's new stacked-base regression failed before the filter correction and passed afterward; push and release triggers were not broadened.

Real-browser checks used a separate synthetic v2 organization and the production standalone frontend. Admin opened the inherited appointment manager with Reschedule/Cancel controls. Operations saw disabled Manage, Change Stage, and Send Email controls. Inspected screenshots showed readable, unclipped appointment states. Both donor types had zero enabled inline edit controls and no photo/upload or collaborator controls; the surrogate also had no collaborator card or retired outcome action. API regressions separately cover each required appointment action, cross-organization denial, collaborator revocation despite appointment ownership, cancellation/rebooking, idempotent retry, and revoked retry. No appointment notification was sent during browser checks.

These rendered checks are focused integration evidence, not acceptance of the People/role/member designs. The complete three-record browser handoffs and production-shaped activation rehearsal documented below were not repeated in this continuation. Docker image builds were not rerun locally. Repeat these gates on the final accepted version and inspect actual GitHub check results before merge; neither local checks nor an absent remote check means CI passed. Release and real-organization activation remain separately authorized.

## September 19 scope correction

The record-page **Intake collaborators** card and its Add/Remove controls were unrequested and have been removed from surrogate and donor overviews. Earlier screenshots and browser results involving that card document a historical implementation, not approved product UI. Backend collaboration retention and the separate member-settings controls remain unchanged; this correction does not establish user approval of either.

Both new page regressions failed before removal. After removal, `pnpm test tests/surrogate-detail.test.tsx tests/donor-detail.test.tsx` passed all 87 tests; focused ESLint and `pnpm run typecheck` also passed. Browser checks against a disposable database containing retained collaborators confirmed that surrogate, egg-donor, and sperm-donor pages display no collaborator card or picker and make zero collaborator resource requests. Inspected screenshots preserve the record/profile and Activity sections, plus donor Owner controls. These targeted checks cover this removal; the broader results below predate it. Nothing was pushed or activated in production.

## September 19 combined integration

The local platform branch incorporates `origin/main` through [PR #714](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/714); the local permission branch incorporates that refreshed platform branch. The original local `main` was not moved. No remote branch update, GitHub merge, deployment, production migration, production activation, or provider send is represented by this verification.

The permission project is **not complete**. Production Roles, existing team/member access controls, a visibility-only Check access screen, and activation review exist. The unified People mockup is not implemented as one screen. Live frontend/design acceptance and the remaining workflow, campaign, form-review, and reporting/cache modularization are separate open work.

### Final automated checks

Commands ran from the relevant app directory with the pinned `mise` runtimes. API tests used disposable PostgreSQL 18.6 databases.

| Check | Result |
|---|---|
| `uv run -m pytest tests/ -q --tb=short --ignore-glob 'tests/test_migration_*.py' --ignore tests/test_email_delivery_outbox.py -n 2 --dist loadscope` | 3,488 passed |
| `uv run -m pytest tests/test_email_delivery_outbox.py tests/test_migration_*.py -q --tb=short` | 96 passed; non-overlapping with the preceding selection |
| `pnpm run check` | TypeScript and ESLint passed; 283 Vitest files / 1,676 tests passed |
| `pnpm build` | Production build passed; browser handoffs used the standalone output |
| API and web Dockerfiles, final combined source | Both production images built successfully; images were local only |
| Ruff on changed API Python files relative to `origin/main` | All 167 files passed |
| Dependency audit guards | API audit guard passed; frontend audit reported no known vulnerabilities |
| Empty database `alembic upgrade head` and `alembic check` | Single head `20260919_0200_permission_heads`; no new upgrade operations detected |
| Existing-schema upgrade and activation rehearsal | Passed on the final application code with the synthetic history described below |

The API selections total **3,584 tests**. Focused tests overlap and are not added.

Integration regressions were reproduced before fixes for donor profile/reveal scope, Create versus Edit in intake promotion, deferred organization workflow authority, shared read-only editors, and revocation while editing. Final validation also exposed two concrete concurrency bugs: status changes captured inconsistent current times around a database lookup, and the permission configuration row lock blocked audit foreign-key checks. The latter now uses PostgreSQL `NO KEY UPDATE`; an independent-session regression proves audit appends can proceed, competing configuration changes remain serialized, and the audit hash chain stays linear.

An earlier overloaded run failed a Google Tasks heartbeat timing assertion and exposed the status-clock race. The final suite passed without relaxing assertions or excluding those tests. An earlier pool/autocommit fixture setup error did not reproduce in isolation or subsequent full runs. Three inherited Python files have pre-existing formatting differences; unrelated formatting was not included.

### Final browser handoffs use real application requests

On the production standalone web build, a synthetic Intake user approved a surrogate, egg donor, and sperm donor. Each moved into its claim pool while retaining Intake collaboration. A Case Manager claimed each through the UI; persisted ownership was checked through authenticated API requests. Removing Intake collaboration through the UI caused HTTP 403 on Intake's next record requests and donor profile request. The donor page then displayed a permission-denied state without the record name or edit controls. The other organization's Admin received HTTP 404 for all three records.

Operations could read the donor but had zero enabled edit controls; seven rendered field editors were disabled. Stage changes, assignment, photo upload, and collaborator removal were absent on the donor page. Surrogate checklist controls and profile editing were disabled as well. The inspected read-only donor screenshot remained readable. The post-fix API process logged no audit failures or tracebacks during these journeys.

The inspected surrogate screenshot shows Approved status and retained Intake collaboration. It does not itself show an explicit owner field; ownership was verified separately from the server response. Earlier integration browser checks exercised Roles edit/save/reload, protected Admin controls, member access, activation, and the narrow visibility-checker result. Those checks are implementation evidence, not approval of every mockup or completion of every frontend interaction state.

### Isolated activation rehearsal preserves organization boundaries

This was **synthetic production-shaped data, not a production-data copy**: two organizations; seven memberships including one inactive member; four surrogates and eight donors; known and unknown historical paused phases; an individual revoke; an old pool grant; an enabled organization workflow with a paused execution; and a scheduled campaign with a running run. Data was seeded using the current-main ORM against revision `20260914_1200_donor_profile`, then upgraded through the combined head.

- All 12 applicant IDs/names and original stage IDs survived. Two donor approval gates were added; known prior donor stages were recovered, and unknown history was not guessed.
- Both organizations remained v1 after schema upgrade. Nine unresolved handoffs, three unknown phases, the revoke, pool grant, and both execution items blocked activation.
- Explicit resolutions were required. A subsequent ownership change invalidated the preview digest.
- The reviewed preview activated Alpha only; Beta remained v1. Nine Intake collaborators and the activation audit persisted. The workflow was disabled, its paused execution canceled, the campaign canceled, and its run failed rather than silently acquiring execution authority.
- Active-v2 downgrade refusal was also checked. Release, real organization review, and actual activation remain separately authorized.

QA browser cookies were cleared. All task-owned services stopped; disposable databases, generated secrets, container scratch data, and temporary scripts were removed. Inspected screenshots remain in the Amp thread artifacts. No live preview is left running.

## Historical September 12 verification

Historical verification: September 12, 2026. Permission foundations are packaged in draft [PR #691](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/pull/691), based on `codex/platform-upgrades`. These results do not establish completion of frontend acceptance or broader module refactors, and do not validate later integrations. No production migration, activation, release, provider send, or deployment occurred.

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
