# Repository lifecycle audit — October 4, 2026

Base: `dbbc70a35`, clean detached worktree before this audit. Scope: backend entrypoints, services, jobs, migrations, frontend imports/routes, tests, infrastructure, release configuration, and read-only production configuration. This snapshot preceded production authorization. The subsequent release and activation are recorded in `delivery.md`.

## Findings

| System | Observed state | Action |
| --- | --- | --- |
| Workflow maintenance | Production worker explicitly sets `WORKFLOW_MAINTENANCE_FALLBACK_ENABLED=false`. This covers inactivity, task-due, task-overdue, and appointment-time sweeps. The Cloud Scheduler inventory contains only billing and antivirus jobs. | Highest-priority activation review: count eligible workflows and affected records per organization, review resulting actions, then approve a bounded canary. Existing enabled-path tests passed. Do not assume activation starts with an empty backlog. |
| Workflow approval expiry | Production worker explicitly sets `WORKFLOW_APPROVAL_EXPIRY_FALLBACK_ENABLED=false`. | Review overdue approval counts and resulting execution changes before enabling. Enabled-path and disabled-path tests passed. |
| Scheduling V2 | Flag absent on API/worker; release `0.91.79` defaults it off. Implementation and schema are present. | Retain and activate after organization inventory, explicit writable calendar bindings, fresh busy projections, and real-account QA. Keep API/worker flags aligned. Historical ambiguous links must not be adopted automatically. |
| Match expansion | Flag absent on API/worker; release defaults it off. Ordinary surrogate matching remains available; donor and repeat-case expansion is gated; the former new-attempt flow has been removed. | Retain. Verify compatible API/worker revisions, migration/cutover evidence and tenant workflows, then approve worker-first activation. The existing rollout procedure intentionally does not auto-enable it. |
| Permission policy V2 | Per-organization data gate: missing policy/version 1 keeps legacy behavior. Environment inspection cannot establish tenant activation. | Use the existing preview/activate flow. Review role changes, individual revokes, record scopes and queued execution authority. Keep V1 until all organizations are reviewed and migrated. |
| Private tracing | `OTEL_ENABLED` and exporter endpoint absent; tracing remains off. | Retain. Select/configure the collector and credential binding, then verify sanitized ingestion. Local privacy/lifecycle tests passed; enabling the flag alone produces no collector. |
| Gmail push synchronization | `GMAIL_PUSH_TOPIC` and webhook token absent. The polling implementation remains connected. | Optional activation: configure Pub/Sub delivery and authentication, refresh watches, then test real mailbox events. Retain polling for recovery. |
| Meta CAPI | Global flag absent; release defaults it off. Per-ad-account enablement, pixel and token checks also exist. | Review account readiness and intended outbound conversion events before activation. No provider setup or transmission was performed. |
| Twilio messaging | `MESSAGING_DELIVERY_DISPATCH_ENABLED=true` on both production API and worker. | Already globally enabled. Organization/route readiness still controls delivery; do not classify this as never activated. |
| Shared intake, matching, token lock | Flags absent; release defaults all three on. | Already enabled by default. Absence of an environment override does not mean a feature is disabled. |
| Next rendering/compiler experiments | Three build switches remain off. The adoption document records prerender/build/compiler blockers from earlier verification. | Keep off. Those historical failures were not re-tested here; a runtime flag change cannot replace the required web build and authenticated navigation QA. |
| Legacy worker scaling schedule | Source remains opt-in and default-off; no scale-up/down jobs appeared in the regional production scheduler inventory. Worker minimum is one instance. | Infrastructure retirement candidate. Confirm Terraform state and a reviewed plan before removing declarations that could destroy managed resources. |

Production returned version `0.91.79`, API revision `crm-api-00258-j4d`, worker revision `crm-worker-00303-m26`, and web revision `crm-web-00235-zvw`, each at 100% traffic. Both health requests returned 200. Database head was `20261003_1800_timezone_aware_form_timestamps`.

The [sanitized configuration snapshot](production-snapshot.json) records explicit flags separately from release-tag defaults. It does not prove historical non-use, per-organization readiness, or a deployed source-digest match.

## Implemented but not in the observed release

The checkout differs from tag `surrogacy-crm-platform-v0.91.79` in 258 files before this cleanup. The new email block editor/forms workbench, pipeline redesign, organization logo, and later UI fixes are release work, not missing feature switches.

The local schema is three revisions beyond production:

1. `20261004_1000_drop_flat_medical_columns`
2. `20261004_1200_email_template_body_design`
3. `20261004_1300_organization_logo`

The first migration drops old columns. A release containing this cleanup also carries that existing migration chain; local cleanup tests do not authorize running it in production. The email editor migration preserves existing HTML and adds nullable design documents. Do not deploy the frontend replacement without its compatible API/schema.

## Removed locally

| Removal | Evidence | Preserved behavior |
| --- | --- | --- |
| Old email visual editor and exclusive helpers | Final production caller replaced in `baa2f26e7`; remaining callers were tests. | Current block editor, original HTML preservation, preview sanitization, variable extraction and HTML normalization. |
| Donor header photo component, upload adapter and exclusive hooks | Deliberately removed from the page in `611eee06f`; no production consumers remained. | Backend photo route/storage, intake photo previews, donor attachments and four rendered header-absence cases. |
| `core/stage_rules.py` | Neither exported constant has a caller. | Current configurable stage definitions, role visibility, record scopes and mutation policies. |
| Transcript offloading service and dead threshold | Introduced in `f41782a44`, never connected to the current interview flow; only six exclusive tests called it. | Inline TipTap transcripts, versions, exports, persisted storage-key columns and migration history. |
| `email_service.list_templates` | No callers; router has used `list_templates_for_user` since `ab221c599`. | Personal/organization visibility and current template filtering. |
| `.build-test` and root ZAP report | January build marker and generated January 24 report. CI creates and uploads `zap-report.html`; it does not consume this report. | Active ZAP configuration and CI job. Added ignore entries for the retired artifacts. |

Removed 962 net production lines and 414 net test/support lines, including 25 cases belonging to deleted implementations. Two root artifacts removed another 1,187 lines. Updated the code map's removed paths and the Next adoption document's stale version/test-typecheck status.

Detailed caller/history/test evidence: [backend](backend-removals.json), [frontend](frontend-removals.md). Independent backend and frontend reviews found no blocking findings.

## Retained compatibility and recovery paths

- `legacy_job_reconciliation_service.py` has a live CLI command and protects uncertain email/job replay. Retirement requires evidence that tokenless running jobs are drained or reconciled.
- Form-routing maintenance and retired-action handling serve operator repair, stored workflow versions and backups. Removing the old workflow actions from the editor does not make these readers obsolete.
- Import mapping fallback is still reached for stored imports without a mapping snapshot.
- Legacy unsubscribe parsing, email delivery adapters and calendar ownership guards still handle persisted records or pending jobs.
- Alembic archives/helpers, worker/scan/migration process entrypoints, and the development-only donor intake prototype have real non-application-import consumers.
- Match-event client hooks have no current UI consumers, but the backend event API remains live. Retirement needs a feature-owner decision rather than assuming the event workflow is unwanted.
- The test-facing WebSocket origin helper and AI provider `TypeError` compatibility fallback are further cleanup candidates. Their auth/provider behavior needs a separate focused change and negative tests; they were not modified here.

## Local validation

| Check | Result |
| --- | --- |
| Affected backend owners | 62 passed |
| Dormant-feature suites, including enabled paths | 253 passed |
| Scheduling/match migration invariants | 18 passed |
| Focused frontend rendered/adapter suites | 232 passed in 14 files |
| Full frontend `check` | Application types, test types, lint and 3,037 tests in 385 files passed |
| Ruff lint and format | Passed on changed Python surfaces |
| React Doctor 0.9.14 | No diagnostics across 10 changed files; remote scoring and supply-chain scan disabled |
| Diff whitespace and independent reviews | Passed |

[Commands, file lists and results](validation.json). Backend checks used three unique local databases created, migrated and dropped by `apps/api/run_tests.sh`; their removal was verified. Existing `crm_db` was left running. No application server or worker was started.

The initial local audit phase did not run a full backend suite, production image build, browser session, real-provider canary, tenant inventory or production database query. At that checkpoint, no flags, production data, provider settings or live services had changed, and no push, PR, release or deployment had been performed. See `delivery.md` for the subsequent authorized production work.
