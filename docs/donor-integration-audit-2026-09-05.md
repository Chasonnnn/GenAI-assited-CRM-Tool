# Donor integration and shared-module audit

## Accepted decision and implementation status

Keep separate surrogate, intended-parent, and donor domain records, with shared capability operations and controls. The user approved this refactor across all three modules. Intended-parent and donor detail pages retain lighter layouts than surrogates.

| Area | Current status |
|---|---|
| Shared notes, activity, tasks, documents, record authorization, and common email contact context | Implemented in the current working tree. Local automated and browser evidence is recorded in the verification report; deployed verification remains outstanding. |
| Donor ownership editing | Additive owner-options API and detail controls implemented. Deploy the API before the new frontend. |
| Donor workflow and queued-email subject validation | Implemented across execution, approval resume, source-job admission, and provider dispatch; prior uncertain provider attempts retain reconciliation handling. |
| Beta availability | Accepted unchanged: developer-only sidebar entries, with existing backend permissions. A stricter server-enforced developer-only gate is deferred. |
| Donor appointments, correspondence history, AI context, matching relationships, and SMS | Deferred product/integration work. This refactor does not make these capabilities complete. |
| Delivery | No schema migration is required. Local validation is recorded in shared-record-modules-verification.md. Provider checks, deployment, and uninterrupted production behavior remain unverified. |

The rollout conditions and rollback boundaries are recorded in [shared-record-modules-rollout.md](/Users/chason/GenAI-assited-CRM-Tool/docs/shared-record-modules-rollout.md).

## Original audit baseline

Date: 2026-09-05. Source revision: `930cd7b2`. The coverage, findings, source references, and verification record below describe the code before the approved refactor. They preserve the original audit evidence and do not describe the completed fixes as still open. Scope: local backend, frontend, migrations, tests, and donor workplan. Three parallel audits covered shared backend behavior, frontend parity, and platform integrations. Production state and live provider behavior were not verified.

The donor module already connects to most platform systems. Its main weakness is inconsistent completion of shared behaviors and record-level workflows. Shared storage has reduced duplication, but authorization, transaction ownership, event creation, template variables, and UI actions still differ by caller.

Keep separate surrogate, intended-parent, and donor domain records. Build shared capability modules around their common operations. A new record type should supply its domain rules and an adapter to each supported capability, then inherit that capability's behavior and tests.

## Baseline coverage

“Present” means implementation and relevant test coverage were inspected; it does not mean live integration verification passed.

| Capability | Donor coverage | Remaining work |
|---|---|---|
| Records and pipelines | CRUD, immutable egg/sperm type, D-numbers, separate configurable pipelines, archive/restore, stage history and approval handling | Ownership exists in contracts but lacks a detail-page editing entry point |
| Notes | Shared persistence, sanitization, donor create/delete, activity, scoped endpoints | Generic deletion permission gap; automation bypasses shared writes; inconsistent editors and author display |
| Documents and profile photos | Shared scanning, storage, signed access, deletion and photo handling | Repeated frontend upload/list behavior; shared authorization differs by entity |
| Tasks and calendar | Donor-linked tasks, global task UI/calendar, notifications and Google Tasks integration | Detail page stops at ten open-task previews; appointments cannot link donors |
| Activity and audit | Donor/IP activity feed, durable lifecycle events, shared compliance audit | Surrogates use a separate activity contract; some writers bypass it; feed pagination loads all records |
| Hosted and Meta intake | Donor classification, immutable snapshots, review/promotion, duplicate handling, profile-photo flow for hosted forms | No application/submission entry point from donor detail |
| Automation | Donor triggers, subtype subjects, tasks, assignment, reviewed email and notifications | Archive guard gap on execution/resume; note and email-context divergence |
| Campaigns | Donor audiences, previews, approved snapshots and email delivery paths | Template context differs from workflows |
| Search and reporting | Donor records/notes/files, subtype analytics, dashboard attention and reports | Beta availability differs across entry points |
| Portability and retention | Admin CSV/photo/history import/export, donor cleanup and legal-hold paths | Live migration, provider cleanup and release gates remain separate verification work |
| Correspondence and AI | Campaign/workflow email exists | Dedicated donor correspondence history and donor AI context are absent |
| Matching and SMS | Intentionally deferred | Domain relationship and consent decisions are required |

Existing integration evidence includes [donor workflow tests](/Users/chason/GenAI-assited-CRM-Tool/apps/api/tests/test_donor_workflows.py), [hosted forms tests](/Users/chason/GenAI-assited-CRM-Tool/apps/api/tests/test_hosted_donor_forms.py), [Meta routing tests](/Users/chason/GenAI-assited-CRM-Tool/apps/api/tests/test_meta_donor_routing.py), [campaign tests](/Users/chason/GenAI-assited-CRM-Tool/apps/api/tests/test_donor_campaigns.py), [search tests](/Users/chason/GenAI-assited-CRM-Tool/apps/api/tests/test_donor_search.py), [analytics tests](/Users/chason/GenAI-assited-CRM-Tool/apps/api/tests/test_donor_analytics.py), and [portability implementation](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/admin_export_service.py:554).

## Baseline findings

### 1. Generic note deletion checks the wrong module's permissions

Priority: high. Source-confirmed control flow; HTTP/database reproduction pending.

The generic `DELETE /notes/{note_id}` route accepts any same-organization note, requires surrogate-note permissions, and checks record access only when the note belongs to a surrogate. It can therefore delete a donor or intended-parent note without checking that record type's permissions.

A regression should create a donor note, retain its UUID, revoke the author's donor permissions while retaining surrogate-note view/edit, then compare both delete routes using valid CSRF. The donor-specific route should deny access; the generic route currently has no donor check. The caller must be the author or have the route's management privilege. This is a same-organization permission bypass, not evidence of cross-organization access.

Evidence: [generic deletion](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/notes.py:124), [organization-only note lookup](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/note_service.py:138), [donor-specific deletion](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/donors.py:473).

Related pre-existing inconsistencies: generic attachment operations accept an entity permission but intended-parent resolution only checks organization; task subject access likewise checks IP organization while explicitly checking donor permission. Correct these through actual-subject authorization rather than weakening donor checks. Evidence: [attachment helpers](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/attachments.py:239), [generic download](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/attachments.py:548), [task subject access](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/task_service.py:638).

### 2. Developer-only beta currently means hidden sidebar navigation

Priority: high if donor access must be restricted to the developer.

The sidebar hides Donors for nondevelopers, but donor routes have no developer-only gate. Backend defaults grant donor permissions to intake specialists, case managers and admins. Search, task pickers, reports and dashboard attention also expose donor paths based on permissions rather than beta status.

This does not establish deployed exposure: deployed revision and effective permission overrides were not inspected. It does establish that the current source does not enforce developer-only availability. The workplan deliberately kept backend permissions available for QA, so the distinction needs an explicit product decision.

Recommendation: if the requirement is “only the developer can use donors,” add one server-enforced module availability policy and use its result throughout navigation and global features. Preserve action permissions underneath it. Worker and public-intake behavior need explicit availability rules; interactive role checks cannot simply be copied into those paths.

Evidence: [sidebar gate](/Users/chason/GenAI-assited-CRM-Tool/apps/web/components/app-sidebar.tsx:615), [role defaults](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/core/permissions.py:468), [donor router policy](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/donors.py:41), [detail permissions](/Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/donors/[id]/page.tsx:63), [report access](/Users/chason/GenAI-assited-CRM-Tool/apps/web/components/reports/DonorAnalyticsSection.tsx:41).

### 3. Note behavior changes according to who creates the note

Priority: high for shared-write consistency.

Manual donor notes use the shared sanitizing operation and record a durable activity event. Workflow notes insert `EntityNote` directly, bypassing sanitization, durable `note_added` recording and shared note-trigger dispatch. The activity reader synthesizes an entry while the note exists, so the defect can remain hidden until deletion removes the source row.

Surrogate note writes have a separate transaction problem: creation commits the note before activity; deletion commits activity before deleting the note. A failure can leave missing activity or a deletion event for a note that still exists.

All note callers should use one transaction-aware operation. Record the note and its activity atomically; preserve workflow recursion controls and existing approval rules. Do not call the current committing helper blindly from another transaction.

Evidence: [shared note creation](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/note_service.py:46), [workflow direct insert](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/workflow_engine_adapters.py:1607), [synthetic timeline fallback](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/entity_activity_service.py:346), [surrogate activity commits](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/routers/notes.py:99).

### 4. Workflow execution does not consistently reject archived donors

Priority: high for workflow correctness. Runtime reproduction pending.

Initial donor resolution and action resolution validate organization and subtype but omit archive state. A workflow paused for approval can resume after donor archival and reach actions such as note creation or assignment. Stage changes have their own archive rejection, which makes action behavior inconsistent.

Validate the subject at initial execution and again at resume, delay completion and retry. Test archival between pause and approval, alongside missing-subject, permission-revocation and subtype checks.

Evidence: [execution subject validation](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/workflow_engine_core.py:349), [resume execution](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/workflow_engine_core.py:632), [action subject resolution](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/workflow_engine_adapters.py:366).

### 5. The same donor email template has different variables across features

Priority: medium.

Campaigns use the shared donor template builder. Workflows maintain another implementation: `first_name`, logo and unsubscribe variables are absent; donor type is raw `egg`/`sperm`; queue owner names are absent. The workflow owner lookup also omits the shared builder's active organization-membership check.

Use one template-context builder in preview, approval and delivery. Test the same template through both campaign and workflow paths. These differences do not by themselves establish a delivery-compliance failure; other delivery layers were not exhaustively audited.

Evidence: [workflow variable resolver](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/workflow_engine_adapters.py:1625), [shared donor variables](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/email_service.py:1129), [campaign caller](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/campaign_service.py:88).

### 6. Donor detail lacks complete operational paths

Priority: medium; direct product-completion work.

- Tasks show at most ten open items without opening, editing, completing, paging or linking to all donor tasks. Existing global task controls can supply these actions.
- Ownership is supported by the API and filters but omitted from the donor edit form.
- Hosted donor applications can be reviewed elsewhere, but donor detail has no submission/application entry point.
- Calendar task support exists, but appointment persistence and link contracts support only surrogates and intended parents. Donor appointment/reminder support was explicitly included in the workplan.

Evidence: [donor task preview](/Users/chason/GenAI-assited-CRM-Tool/apps/web/components/donors/DonorTasksSection.tsx:25), [donor edit payload](/Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/donors/[id]/page.tsx:103), [detail composition](/Users/chason/GenAI-assited-CRM-Tool/apps/web/app/(app)/donors/[id]/components/DonorDetailSections.tsx:197), [appointment links](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/schemas/appointment.py:258).

### 7. Activity is partly shared but needs a neutral contract

Priority: medium before wider adoption.

Donors and intended parents share activity persistence and UI. Surrogates retain another writer/store, and the generic timeline still imports surrogate activity/history types and outcome helpers. The donor/IP reader loads all activity, notes, tasks and attachments, sorts in memory, then slices the requested page.

Share the event contract, writers and bounded read interface first. Existing tables can remain behind adapters. Preserve donor/IP safe-metadata events and permission-based preview hydration; surrogate activity retains note previews, so retention behavior requires a deliberate migration decision.

Keep activity, stage history, compliance audit and operational logs distinct: they answer different questions and have different retention and access rules. Donor compliance events already exist; useful audit improvements would be record filters and links.

Evidence: [generic timeline imports](/Users/chason/GenAI-assited-CRM-Tool/apps/web/components/activity/EntityActivityTimeline.tsx:22), [activity loading](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/entity_activity_service.py:255), [pagination](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/entity_activity_service.py:439), [surrogate note previews](/Users/chason/GenAI-assited-CRM-Tool/apps/api/app/services/activity_service.py:234).

## Shared module design

| Module | Interface responsibility | Entity-specific behavior |
|---|---|---|
| Record access | Resolve a record under authenticated membership and authorize an action | Ownership rules, post-approval restrictions, donor subtype and availability |
| Notes | List, add and delete with consistent content handling, author presentation and atomic activity | Subject policy and controlled workflow event dispatch |
| Documents | Upload, scan state, list, download and delete through existing attachment infrastructure | Profile-photo purpose, permitted file use and subject authorization |
| Tasks | Record filtering, create/edit/complete/open and shared list/calendar presentation | Supported relationships, task permissions and archive rules |
| Activity | Safe event recording, permitted previews and bounded ordered pages | Specialized event rendering and lifecycle semantics |
| Communication context | Reviewed recipient identity, display labels and template variables | Channel eligibility, consent rules and record-specific fields |

Start with a small typed record reference containing kind and ID. The backend derives organization from membership and resolves the actual subject; a client-provided reference is never authorization. Use narrow adapters where behavior already differs. Keep TanStack Query as the frontend server-state owner and centralize cache invalidation for capability mutations.

Explicit foreign keys and current domain tables should remain initially. Match tasks deliberately support both surrogate and intended-parent links; a universal single-subject constraint would break that behavior. Egg/sperm pipeline rules, pregnancy tracking, intended-parent relationships and donor matching decisions belong to their domain modules.

Shared UI should include the existing loading, empty, error, retry, author and action states. A generic card wrapper alone would leave the current behavioral differences intact. Start notes/documents adoption with donor and intended parent, then adapt the richer surrogate surface without removing its behavior.

## Delivery sequence and acceptance

| Step | Work | Acceptance |
|---|---|---|
| 1 | Fix actual-subject permissions; resolve beta availability policy | Generic and entity-specific routes agree; denied permissions and cross-org IDs are rejected; beta rules hold across direct routes and global entry points |
| 2 | Consolidate note writes, workflow subject checks and template context | Atomic note/activity rollback; manual/workflow sanitization parity; durable deletion history; archived resume rejection; identical template output |
| 3 | Complete donor task actions, ownership and application navigation | Create, assign, open, edit and complete a task from a donor; inspect completed/all tasks; assign a record owner; open its source submission |
| 4 | Add donor appointment support | Organization/type-safe links, reminders, permissions, display and cleanup; migration and negative tests |
| 5 | Adopt shared notes/documents/tasks UI and neutral activity contract | Shared behavior tests pass for each supported entity; no regression in surrogate specialized states; bounded activity pagination |
| 6 | Define correspondence, AI and matching scope | Explicit relationship/lifecycle and supported-capability decisions before implementation |

Each step should be independently reviewable. Start by identifying or adding failing regressions for the concrete defects. Backend verification requires a verified isolated database; release work additionally requires migration and deployed integration evidence.

The existing workplan explicitly defers donor matching relationships and donor SMS, and excludes Meta photo uploads. Those are product decisions, not unfinished generic wiring. Dedicated donor correspondence and AI are additional scope choices. See [product decisions](/Users/chason/GenAI-assited-CRM-Tool/docs/donor-module-workplan.md:7).

## Original audit verification

- Frontend suite: 256 files executed; 255 passed and one failed. Tests: 1,427 passed, one failed. The failure is an unrelated instruction-file expectation at [next-16-3-adoption.test.ts:55](/Users/chason/GenAI-assited-CRM-Tool/apps/web/tests/next-16-3-adoption.test.ts:55), which expects nested frontend `AGENTS.md`/`CLAUDE.md` files despite the current root-only policy.
- Focused donor/activity/task run: nine files, 64 tests passed. Files covered donor detail/list/history, shared activity/history, task record presentation/calendar and donor/attachment clients.
- Backend tests were inspected, not executed. The permission and workflow findings remain source-confirmed findings awaiting runtime regression tests.
- No browser QA, provider calls, production inspection, migrations or backend database operations were performed. No application source was changed. Only this audit report was added; no branch, commit, push or deployment was made. No servers were started.
