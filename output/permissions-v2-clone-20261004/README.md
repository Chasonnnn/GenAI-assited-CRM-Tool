# Permission V2 clone rehearsal

Date: 2026-10-04, America/New_York. Latest application commit: `c9b0018a418b01362f71a21a27f20f582473b029`.

## Result

V2 activation remains blocked by business reviews. No clone or production organization was activated. Production was not deployed or changed.

The rehearsal found three defects. Each fix is committed locally. The revised query passed the real clone comparison and 256 affected tests with 19 subtests. The final exact-commit recheck passed at 2026-10-05T00:57:28 UTC.

## Fixed defects

| Commit | Defect | Evidence |
| --- | --- | --- |
| `f9b908de8` | On Hold records with a terminal pause origin could not use their preceding operational history. | 12 failing regression cases became passing. Valid operational origins retain precedence; invalid origins remain denied. |
| `a95db13ea` | A manual phase review could affect another unknown record in the same organization. | Surrogate and donor regressions failed before the fix. Negative checks cover unreviewed, foreign-tenant and stale-stage reviews, plus aliased lists. |
| `c9b0018a4` | Two real records received different phases in list, detail, count and migration queries. | The clone failed with the old query and passed with correlated effective-stage checks. No global planner setting changed. |

The final local validation passed 256 tests and 19 subtests across 15 permission, scope, workflow, campaign and surrogate suites. Ruff, staged diff checks and independent query review passed. The committed function has the same executable AST as the clone-tested candidate. [Validation evidence](phase-fix-validation.json).

## Latest organization preview

The following counts come from the exact-commit recheck. [Verified output](verified-recheck-log.json).

All four organizations remain on V1. The largest organization, `e27e066a-2841-4da5-89ae-98d0735d55b1`, has 8,215 surrogates and eight memberships. Seven memberships are active: one Admin, one Developer, one Case Manager and four Intake Specialists.

| Scope | V1 | Proposed V2 | Lost scope pairs |
| --- | ---: | ---: | ---: |
| Case Manager, surrogates | 2,120 | 46 | 2,074 |
| Intake Specialists, surrogates | 1,500 | 1,497 | 3 |
| Intake Specialists, intended parents | 100 | 0 | 100 |

These are **record-scope-only** member-record pairs. They exclude required module and action permissions. The 100 intended-parent pairs represent four Intake Specialists and 25 records; they do not establish effective access. See the [follow-up correction and permission findings](permission-clarifications.md).

The Case Manager losses comprise 2,072 terminal records with pre-approval operational history and two On Hold records with pre-approval history. V1 uses terminal-stage order; V2 uses the preceding operational phase. The terminal records are 1,465 Disqualified, 510 Lost and 97 Cold Leads. This reduction requires an explicit rollout decision.

The active Case Manager has no creator-owned records in this snapshot. Earlier local regression and browser checks cover the creator route. This clone cannot establish real-record creator coverage.

The three remaining Intake Specialist losses are post-approval records: Heartbeat Confirmed, Legal Clearance Passed and OB Care Established. The query fix restores the two On Hold records to Intake scope.

All 25 intended parents are queue-owned or unassigned. V1 applies no IP ownership filter after the required module permission passes. V2 defaults to assigned-only scope. The earlier claim that every Intake member could access all 25 records was incorrect: the preview excludes module permissions. The recommendation to preserve that presumed access is withdrawn. No permission change was applied.

The largest organization has 46 unresolved surrogate handoffs and one workflow review. No unknown-phase handoffs remain. The initial count of 48 included two records incorrectly selected by the old query.

Organization `ef8599ee-db82-491f-a465-d288b5e07d91` has 901 surrogates, one Admin and one unresolved handoff. Its Admin scope stays unchanged. Two other organizations report ready: one has one surrogate and no members; the other has one Admin and no records. Neither establishes readiness for the populated organizations.

## Reviews required before activation

- Confirm the approved-or-created Case Manager rule despite the reduction in terminal-record access.
- Confirm effective IP permissions separately from record scope. The requested default is no Intake IP access; any match-specific exception needs an explicit access rule.
- Review 46 historical handoffs in the largest organization and one in the other populated organization.
- Select execution authority for one enabled, non-system organization workflow.

Status-change actors are not verified historical owners. Current membership does not prove a historical role. Some workflow and approval owner changes lack ownership activity events. The rehearsal did not infer collaborators from those records or clear reviews automatically.

The final historical scan found 96 recognized ownership events across 45 of 46 handoff records. Three records have current active Intake owners. Sixteen have an Intake assignment target before one explicit recorded approval transition. These targets are candidates, not verified historical owners. Twenty-four lack an explicit approval transition; six lack an active Intake assignment target before it.

The workflow is not a generated routing workflow. It has no pending unreviewed executions. No running campaign runs were found in any organization. Running-campaign migration therefore remains covered by synthetic tests, not a live clone example.

The preview reports no legacy pool grants, legacy individual revokes or missing approval gates in the largest organization. It contains no existing collaborators or manual phase reviews.

## Action permission changes

| Role | Gained action keys | Lost action keys |
| --- | --- | --- |
| Case Manager | `assign_donors`, `create_donors`, `create_intended_parents`, `create_surrogates`, `edit_campaigns`, `manage_automation`, `manage_email_templates`, `review_form_submissions`, `send_email`, `send_sms`, `view_campaigns`, `view_form_submissions` | `manage_ai_settings` |
| Intake Specialist | `approve_donors`, `approve_surrogates`, `create_donors`, `create_surrogates`, `edit_campaigns`, `manage_automation`, `manage_email_templates`, `review_form_submissions`, `send_email`, `send_sms`, `view_campaigns`, `view_form_submissions` | `manage_ai_settings` |

These are permission-key differences. They do not prove every listed action was previously unavailable through legacy role checks. Record scope still limits accessible records. The aggregate preview records all roles and organizations, including administrative and organization-specific differences.

## Query investigation

The clone runs PostgreSQL 18.4. The old query classified two On Hold records as pre-approval when selected by ID. A full-organization scalar query classified neither phase. A handoff query included them despite selecting pre-approval values.

Disabling JIT, Memoize, both together, or forcing custom plans did not resolve the mismatch. Disabling hash joins, merge joins, Memoize and JIT together produced consistent results. No Memoize nodes appeared in the captured baseline scalar plans. These controls do not identify a specific PostgreSQL defect.

The fix removes the outer join on the derived stage ID. Correlated existence checks preserve active-stage, pipeline, tenant and manual-review boundaries. The default-settings clone trial passed all seven agreement checks for both affected records. All policy versions stayed unchanged. [Trial output](query-trial-log.json).

The phase comparison took 2.50 seconds with the candidate and 2.56 seconds with the initial baseline. This single observation is not a performance benchmark. Four-organization preview took 2.92 seconds.

Local synthetic probes did not reproduce the old query failure on PostgreSQL 18.1. The real clone comparison is the failing regression evidence. [Local probe results](local-memoize-reproduction.md).

## Isolation and data preservation

The private Cloud SQL clone completed at 2026-10-04T23:23:37 UTC. The source was `crm-db` in `probable-dream-484923-n7/us-central1`. No database dump or personal record content was downloaded.

The runner used a dedicated service account, independent clone password and task-specific credential secret. Network-tag rules allowed only clone TCP 5432 and denied other IPv4 egress. Socket and libpq guards separately restricted database connections. No API, worker, scheduler or provider client was started. Production provider and encryption keys were not supplied.

Encrypted ORM fields were deferred, and encryption/decryption attempts were rejected. Logs contain aggregate counts, configuration keys, organization UUIDs and validation outcomes. Exception details were suppressed.

The clone contained 9,117 surrogates, 25 intended parents, one donor, 3,278 appointments, 29 matches, 92 tasks and four organizations. Counts and ID/tenant/assignment/stage/archive fingerprints matched across 36 existing business tables. These checks did not compare every clinical or free-text value.

The schema was already `20261004_1300_organization_logo`. The normal release migration command did not advance it. This rehearsal did not exercise an older-schema upgrade.

The setup uses Google's [private clone](https://docs.cloud.google.com/sql/docs/postgres/clone-instance) and [Direct VPC egress](https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc) interfaces. A startup connection timeout occurred before application queries. A retry succeeded; the final harness adds bounded connection retries. No global or production network setting changed.

## Activation guard and artifact identity

The initial activation probe called the real service with a fresh digest. It rejected unresolved reviews before policy writes. The runner rolled back and verified unchanged policy versions across every organization. [Activation guard output](blocked-activation-log.json).

The strict recheck of `a95db13ea` correctly failed on query disagreement before its activation probe. Its completed application steps were read-only. The generic possible-mutation error flag was conservative. [Failed recheck](final-recheck-log.json).

Each build verified all 1,409 tracked API files against its exact source commit. Rehearsal-only overlays added guard and diagnostic code. The final application source is `c9b0018a418b01362f71a21a27f20f582473b029`. [Final source manifest](verified-source-manifest.json). The normal final recheck uses production application functions without a candidate override.

Build `38f690a8-413d-4f3a-881e-15fc3c7ff3e0` produced image `sha256:20ffadbfbae5d77d112d492f1d2e981d0958c53f20811ff1d71c198b2fc34fef`. Execution `crm-perm-rehearsal-1004-nhg5l` passed preview, diagnosis, phase parity and the real activation-blocking probe. No resolutions were applied. Policy versions and protected-table fingerprints remained unchanged. [Verified recheck](verified-recheck-log.json).

Builds, immutable image digests, executions and source uploads are recorded in [resources.json](resources.json). No branch, push, pull request or deployment was created.

## Cleanup

Cleanup completed and absence checks passed at 2026-10-05T01:04:31 UTC. The clone, backup, runner, secret, service account, two firewall rules, eight images and eight source uploads were removed. No project IAM role bindings were added; the secret-only accessor binding was removed with its secret. Normal Cloud Build and Cloud Logging audit records remain. [Cleanup evidence](cleanup-verification.json).

Private credential staging, task cache, temporary test logs and Python caches were removed. The saved artifacts passed an exact secret-value scan. Production SQL remains RUNNABLE at settings version 367. API revision `crm-api-00262-spp` retains 100% traffic. Temporary test databases and wrappers were removed. The pre-existing local PostgreSQL container remains unchanged. No task-owned local service is running.
