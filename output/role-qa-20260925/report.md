Local browser QA — September 25, 2026

Tested commit: `c483b0f566025bde0b65a6410499158598238ee7`, the approved combined snapshot containing permission, scheduling, and match changes. Permission policy v2, scheduling v2, and match expansion were enabled in a disposable database with synthetic data. Chrome ran visibly against a production frontend build and the local API.

Four small permission/UI fixes passed verification. Three larger workflow issues remain open, plus one session-creation issue exposed by the test harness. This is not an all-clear for the combined changes.

| Coverage | Observed result |
|---|---|
| Admin, Developer, Intake Specialist, Case Manager, Operations | 27 routes per role; 135 baseline page visits |
| Record scope | Assigned, other-owned, approved, and archived surrogate/egg-donor fixtures; owned and other-owned intended parents |
| Baseline rendering | No uncaught page JavaScript errors, navigation timeouts, or document horizontal overflow; permission/data failures recorded separately |
| Fix verification | 13 role/route assertions passed with no failing HTTP requests |
| Permission states | Loading, failed permission lookup, retry recovery, denied, and allowed states checked |
| Role editor | Admin granted and removed Intake report access; saved changes affected the Intake browser; baseline restored |
| Handoff and revocation | Intake created and approved a surrogate; Case Manager claimed it; Intake retained collaborator access; Admin removal revoked access on reload |
| Tenant isolation | A second organization's Admin received a denied browser state and HTTP 404 for the handoff record |
| Match lifecycle | Case Manager created and accepted a match, requested cancellation; a different Admin approved it in Tasks; final status `cancelled` |
| Scheduling | Stale availability returned an error; manual calendar sync and retry recovered slots; UI reschedule and cancellation persisted; simulated Google sync reached `completed` |
| Mobile | Role editor at 390 × 844 had no horizontal overflow; protected Admin baseline switches were disabled |

[Baseline route results](evidence/route-matrix.json), [fix checks](evidence/fixed-results.json), [role changes](evidence/role-change-results.json), [handoff checks](evidence/handoff-results.json), [match results](evidence/match-results.json), [scheduling results](evidence/scheduling-results.json).

| Open issue | Reproduction and impact | Code evidence and next decision |
|---|---|---|
| High: Case Manager creates a record they cannot reopen | Default Case Manager → Surrogates → create a surrogate. Creation returns 201; the subsequent detail read returns 403 and the browser shows an access error. [Screenshot](evidence/case-manager-created-record.png), [response evidence](evidence/manager-create-results.json). | Creation is permitted while the new pre-approval record falls outside this role's normal scope. Decide whether to grant creator access, change scope, or restrict creation; cover the chosen behavior with denied and cross-org tests. |
| Medium: Operations SMS authoring cannot read templates | Operations → Campaigns → Create Campaign → SMS/MMS → Next. The template picker is empty; `GET /messaging/templates` returns 403. No published templates were seeded, so this confirms the authorization mismatch, not selection of an existing template. [Screenshot](evidence/operations-sms-templates.png), [response evidence](evidence/sms-results.json). | `apps/api/app/routers/messaging.py:362` requires `INTEGRATIONS_MANAGE` for template listing, although this role can author campaigns. Define a scoped template-read permission without granting integration administration; show a request error instead of an empty picker. |
| Medium: Archived donor detail has inconsistent access checks | Case Manager or Operations → direct URL of an approved archived egg donor. The donor header loads, but profile and related-task reads return 403; the page says “Unable to load donor information.” Admin and Developer load the same fixture. [Screenshot](evidence/case_manager-24.png). | `apps/api/app/routers/donors.py:216` allows archived detail reads; the profile route at line 237 uses `_get_or_404` with its default `allow_archived=False`. Decide the archived-read policy and apply it consistently to nested reads. |
| Medium: Same-second session creation can fail | Two QA logins for the same account within one second produced a unique-constraint error on `user_sessions_session_token_hash_key` and HTTP 500. Sequential logins avoided it. | Shared `create_session_token` in `apps/api/app/core/security.py:34` has no per-session nonce; identical claims within one second produce the same JWT. `session_service.py:73` stores a unique token hash. Observed through development login; production OAuth reproduction was not performed. Add a deterministic concurrent-session regression before changing shared auth. |

| Isolated fix | Before | After |
|---|---|---|
| Reports access | Intake direct navigation mounted partial reports and issued forbidden analytics requests | Permission checks complete before report hooks mount |
| Team settings access | Unauthorized staff saw misleading member counts and request errors | Denied/loading/error states precede member and invitation hooks |
| Appointments and availability settings | Operations mounted appointment requests that returned 403 | Both surfaces use the existing permission states before loading data |
| Task calendar | Operations task calendar also requested forbidden appointments | Tasks remain available; appointment fetching requires `manage_appointments` |

[fixes.patch](fixes.patch) contains six production files and four test files, based on `c483b0f`. Applying the patch to a clean copy of those baseline files reproduced all ten tested files byte for byte. The patch was not applied to the user's working checkout. `origin/main` advanced to `9bb158ed` during QA, and concurrent source edits were present; those changes were outside the initial browser pass.

| Validation | Result |
|---|---|
| Reports/team regression tests | Four new assertions failed before the fix; all 13 tests passed afterward |
| Appointment/task access regressions | Four assertions failed before the fix; all 51 focused tests passed afterward |
| `cd apps/web && mise exec -- pnpm run check` | Type checking, ESLint, 292 test files and 1,808 tests passed |
| Production build | Passed |
| React Doctor 0.9.14, six changed production files | Two unchanged findings: ReportsQuickStatsGrid complexity and the browser-global booking-link fallback in AppointmentSettings. Neither was introduced or modified by this patch |

[Frontend validation log](checks/frontend-check-final.log), [build log](checks/web-build-final.log), [regressions before](checks/regression-before.log), [regressions after](checks/regression-after.log), [appointment regressions before](checks/appointment-before.log), [appointment regressions after](checks/appointment-after.log), [React Doctor diagnostics](checks/react-doctor.log).

The 135 visits are navigation and rendering checks, not 135 complete workflows. Full API suites, live OAuth/provider delivery, public token booking flows, sperm-donor handoffs, every match/campaign branch, permission policy v1, and the newer `origin/main` were not browser-validated in this pass. No backend production code changed. Calendar calls used the existing guarded synthetic transport; no real messages were sent.

The task-owned API and frontend processes exited, and ports 8017 and 3047 closed. The disposable database was dropped; the shared PostgreSQL service remained running. Temporary environment files, provider state, dependencies, and the isolated source copy were removed after the verified patch and selected evidence were saved. No push, PR, or deployment was created.

The fixes were subsequently committed on `fix/role-qa-permission-gates`, based on `origin/main` at `9bb158ed`: `c315fa88` (reports), `72aa18c6` (team access), and `b1a04635` (appointments and task calendar). All ten files match the verified QA patch. Type checking, lint, and all 1,808 frontend tests passed again on this branch. [Commit record](commits.json), [validation log](checks/commit-frontend-check.log).
