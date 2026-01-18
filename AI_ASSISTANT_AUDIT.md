# AI Assistant Audit Report

## 1) High-Level Map

### Backend (apps/api)
- AI entrypoints and orchestration: `apps/api/app/routers/ai.py`
- AI settings and BYOK key handling: `apps/api/app/services/ai_settings_service.py`, `apps/api/app/services/ai_provider.py`
- Chat pipeline and storage: `apps/api/app/services/ai_chat_service.py`, `apps/api/app/db/models.py`
- Action approvals and execution: `apps/api/app/services/ai_action_executor.py`
- One-shot AI features: `apps/api/app/services/ai_interview_service.py`, `apps/api/app/services/schedule_parser.py`, `apps/api/app/services/ai_workflow_service.py`
- Background jobs for async chat: `apps/api/app/worker.py`, `apps/api/app/services/job_service.py`
- Usage analytics: `apps/api/app/services/ai_usage_service.py`
- Data models: `apps/api/app/db/models.py` (AISettings, AIConversation, AIMessage, AIActionApproval, AIBulkTaskRequest, AIEntitySummary, AIUsageLog)

### Frontend (apps/web)
- AI assistant UI: `apps/web/components/ai/AIChatPanel.tsx`, `apps/web/components/ai/AIFloatingButton.tsx`
- Schedule parsing UI: `apps/web/components/ai/ScheduleParserDialog.tsx`
- AI settings UI (BYOK): `apps/web/app/(app)/settings/integrations/page.tsx`
- AI assistant page: `apps/web/app/(app)/ai-assistant/page.tsx`
- API client and hooks: `apps/web/lib/api/ai.ts`, `apps/web/lib/hooks/use-ai.ts`, `apps/web/lib/hooks/use-schedule-parser.ts`
- AI context gating: `apps/web/lib/context/ai-context.tsx`

### End-to-End Flows
1) BYOK settings update
   - UI -> `PATCH /ai/settings` -> `ai_settings_service.update_ai_settings` -> store `AISettings.api_key_encrypted` -> return masked key.
2) Consent
   - UI -> `POST /ai/consent/accept` -> `ai_settings_service.accept_consent` -> audit log.
3) Chat (async)
   - UI -> `POST /ai/chat/async` -> `JobType.AI_CHAT` -> `worker.process_ai_chat` -> `ai_chat_service.chat_async`
   - `ai_provider` call -> persist `AIConversation`, `AIMessage`, `AIActionApproval`, `AIUsageLog` -> job result -> UI polls `GET /ai/chat/jobs/{job_id}`.
4) Action approvals
   - UI -> `POST /ai/actions/{approval_id}/approve` -> `ai_action_executor.execute_action` -> create task/note/update status/send email -> audit log.
5) Surrogate summary
   - UI -> `POST /ai/summarize-surrogate` -> prompt build in `ai.py` -> `ai_provider` -> response to UI.
6) Interview summaries
   - UI -> `POST /interviews/{id}/ai/summarize` or `/surrogates/{id}/interviews/ai/summarize-all`
   - `ai_interview_service` -> `ai_provider` -> response to UI.
7) Schedule parsing
   - UI -> `POST /ai/parse-schedule` -> `schedule_parser.parse_schedule_text` -> proposed tasks -> user review
   - UI -> `POST /ai/create-bulk-tasks` -> DB tasks + activity log.
8) Email drafting
   - UI -> `POST /ai/draft-email` -> `ai_provider` -> draft returned; separate user action required to send.
9) Dashboard insights
   - UI -> `POST /ai/analyze-dashboard` -> stats gathered -> `ai_provider` -> recommendations.
10) Workflow generation
    - UI -> `POST /ai/workflows/generate` -> `ai_workflow_service.generate_workflow` -> user review -> `POST /ai/workflows/save`.

## 2) Findings (Ranked by Severity)

### Critical 1 - Anonymize PII setting is ignored in non-chat AI endpoints (Security / Privacy)
- Impact: Surrogate PII and interview content is sent to external LLMs even when anonymize_pii is enabled (default), contradicting consent text and increasing data exposure risk.
- Where: `apps/api/app/routers/ai.py:1210`, `apps/api/app/routers/ai.py:1350`, `apps/api/app/services/ai_interview_service.py:139`, `apps/api/app/services/schedule_parser.py:182`
- How to reproduce: (1) Enable AI with anonymize_pii=true. (2) Call `/ai/summarize-surrogate`, `/ai/draft-email`, `/interviews/{id}/ai/summarize`, or `/ai/parse-schedule` with PII in the input. (3) Observe outbound prompt includes raw names/emails/transcripts.
- Recommended fix: Centralize prompt construction with `pii_anonymizer` for all AI calls; strip PII before provider calls and rehydrate responses. For draft email, send placeholders to the model and inject recipient name/email after response.
- Tests to add: Unit tests for each endpoint asserting provider inputs exclude PII when anonymize_pii is true; integration test that response is rehydrated correctly.

### Critical 2 - Missing surrogate access checks for summarize and draft endpoints (Multi-tenancy / RBAC)
- Impact: Any user with `use_ai_assistant` can summarize or draft email for any surrogate in the org, bypassing owner-based access controls.
- Where: `apps/api/app/routers/ai.py:1181`, `apps/api/app/routers/ai.py:1334`
- How to reproduce: (1) Log in as a user without access to a surrogate. (2) Call `/ai/summarize-surrogate` or `/ai/draft-email` with that surrogate_id. (3) Response includes surrogate data.
- Recommended fix: Enforce `check_surrogate_access` in both endpoints (same as `/ai/chat`) before assembling context or returning drafts.
- Tests to add: RBAC tests that a user without access receives 403 for `/ai/summarize-surrogate` and `/ai/draft-email`.

### Critical 3 - Consent not enforced for dashboard analysis (Safety / Policy)
- Impact: Dashboard insights can call LLMs without explicit consent, violating consent requirements and the AI consent UX.
- Where: `apps/api/app/routers/ai.py:1432`
- How to reproduce: (1) Enable AI settings but do not accept consent. (2) Call `/ai/analyze-dashboard`. (3) Request proceeds without consent check.
- Recommended fix: Add `ai_settings_service.is_consent_required` guard similar to `/ai/chat` and `/ai/draft-email`.
- Tests to add: Integration test asserting `/ai/analyze-dashboard` returns 403 when consent is required.

### High 4 - Org-level ai_enabled flag is not enforced server-side (Safety / Policy)
- Impact: AI can be used via direct API calls even when the organization feature flag is disabled, defeating plan or policy controls.
- Where: `apps/api/app/db/models.py:71`, `apps/web/lib/context/ai-context.tsx:50`, `apps/api/app/routers/ai.py:1168`
- How to reproduce: (1) Set org.ai_enabled=false. (2) Call AI endpoints directly. (3) Requests succeed if AISettings is enabled and permissions are granted.
- Recommended fix: Enforce org.ai_enabled in AI routes or in a shared dependency (e.g., a new `require_ai_enabled` in deps).
- Tests to add: API tests asserting AI endpoints return 403 when org.ai_enabled is false, even if permissions are present.

### High 5 - Async chat jobs persist raw prompts in job payload (Security / Privacy)
- Impact: Raw AI prompts (often PII) are stored in jobs payloads and may persist on failures, expanding the sensitive data footprint.
- Where: `apps/api/app/routers/ai.py:498`, `apps/api/app/worker.py:974`
- How to reproduce: (1) Submit `/ai/chat/async` with PII in the message. (2) Inspect jobs table payload. (3) Observe raw message stored; on job failure it remains.
- Recommended fix: Store only a message reference in job payload, or encrypt/redact message before persistence; ensure message is removed on both success and failure paths.
- Tests to add: Job processing test asserting payload does not retain raw message after completion or failure.

### Medium 6 - Sync AI endpoints use get_event_loop().run_until_complete (Reliability / Performance)
- Impact: Sync endpoints can throw `RuntimeError: There is no current event loop` in threadpool contexts, causing intermittent 500s.
- Where: `apps/api/app/routers/ai.py:1244`, `apps/api/app/routers/ai.py:1374`, `apps/api/app/routers/ai.py:1513`
- How to reproduce: Run FastAPI with default threadpool for sync handlers and hit `/ai/summarize-surrogate` or `/ai/draft-email` under load; observe event loop errors.
- Recommended fix: Convert these endpoints to async and `await provider.chat`, or use `asyncio.run` safely as in `ai_chat_service.chat`.
- Tests to add: Integration test invoking these endpoints in a sync context to confirm no event loop errors.

### Medium 7 - Duplicate surrogate_id fields in schedule parsing and bulk task schemas (Correctness)
- Impact: Validation logic is confusing and error-prone; duplicated fields and checks can mask invalid payloads and complicate client usage.
- Where: `apps/api/app/routers/ai.py:1748`, `apps/api/app/routers/ai.py:1885`
- How to reproduce: Inspect schema definitions; both requests declare surrogate_id twice and validator references the same field twice.
- Recommended fix: Remove duplicate fields or define a proper alias (e.g., `case_id` -> `surrogate_id`) and update validators accordingly.
- Tests to add: Schema validation tests covering required ID combinations and alias behavior.

### Medium 8 - Retention policies omit AI data tables (Security / Privacy)
- Impact: AI conversations, messages, approvals, and usage logs are retained indefinitely, which conflicts with data minimization and retention expectations.
- Where: `apps/api/app/services/compliance_service.py:571`
- How to reproduce: Review default retention policies; AI tables are not included and purge job does not target them.
- Recommended fix: Add AI tables to retention policies and purge logic (with legal-hold awareness).
- Tests to add: Purge tests verifying AIConversation/AIMessage/AIUsageLog rows are removed after retention window.

### Medium 9 - Workflow generation prompt includes staff identifiers without anonymization (Security / Privacy)
- Impact: User names/emails are sent to the LLM; if anonymize_pii is intended to protect all personal identifiers, this violates that expectation.
- Where: `apps/api/app/services/ai_workflow_service.py:262`
- How to reproduce: Generate workflow; prompt includes `display_name` or `email` for users.
- Recommended fix: Send only user IDs and roles to the model, or anonymize staff identifiers before provider calls.
- Tests to add: Prompt construction tests that exclude raw emails when anonymize_pii is true.

### Low 10 - AIEntitySummary model is unused (DX / Maintainability / Cost)
- Impact: Context caching is defined but not implemented; repeated context building increases token usage and DB load.
- Where: `apps/api/app/db/models.py:2626`
- How to reproduce: Search for AIEntitySummary usage; only model definition exists.
- Recommended fix: Either implement summary cache maintenance or remove the model to reduce dead code.
- Tests to add: If implemented, add tests ensuring summaries update on note/task/status changes.

## Fix Order (Top 10)
1) Critical 1 - Anonymize PII setting ignored in non-chat endpoints
2) Critical 2 - Missing surrogate access checks for summarize/draft
3) Critical 3 - Consent not enforced for dashboard analysis
4) High 4 - Org-level ai_enabled not enforced server-side
5) High 5 - Async chat jobs store raw prompts
6) Medium 6 - Event loop misuse in sync endpoints
7) Medium 7 - Duplicate surrogate_id fields
8) Medium 8 - Retention policies omit AI tables
9) Medium 9 - Workflow generation exposes staff identifiers
10) Low 10 - AIEntitySummary unused

## 3) Threat Model

### Data Flow (Textual)
Browser UI -> Next.js API client -> FastAPI router -> AI service -> External LLM provider -> AI responses persisted (AIConversation/AIMessage/AIUsageLog) -> UI rendering and action approvals.

### Trust Boundaries
- Browser <-> API: authenticated cookies + CSRF header required for mutations.
- API <-> DB: org-scoped queries, RBAC checks, encrypted secrets at rest.
- API <-> LLM provider: BYOK key, outbound prompts may include PII.
- Worker <-> LLM provider: async chat jobs running outside request context.

### Top Risks and Mitigations
- Prompt injection via notes or user-supplied text: enforce strict system prompts, delimit untrusted content, validate action schemas, and gate execution by explicit approval.
- Cross-org data bleed: require org_id scoping in every AI query and enforce access checks before building context.
- API key exposure: keep keys write-only and encrypted; never echo raw keys in API responses.
- PII leakage in prompts/logs: anonymize PII before provider calls; log metadata only.
- Cost overruns and rate limits: apply per-org quotas, timeouts, and circuit breakers; log token usage and alert on spikes.

## 4) Coverage and Gaps

### Existing Coverage (not exhaustive)
- Backend contract tests: `apps/api/tests/test_ai_contract.py`
- Bulk task creation and idempotency: `apps/api/tests/test_ai_bulk_tasks.py`
- Workflow validation and AI workflow tests: `apps/api/tests/test_ai_workflow.py`, `apps/api/tests/test_workflows.py`
- Interview summary endpoint coverage: `apps/api/tests/test_interviews.py`
- Frontend AI assistant UI contract: `apps/web/tests/api-ai-contracts.test.ts`, `apps/web/tests/ai-assistant.test.tsx`

### Top Missing Tests (prioritized)
1) Anonymize PII across non-chat AI endpoints (summary, draft email, interview summary, schedule parsing).
2) Consent enforcement on `/ai/analyze-dashboard`.
3) Surrogate access control on `/ai/summarize-surrogate` and `/ai/draft-email`.
4) org.ai_enabled enforcement for AI endpoints.
5) Async chat job payload redaction on success and failure.
6) Retention/purge for AIConversation, AIMessage, AIUsageLog, AIActionApproval.

## 5) Ticket Backlog (Templates)

### T1 - Apply PII anonymization to non-chat AI endpoints (Critical)
- Scope: `apps/api/app/routers/ai.py`, `apps/api/app/services/ai_interview_service.py`, `apps/api/app/services/schedule_parser.py`, `apps/api/app/services/pii_anonymizer.py`
- Summary: Respect `AISettings.anonymize_pii` across summary, draft, interview, and schedule parsing flows by anonymizing prompts and rehydrating responses.
- Implementation notes:
  - Build a shared helper for anonymized prompt generation and response rehydration.
  - Use `PIIMapping` + `anonymize_text` for free text; add known names when available.
  - For draft email: do not pass recipient email/name to provider; inject those after parsing the JSON response.
- Acceptance criteria:
  - Provider input contains no surrogate names/emails/phones when anonymize_pii is true.
  - Responses are rehydrated correctly for display and action payloads.
  - Consent text behavior matches actual data handling.
- Tests:
  - Unit tests asserting provider messages exclude PII for `/ai/summarize-surrogate`, `/ai/draft-email`, `/interviews/*/ai/summarize`, `/ai/parse-schedule`.
  - Integration test confirming rehydrated response for draft email includes correct recipient name in returned body, without being sent to provider.

### T2 - Enforce surrogate access checks on summarize and draft endpoints (Critical)
- Scope: `apps/api/app/routers/ai.py`
- Summary: Apply `check_surrogate_access` to `/ai/summarize-surrogate` and `/ai/draft-email`.
- Acceptance criteria:
  - Users lacking surrogate access receive 403.
  - Authorized users retain current behavior.
- Tests:
  - RBAC tests for both endpoints using a surrogate owned by another user.

### T3 - Enforce AI consent on dashboard analysis (Critical)
- Scope: `apps/api/app/routers/ai.py`
- Summary: Block `/ai/analyze-dashboard` when consent is required.
- Acceptance criteria:
  - Requests return 403 when consent not accepted.
  - Requests succeed when consent is accepted or AI is disabled (existing behavior preserved).
- Tests:
  - Integration test for consent gating on `/ai/analyze-dashboard`.

### T4 - Enforce org.ai_enabled server-side (High)
- Scope: `apps/api/app/routers/ai.py`, `apps/api/app/core/deps.py`, `apps/api/app/services/org_service.py`
- Summary: Prevent AI usage when org feature flag is disabled regardless of AISettings state.
- Implementation notes:
  - Add a shared dependency (e.g., `require_ai_enabled`) used by AI endpoints.
- Acceptance criteria:
  - AI endpoints return 403 when org.ai_enabled=false.
  - Frontend behavior remains unchanged (still gated by `user.ai_enabled`).
- Tests:
  - API tests for `/ai/chat`, `/ai/summarize-surrogate`, `/ai/draft-email`, `/ai/analyze-dashboard` with org.ai_enabled=false.

### T5 - Remove raw prompt storage from async chat jobs (High)
- Scope: `apps/api/app/routers/ai.py`, `apps/api/app/worker.py`, `apps/api/app/services/ai_chat_service.py`
- Summary: Avoid persisting raw user messages in job payloads; store a reference or encrypted value instead.
- Implementation notes:
  - Option A: Create a new AIMessage row before enqueue and pass message_id to the job.
  - Option B: Encrypt message in payload and decrypt in worker; scrub on completion/failure.
- Acceptance criteria:
  - Job payload contains no raw message after completion or failure.
  - Async chat still works and yields identical responses.
- Tests:
  - Job processing test verifying payload scrubbing.
  - Regression test for `/ai/chat/async` success path.

### T6 - Fix event loop usage in sync AI endpoints (Medium)
- Scope: `apps/api/app/routers/ai.py`
- Summary: Convert sync handlers to async or use safe async execution for provider calls.
- Acceptance criteria:
  - No `RuntimeError` from event loop access under load.
  - Responses and error handling unchanged.
- Tests:
  - Integration test that exercises `/ai/summarize-surrogate`, `/ai/draft-email`, `/ai/analyze-dashboard` without event loop errors.

### T7 - Remove duplicate surrogate_id fields in AI request schemas (Medium)
- Scope: `apps/api/app/routers/ai.py`, `apps/web/lib/api/schedule-parser.ts` (if aliasing changes)
- Summary: Fix duplicate `surrogate_id` fields and validators in `ParseScheduleRequest` and `BulkTaskCreateRequest`.
- Acceptance criteria:
  - Schemas define each field once and validate correctly.
  - Frontend payloads continue to be accepted (or are updated accordingly).
- Tests:
  - Pydantic validation tests for each request schema.
  - Frontend contract test for schedule parsing request shape.

### T8 - Add retention coverage for AI tables (Medium)
- Scope: `apps/api/app/services/compliance_service.py`, data purge logic, retention policies
- Summary: Include AIConversation, AIMessage, AIActionApproval, AIUsageLog in retention defaults and purge jobs.
- Acceptance criteria:
  - AI tables are included in retention policy list and are purged when policy applies.
  - Legal holds prevent purge as expected.
- Tests:
  - Purge tests covering AI tables.

### T9 - Anonymize staff identifiers in AI workflow generation prompts (Medium)
- Scope: `apps/api/app/services/ai_workflow_service.py`
- Summary: Prevent staff emails/names from being sent to the LLM when anonymize_pii is true.
- Acceptance criteria:
  - Prompt includes only user IDs or anonymized labels when anonymize_pii is enabled.
  - Generated workflows still map to valid user IDs.
- Tests:
  - Prompt construction test verifying absence of raw emails.

### T10 - Decide on AIEntitySummary usage or removal (Low)
- Scope: `apps/api/app/db/models.py`, related services
- Summary: Either implement summary caching or remove the unused model to reduce dead code.
- Acceptance criteria:
  - If implemented: summary is updated when notes/tasks/status change and used by chat context.
  - If removed: no references remain and migrations are updated accordingly.
- Tests:
  - If implemented: unit tests verifying summary updates and read path uses cache.

## 6) Pre-Ship Checklist
- [ ] Consent checks cover every AI endpoint that can call a provider.
- [ ] PII anonymization is applied consistently or explicitly documented as disabled for specific flows.
- [ ] Surrogate access checks are enforced for all surrogate-scoped AI endpoints.
- [ ] org.ai_enabled is enforced server-side.
- [ ] Async job payloads do not store raw prompts.
- [ ] Retention policies include AI tables and purge jobs are verified.
- [ ] Rate limits and timeouts are validated in staging with load.
- [ ] Add/adjust tests for the fixes above.
