# Permission upgrade execution plan

Status: permission version 2 foundations, the selected Team/member navigation, workflow and campaign service splits, atomic form retries, and shared dashboard attention datasets are implemented for draft PR #691. Release acceptance and organization activation remain separate gates. Production organizations remain on version 1 until reviewed activation. The selected role editor is the September 12 module-first mockup, option 1; a selected mockup is not implementation evidence.

## Implemented foundations

| Package | Result | Boundary |
|---|---|---|
| Permission core | Protected Admin/Dev, editable supplied roles, individual additions, explicit role-change review, current membership checks | Actions remain separate from record scope |
| Record scope | Assignment, phase/stage rules, individual scope additions, retained Intake collaboration, access explanations | One SQL scope feeds lists, counts, details, linked work, and reports |
| Approval | Surrogate, egg-donor, and sperm-donor approval gates; retained Intake owner and claim pool | Approval, stage changes, assignment, and ordinary editing remain distinct actions |
| Organization authority | Durable workflow/campaign authority, personal audience rechecks, safe publication copies and proposer credit | Organization work survives proposer departure; personal work uses its owner's current authority |
| Administration UI | Production Roles editor, existing team/member pages, visibility-only Check access, migration review, individual additions, role carryover review | Not a completed reproduction of every mockup; server capabilities govern controls and inherited access has no individual deny |
| Consumer integration | Records, notes/interviews/profile, search, tasks, matches, attachments, appointments, status corrections, reporting, submission review, AI-approved actions | Related record access follows the same tenant and scope constraints |

Detailed checks and local delivery status are in [permission-upgrade-verification.md](permission-upgrade-verification.md).

## Active workplan — September 22

Keep this work in draft PR #691, stacked on draft platform PR #690. Keep changes in small logical commits and push verified increments to these drafts. This authorizes neither merge/deployment nor production migrations, provider sends, or organization activation.

The September 22 refresh incorporates current main in the isolated permission completion worktree. The additive `20260922_1600_permission_heads` revision joins the permission and Google appointment migration histories. Verification for this completion is recorded separately from earlier snapshots.

| Order | Work | Completion evidence / boundary |
|---|---|---|
| 1 | Recover safety fixes and refresh the permission branch | Required approval-task failures stop execution; form retry failures roll back the full retry. Current main is merged into the permission worktree with an additive migration join |
| 2 | Review and finish permission frontend | Selected existing Team list plus separate member pages; shared navigation, search/filtering, and Admin/Dev-managed record collaborators in Actions and member settings |
| 3 | Refactor workflow action execution | Intake, record, task, and communication actions have separate modules. Shared dispatch, approval, retry/resume, and delivery admission remain centralized |
| 4 | Refactor campaign lifecycle | Audience, content, run lifecycle, execution, delivery, and suppression have named owners; definition CRUD stays in the existing service |
| 5 | Consolidate intake matching/retry transactions | One service-owned retry transaction covers reset, matching, lead creation, and audit; failure and scope regressions pass |
| 6 | Consolidate reporting datasets | Dashboard attention rows/counts share authorized queries; donor drill-down parity is covered. Cross-request v2 caching remains a separate optimization |
| 7 | Validate the exact combined version | Full API/frontend suites and production build pass. Current browser and activation evidence is recorded in the verification document |
| 8 | Release and real-organization activation | Separately authorized after acceptance and final CI. Review actual organization access/execution changes before activation |

The selected frontend direction preserves the existing Team and member-page structure. Do not add new UI, change permission defaults, or claim that mockup selection approves every implemented control. Refactoring and behavior changes must be separate commits with their own tests. Meta/Twilio configuration, onboarding, and broader redesign are outside this workplan.

The CI PR-base filter now includes `codex/platform-upgrades`, with a regression test. Push and release triggers are unchanged. Inspect actual remote check results after publication; local validation or an absent check is not a passing GitHub run. The final accepted combined version must receive CI before merge without triggering deployment workflows.

## Agreed defaults

- Personal workflows, templates, and campaign authoring are included for every active member. AI is included when enabled by the organization; provider settings remain Admin/Dev only.
- Create is independent of Edit for all three record modules.
- Intake: assigned records before approval, retained collaboration after handoff, configurable applicant approval.
- Case Manager: all records from Approved onward; actions remain configurable.
- Operations: organization workflow/campaign/template management and record/report viewing; no record writes or sending by default.
- Admin/Dev: protected administration authority within organization boundaries.
- Reports and exports: the viewer's record scope; organization advertising spend requires unrestricted donor and surrogate scope.
- Form submissions: linked submissions follow record access; unlinked intake belongs to Intake/Admin/Dev. Review is separate from form-building authority.

## Migration and activation

1. Apply additive migrations `20260907_2200_perm_policy`, `20260907_2210_record_scope`, and `20260907_2220_work_authority` with their matching application version. Existing organizations continue using version 1.
2. Inspect the per-organization preview: role and individual action changes, record-scope changes, uncertain historical handoffs, old pool grants, and existing execution items.
3. Resolve each legacy individual revoke by explicit removal or a meaningful role-wide denial. Protected-role and already-denied permissions cannot use a no-op role resolution. Included personal/AI features require explicit legacy-revoke removal; they cannot become role denials.
4. Review historical approval ownership and unknown phases using explicit evidence. Do not infer collaborators from every past owner.
5. Resolve existing workflow/campaign execution before activation. Unreviewed organization execution cannot silently acquire authority.
6. Activate the exact reviewed preview. The server rechecks membership, configuration, records, and execution state under the organization lock; stale reviews require regeneration.
7. Verify each activated organization's real configuration and operational journeys before broadening rollout.

Schema downgrade rejects active version 2 policies and personal campaigns that the old schema cannot represent. A rollback after activation requires a reviewed data and authority plan. The migration retains inserted Approved stages because live records or configuration may reference them.

## Remaining platform sequence

The active workplan above governs this continuation. The implemented service boundaries and remaining rollout work are recorded in the [module refactor sequence](permission-module-refactor-plan.md#next-refactor-sequence). The longer-term platform items below are context, not additional scope authorized by resuming the permission work. Review the live frontend before declaring UI acceptance.

| Order | Work | Start condition |
|---|---|---|
| 1 | Live frontend acceptance | Compare Roles and existing team/member controls with the selected concepts; verify the selected People navigation; check reviewed changes and personal/organization authority controls |
| 2 | Release review and first organization activation | Exact combined version validated; isolated activation rehearsal complete; explicit release and organization activation authorization |
| 3 | Remaining donor journeys and provider verification | Shared record and execution contracts stable; synthetic integration tests pass |
| 4 | Workflow and form-builder UX simplification | Editing, publication, validation, and execution authority remain behind existing service interfaces |
| 5 | Reporting redesign and per-organization Meta MCP | Evaluate the MCP connector and organization authorization; reuse existing ingestion/reporting contracts where applicable |
| 6 | Remaining platform UI and onboarding | Apply proven permission and scope patterns module by module |

Twilio end-to-end provider testing and Meta MCP configuration remain separate work. The earlier Meta app integration is blocked by app approval; a per-organization MCP connection is the chosen direction to evaluate. No provider traffic or production activation is part of this local implementation.

## Refactor rules

- Extract a module boundary when a concrete consumer needs it; avoid a generic framework for every model.
- Keep transport in routers, use cases and transactions in services, and phase transitions in their domain modules.
- Keep action permissions, record datasets, organization execution authority, and presentation separate.
- Migrate every consumer of a changed decision together, including aliases, list counts, exports, and queued work.
- Use independent agent ownership for separate modules, then run shared negative tests and full affected suites at integration.
- Remove the legacy policy path after all organizations migrate and its removal is separately verified; do not preserve two permanent permission systems.

[Module ownership and refactor sequence](permission-module-refactor-plan.md) · [Product model](permission-system-design.md)
