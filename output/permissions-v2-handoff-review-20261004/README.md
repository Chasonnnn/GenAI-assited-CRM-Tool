# Historical handoff evidence collector

`collector.py` exports `collect_handoff_evidence(db, org_id, source_commit)` and `aggregate_summary(ledger)`. The first returns a private, JSON-serializable ledger for one organization. The second returns identifier-free counts. Neither function prints, connects, writes files, resolves reviews, grants access, or activates a policy.

The caller supplies the clone-identity, outbound-network, encrypted-column, and fail-closed crypto guards. The collector requires a clean Session, PostgreSQL read-only repeatable-read or serializable transaction, and UTC session timezone. The caller encrypts the private ledger and rolls back the transaction. Ordinary logs may contain only `aggregate_summary()` or static error codes.

The ledger includes surrogate and donor candidates selected by the current canonical phase predicate; service-compatible record fingerprints; current owner and archive metadata; active membership metadata; status transition IDs and recorded/effective timestamps; recognized ownership activity; assignment audit observations; workflow trigger owner observations; organization and platform role-change metadata; existing collaborators and human-review metadata. Every query is organization scoped. JSON fields are projected individually and checked against UUID, role, ownership-type, or boolean allowlists. Stage keys use the repository's known keys; custom labels and keys are omitted. No names, email addresses, phone numbers, notes, status reasons, evidence-reference text, message bodies, tokens, ciphertext, IP addresses, user agents, full JSON payloads, workflow actions, or execution descriptions are selected.

`current_direct_owner` identifies current active Intake ownership separately. An unarchived direct owner is a preservation candidate; action permissions are not evaluated, and this does not prove ownership at historical approval.

Historical classification is `candidate` only when one recorded approval crossing and a consistent last recorded user assignment have no detected time, chain, phase, role, or current-membership conflict. These observations cannot establish complete ownership or role history. `verified` is reserved for an existing human `retain_verified_owner` review whose record fingerprint is current, evidence reference is present, retained Intake member is currently active, and matching collaborator exists. Every other case is `ambiguous`. No classification produces a grant or a `no_verified_owner` decision.

Missing assignments never mean no historical owner. The approval actor is not treated as an owner. Approval crossings use current pipeline configuration; the ledger also includes all status metadata and explicit entries to the Approved key for manual comparison. Equal timestamps do not establish event order. Backdated approvals, repeated approval cycles, malformed ownership references, and contradictory chains remain ambiguous. Workflow trigger metadata is an observation rather than a successful mutation receipt.

Role evidence includes `audit_logs` user-role changes/deactivations and `admin_action_logs` member updates. Current membership timestamps do not exclude invite reactivation. These logs cannot establish historical membership continuity. Ownership activity is also incomplete: `workflow_record_actions.assign_surrogate` changes ownership without an ownership activity row. No audit hash-chain verification is claimed because the collector never reads the full payloads.

Bounds fail closed at 10,000 candidates per record kind, 1,000 members, and 100,000 rows per metadata query. A limit violation produces no partial ledger. Ledger and per-record evidence fingerprints cover the selected metadata; they are separate from the service's migration record fingerprint.

Validation: eight standard-library synthetic tests passed, covering assignment versus verification, current owner versus stage actor, approval timing/cycles, role and membership ambiguity, conflicting owner chains, stale human reviews, aggregate privacy, and timestamp ordering. Eighteen SQL query shapes compiled against the current app models with network connections disabled and synthetic surrogate/donor rows. Ruff passed. No database or cloud query ran during development.

Commands:

```sh
mise exec -- python -B -m unittest discover -s output/permissions-v2-handoff-review-20261004 -p test_collector.py
UV_CACHE_DIR=/private/tmp/crm-live-qa-tests-uv-cache mise exec -- uv run --project apps/api --no-sync ruff check output/permissions-v2-handoff-review-20261004/collector.py output/permissions-v2-handoff-review-20261004/test_collector.py
```

Source owners: `record_scope_service._stage_filter` and `_record_fingerprint`; `SurrogateStatusHistory` / `DonorStatusHistory`; `activity_service.log_assigned` / `log_unassigned`; `queue_service` claim/release/queue assignment; `surrogates_write.assign_surrogate`; `WorkflowExecution.trigger_event`; `audit_service.log_user_role_changed` / `log_user_deactivated`; `platform_service.update_member`; `auth_service` invite reactivation; `RecordScopeMigrationReview` / `RecordCollaborator`.
