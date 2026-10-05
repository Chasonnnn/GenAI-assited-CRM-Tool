# Historical handoff review — 2026-10-04

The isolated evidence collection succeeded. No historical access decision was applied, and permission V2 was not activated.

## EWI findings

| Finding | Records |
| --- | ---: |
| Historical handoffs requiring review under the fixed application code | 46 |
| Current active Intake owner to preserve | 3 |
| Recorded assignment identifies a possible former Intake owner | 16 |
| No former Intake owner identified by the selected events | 30 |
| Historically verified owners from existing valid human reviews | 0 |

Current ownership and historical assignment are separate facts. One current-owner record also has a different possible former owner. Preserving current access and restoring former access can require two collaborators on that record. The three current-owner records must not be added to the sixteen assignment observations as separate cases.

The collector found 96 ownership activity events, 60 ownership audit observations, 215 stage-history events, and three role-audit observations. No selected workflow event supplied another ownership observation. None of the sixteen possible former owners had a historical role observation at approval.

Missing events do not establish that a record had no former Intake owner. Workflow assignments can lack ownership activity, and membership history can omit reactivation. These gaps prevent automatic historical verification.

Forty-four approval transitions have different effective and recorded timestamps. Every difference is less than one second. These differences do not establish backdating or corrupted history. The conservative classifier marks 44 records ambiguous and two candidates; both classifications still require human review. The review page labels a recorded assignment as unverified regardless of this distinction.

The deployed preview previously showed 48 records. It runs older phase logic. This review uses the locally fixed source and identifies 46. Decisions must be checked against a fresh preview after the fixes are deployed.

## Private deliverables

- `.exports/permissions-v2-handoff-review-20261004/review.html`: 46 record links, current-owner metadata, assignment observations, evidence timelines, and unselected review controls.
- `.exports/permissions-v2-handoff-review-20261004/evidence.json`: EWI-only metadata evidence with record and evidence fingerprints.

The directory is mode `0700`; both files are mode `0600` and excluded from Git. Neither file contains names, contact details, notes, message bodies, credentials, or full source JSON payloads. Member aliases include IDs for comparison with CRM records.

The page exports an unapplied decision draft. Retention requires an active Intake member and evidence reference. A no-owner decision also requires evidence. No option starts selected, and no API write exists. An EWI administrator must confirm the sixteen assignment observations and resolve the thirty records without an identified former owner.

## Execution and validation

- Application source: `91da87428dc6d90ac051f96a25ae2decf0f6de43`.
- Successful execution: `crm-handoff-review-1004-rn9h5`, completed `2026-10-05T02:46:28.639533Z`.
- One consistent PostgreSQL read-only snapshot; no application migration, workflow, campaign, grant, or activation operation.
- Four organizations checked; EWI has 46 candidates and another organization has one. Only EWI's private ledger is retained locally.
- Only clone guard tables were initialized outside the read-only business-data transaction.
- Eight synthetic classification tests passed. Two disposable PostgreSQL checks passed, including populated history, malformed UUIDs, privacy, and tenant negatives.
- Source, clone identity, database user, network, encryption, and aggregate-output guards passed. Repository Ruff and diff checks passed.
- Synthetic rendered-DOM checks passed for unreviewed defaults, retention validation, evidence validation, and unapplied JSON export.
- Browser policy rejected local file URLs. No browser visual check of this HTML file was completed or bypassed. The production permission-review page had no captured console warnings or errors.

The first two executions stopped before business collection. The clone's `postgres` login lacked application-table privileges (`42501` on `alembic_version`). The successful execution used the clone's existing `crm_user` login with a temporary clone-only password. Production credentials were not accessed or changed.

Production API revision `crm-api-00262-spp` retained 100% traffic. Application code was not changed during this evidence phase. Nothing was pushed or deployed.

Cleanup evidence is recorded in `resources.json`. Normal provider build history and audit logs remain. The cloud ledger was encrypted, and temporary decryption keys are removed after local evidence preservation.

## Remaining migration gates

- Confirm historical owner decisions with EWI and preserve current Intake access.
- Complete the agreed access rules, pool behavior, and workflow review.
- Push and deploy the validated fixes through the normal release process.
- Generate a fresh organization preview and validate decision fingerprints.
- Obtain explicit activation authorization. Activation remains disabled.
