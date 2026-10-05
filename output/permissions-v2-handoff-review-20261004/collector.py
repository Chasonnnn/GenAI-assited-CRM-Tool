"""Private metadata ledger; accepts a caller-guarded, read-only clone Session.

No connections, writes, printing, files, decryption, or provider calls occur here.
The caller owns clone identity/network/crypto guards, encryption, and rollback.
Only aggregate_summary() is suitable for ordinary logs. The ledger contains IDs.
"""

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

ROLES = ("intake_specialist", "case_manager", "operations", "admin", "developer")
OWNER_TYPES = ("user", "queue")
ACTIVITIES = (
    "assigned",
    "unassigned",
    "surrogate_claimed",
    "surrogate_released",
    "surrogate_assigned_to_queue",
)
UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
MAX_RECORDS = 10_000
MAX_ROWS = 100_000
LIMITATIONS = (
    "ownership_activity_is_not_a_complete_mutation_log",
    "role_audits_are_not_a_complete_membership_history",
    "current_membership_created_at_does_not_exclude_reactivation",
    "stage_phase_uses_current_configuration_not_historical_configuration",
    "missing_events_do_not_establish_no_owner",
    "approval_actor_is_not_ownership_evidence",
    "workflow_execution_is_observation_not_mutation_receipt",
    "audit_hash_chain_not_validated_without_private_payloads",
)


class CollectionBlocked(Exception):
    """Static error code only; callers must not print DB exceptions or parameters."""


def require(condition, code):
    if not condition:
        raise CollectionBlocked(code)


def primitive(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        utc = (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )
        return utc.isoformat(timespec="microseconds")
    return value


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def enum_value(expression, values, label):
    from sqlalchemy import case

    return case((expression.in_(values), expression)).label(label)


def uuid_value(expression, label):
    from sqlalchemy import case, cast
    from sqlalchemy.dialects.postgresql import UUID as PgUUID

    return case(
        (expression.op("~")(UUID_PATTERN), cast(expression, PgUUID(as_uuid=True)))
    ).label(label)


def bool_value(expression, label):
    from sqlalchemy import case

    return case((expression == "true", True), (expression == "false", False)).label(
        label
    )


def rows(db, statement, *, limit=MAX_ROWS):
    result = db.execute(statement.limit(limit + 1)).mappings().all()
    require(len(result) <= limit, "metadata_row_limit_exceeded")
    return [{key: primitive(value) for key, value in row.items()} for row in result]


def current_intake(member):
    return bool(
        member
        and member["role"] == "intake_specialist"
        and member["membership_active"]
        and member["user_active"]
    )


def role_evidence(events, cutoff):
    """Observed role transitions only; absence cannot prove a historical role."""
    transitions = [
        event for event in events if event.get("old_role") or event.get("new_role")
    ]
    if any(event["at"] == cutoff for event in events):
        return "same_timestamp_role_order_uncertain"
    if any(
        event["at"] < cutoff
        and (
            event["event_type"] == "user_deactivated"
            or event.get("new_active") is False
        )
        for event in events
    ):
        return "historical_membership_activity_uncertain"
    if any(
        len(
            {
                (event.get("old_role"), event.get("new_role"))
                for event in transitions
                if event["at"] == at
            }
        )
        > 1
        for at in {event["at"] for event in transitions}
    ):
        return "role_chain_conflict"
    before = [event for event in transitions if event["at"] < cutoff]
    after = [event for event in transitions if event["at"] > cutoff]
    earlier = max(before, key=lambda event: event["at"], default=None)
    later = min(after, key=lambda event: event["at"], default=None)
    if earlier and later and earlier["new_role"] != later["old_role"]:
        return "role_chain_conflict"
    observed = earlier["new_role"] if earlier else later["old_role"] if later else None
    if observed is None:
        return "no_historical_role_observation"
    return (
        "audited_intake_observation"
        if observed == "intake_specialist"
        else "audited_other_role_observation"
    )


def classify_record(record, members, role_events):
    """Conservative review aid; never creates a proposed grant or no-owner decision."""
    owner = record["current_owner"]
    direct_owner = (
        owner["id"]
        if owner["type"] == "user" and current_intake(members.get(owner["id"]))
        else None
    )
    approvals = [
        event
        for event in record["status_history"]
        if event["approval_crossing_current_configuration"]
    ]
    events = record["ownership_activity"]
    reasons = []
    targets = sorted(
        {
            event["to_id"]
            for event in events
            if event["to_type"] == "user" and event["to_id"]
        }
    )
    result = {
        "current_direct_owner": {
            "user_id": direct_owner,
            "classification": "verified_current_metadata"
            if direct_owner
            else "not_present",
            "historical_ownership_proven": False,
            "scope_preservation_candidate": bool(
                direct_owner and not record["is_archived"]
            ),
            "action_permission_not_evaluated": True,
        },
        "historical_classification": "ambiguous",
        "verification_basis": None,
        "candidate_user_id": None,
        "recorded_user_targets": targets,
        "candidate_role_evidence": None,
        "reasons": reasons,
    }
    if record["phase_requires_review"]:
        reasons.append("phase_requires_review")
    if len(approvals) != 1:
        reasons.append(
            "no_explicit_approval_crossing"
            if not approvals
            else "multiple_approval_crossings"
        )
    else:
        approval = approvals[0]
        cutoff = approval["recorded_at"]
        if approval["effective_at"] != cutoff:
            reasons.append("approval_effective_time_differs_or_missing")
        if approval["is_undo"]:
            reasons.append("approval_is_undo")
        before = [event for event in events if event["at"] <= cutoff]
        timed = Counter(event["at"] for event in before)
        if any(count > 1 for count in timed.values()) or any(
            event["at"] == cutoff for event in before
        ):
            reasons.append("same_timestamp_ownership_order_uncertain")
        if any(not event["required_references_valid"] for event in before):
            reasons.append("malformed_or_missing_owner_reference")
        previous = None
        for event in before:
            source = (event["from_type"], event["from_id"])
            target = (event["to_type"], event["to_id"])
            # Unassigned activity has no destination. Do not turn it into no-owner proof.
            if event["event_type"] == "unassigned":
                previous = None
                continue
            if previous and all(source) and source != previous:
                reasons.append("recorded_ownership_chain_conflict")
            previous = target if all(target) else None
        latest = before[-1] if before else None
        candidate = latest["to_id"] if latest and latest["to_type"] == "user" else None
        result["candidate_user_id"] = candidate
        if candidate is None:
            reasons.append("no_recorded_user_owner_at_approval")
        elif not current_intake(members.get(candidate)):
            reasons.append("candidate_not_current_active_intake")
        if candidate:
            observed_role = role_evidence(role_events.get(candidate, []), cutoff)
            result["candidate_role_evidence"] = observed_role
            if observed_role in {
                "role_chain_conflict",
                "same_timestamp_role_order_uncertain",
                "audited_other_role_observation",
                "historical_membership_activity_uncertain",
            }:
                reasons.append(observed_role)
        if not reasons:
            result["historical_classification"] = "candidate"
    # Only an explicit, still-current human decision supplies historical verification.
    review = record.get("existing_review")
    if (
        review
        and review["fingerprint_matches"]
        and review["decision"] == "retain_verified_owner"
    ):
        retained = review["retained_user_id"]
        if (
            review["has_evidence_reference"]
            and current_intake(members.get(retained))
            and any(
                collaborator["user_id"] == retained
                and collaborator["membership_id"] == members[retained]["membership_id"]
                for collaborator in record["collaborators"]
            )
            and not record["phase_requires_review"]
        ):
            result["historical_classification"] = "verified"
            result["verification_basis"] = "existing_current_fingerprint_human_review"
            result["candidate_user_id"] = retained
    result["reasons"] = sorted(set(reasons))
    return result


def collect_handoff_evidence(db, org_id, source_commit):
    """Return a private per-org ledger. A guarded read-only snapshot is mandatory."""
    from app.core.stage_definitions import DEFAULT_STAGE_ORDER_BY_ENTITY
    from app.db.models import (
        AdminActionLog,
        AuditLog,
        DonorStatusHistory,
        EntityActivityLog,
        Membership,
        Pipeline,
        PipelineStage,
        SurrogateActivityLog,
        SurrogateStatusHistory,
        User,
        WorkflowExecution,
    )
    from app.db.models.record_access import (
        RecordCollaborator,
        RecordScopeMigrationReview,
    )
    from app.schemas.record_scope import RecordScopeRule
    from app.services import record_scope_service as scopes
    from sqlalchemy import and_, case, or_, select, text

    org_id = UUID(str(org_id))
    require(bool(re.fullmatch(r"[0-9a-f]{40}", source_commit)), "invalid_source_commit")
    require(
        not db.new and not db.dirty and not db.deleted, "session_has_pending_writes"
    )
    require(
        db.scalar(text("SHOW transaction_read_only")) == "on",
        "read_only_transaction_required",
    )
    require(
        db.scalar(text("SHOW transaction_isolation"))
        in {"repeatable read", "serializable"},
        "consistent_snapshot_required",
    )
    require(
        db.scalar(text("SHOW TimeZone")) in {"UTC", "Etc/UTC"},
        "utc_database_session_required",
    )

    known_keys = sorted(
        {key for keys in DEFAULT_STAGE_ORDER_BY_ENTITY.values() for key in keys}
    )
    stage_rows = rows(
        db,
        select(
            PipelineStage.id,
            PipelineStage.pipeline_id,
            enum_value(PipelineStage.stage_key, known_keys, "stage_key"),
            enum_value(
                PipelineStage.stage_type,
                ("intake", "post_approval", "paused", "terminal"),
                "stage_type",
            ),
            PipelineStage.order,
            PipelineStage.is_active,
        )
        .join(Pipeline, Pipeline.id == PipelineStage.pipeline_id)
        .where(Pipeline.organization_id == org_id),
    )
    stages = {row["id"]: row for row in stage_rows}
    gates = {
        row["pipeline_id"]: row
        for row in stage_rows
        if row["stage_key"] == "approved" and row["is_active"]
    }
    member_rows = rows(
        db,
        select(
            Membership.id.label("membership_id"),
            Membership.user_id,
            enum_value(Membership.role, ROLES, "role"),
            Membership.is_active.label("membership_active"),
            User.is_active.label("user_active"),
            Membership.created_at,
        )
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == org_id),
        limit=1000,
    )
    members = {row["user_id"]: row for row in member_rows}
    role_history = rows(
        db,
        select(
            AuditLog.id,
            AuditLog.target_id.label("user_id"),
            AuditLog.actor_user_id,
            AuditLog.created_at.label("at"),
            AuditLog.event_type,
            enum_value(AuditLog.details["old_role"].astext, ROLES, "old_role"),
            enum_value(AuditLog.details["new_role"].astext, ROLES, "new_role"),
        ).where(
            AuditLog.organization_id == org_id,
            AuditLog.target_type == "user",
            AuditLog.event_type.in_(("user_role_changed", "user_deactivated")),
        ),
    )
    for row in role_history:
        row["source"] = "audit_logs"
    platform_history = rows(
        db,
        select(
            AdminActionLog.id,
            AdminActionLog.target_user_id.label("user_id"),
            AdminActionLog.actor_user_id,
            AdminActionLog.created_at.label("at"),
            AdminActionLog.action.label("event_type"),
            enum_value(
                AdminActionLog.metadata_["role"]["old"].astext, ROLES, "old_role"
            ),
            enum_value(
                AdminActionLog.metadata_["role"]["new"].astext, ROLES, "new_role"
            ),
            bool_value(
                AdminActionLog.metadata_["is_active"]["old"].astext, "old_active"
            ),
            bool_value(
                AdminActionLog.metadata_["is_active"]["new"].astext, "new_active"
            ),
        ).where(
            AdminActionLog.target_organization_id == org_id,
            AdminActionLog.action == "member.update",
        ),
    )
    for row in platform_history:
        row["source"] = "admin_action_logs"
    role_history.extend(platform_history)
    role_history.sort(key=lambda row: (row["at"], row["source"], row["id"]))
    role_events = defaultdict(list)
    for row in role_history:
        role_events[row["user_id"]].append(row)

    records = []
    context = SimpleNamespace(org_id=org_id, user_id=None, role="admin")
    for kind in ("surrogate", "donor"):
        model = scopes.RECORDS[kind][0]
        display_number = getattr(model, f"{kind}_number")
        number_pattern = r"^S[0-9]+$" if kind == "surrogate" else r"^D[0-9]+$"
        post, pre = [
            scopes._stage_filter(
                context, kind, model, RecordScopeRule(assignment="all", phase=phase)
            )
            for phase in ("post_approval", "pre_approval")
        ]
        candidates = rows(
            db,
            select(
                model.id,
                case((display_number.op("~")(number_pattern), display_number)).label(
                    "record_number"
                ),
                model.stage_id,
                model.paused_from_stage_id,
                model.owner_id,
                enum_value(model.owner_type, OWNER_TYPES, "owner_type"),
                model.created_at,
                model.is_archived,
                post.label("post"),
                pre.label("pre"),
            )
            .where(model.organization_id == org_id, or_(post, and_(~pre, ~post)))
            .order_by(model.id),
            limit=MAX_RECORDS,
        )
        ids = [UUID(row["id"]) for row in candidates]
        if not ids:
            continue
        history_model = (
            SurrogateStatusHistory if kind == "surrogate" else DonorStatusHistory
        )
        history_record_id = getattr(history_model, f"{kind}_id")
        old = (
            history_model.from_stage_id
            if kind == "surrogate"
            else history_model.old_stage_id
        )
        new = (
            history_model.to_stage_id
            if kind == "surrogate"
            else history_model.new_stage_id
        )
        history_rows = rows(
            db,
            select(
                history_model.id,
                history_record_id.label("record_id"),
                old.label("from_stage_id"),
                new.label("to_stage_id"),
                history_model.changed_by_user_id,
                history_model.effective_at,
                history_model.recorded_at,
                history_model.is_undo,
                history_model.request_id,
            )
            .where(history_model.organization_id == org_id, history_record_id.in_(ids))
            .order_by(history_model.recorded_at, history_model.id),
        )
        for row in history_rows:
            origin, target = (
                stages.get(row["from_stage_id"]),
                stages.get(row["to_stage_id"]),
            )
            gate = gates.get(target["pipeline_id"]) if target else None
            row["approval_crossing_current_configuration"] = bool(
                origin
                and target
                and gate
                and origin["pipeline_id"] == target["pipeline_id"]
                and origin["is_active"]
                and target["is_active"]
                and origin["stage_type"] in {"intake", "post_approval"}
                and target["stage_type"] in {"intake", "post_approval"}
                and origin["order"] < gate["order"] <= target["order"]
            )
            row["to_approved_key"] = bool(target and target["stage_key"] == "approved")

        activity = SurrogateActivityLog if kind == "surrogate" else EntityActivityLog
        activity_record_id = getattr(activity, f"{kind}_id")
        at = activity.created_at if kind == "surrogate" else activity.recorded_at
        keys = (
            "from_user_id",
            "to_user_id",
            "from_owner_id",
            "to_owner_id",
            "from_queue_id",
            "to_queue_id",
        )
        activity_rows = rows(
            db,
            select(
                activity.id,
                activity_record_id.label("record_id"),
                activity.activity_type.label("event_type"),
                activity.actor_user_id,
                at.label("at"),
                *(uuid_value(activity.details[key].astext, key) for key in keys),
                *(
                    enum_value(activity.details[key].astext, OWNER_TYPES, key)
                    for key in ("from_owner_type", "to_owner_type")
                ),
            )
            .where(
                activity.organization_id == org_id,
                activity_record_id.in_(ids),
                activity.activity_type.in_(ACTIVITIES),
            )
            .order_by(at, activity.id),
        )
        for row in activity_rows:
            normalize_ownership(row, kind)

        audits = rows(
            db,
            select(
                AuditLog.id,
                AuditLog.target_id.label("record_id"),
                AuditLog.event_type,
                AuditLog.created_at.label("at"),
                AuditLog.actor_user_id,
                enum_value(
                    AuditLog.details["owner_type"].astext, OWNER_TYPES, "owner_type"
                ),
                uuid_value(AuditLog.details["owner_id"].astext, "owner_id"),
            )
            .where(
                AuditLog.organization_id == org_id,
                AuditLog.target_type == kind,
                AuditLog.target_id.in_(ids),
                AuditLog.event_type.in_(("surrogate_assigned", "surrogate_claimed")),
            )
            .order_by(AuditLog.created_at, AuditLog.id),
        )
        workflow_rows = rows(
            db,
            select(
                WorkflowExecution.id,
                WorkflowExecution.event_id,
                WorkflowExecution.entity_id.label("record_id"),
                WorkflowExecution.executed_at.label("at"),
                *(
                    uuid_value(WorkflowExecution.trigger_event[key].astext, key)
                    for key in ("old_owner_id", "new_owner_id")
                ),
                *(
                    enum_value(
                        WorkflowExecution.trigger_event[key].astext, OWNER_TYPES, key
                    )
                    for key in ("old_owner_type", "new_owner_type")
                ),
            )
            .where(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.entity_type == kind,
                WorkflowExecution.entity_id.in_(ids),
                WorkflowExecution.trigger_event.has_key("new_owner_id"),
            )
            .order_by(WorkflowExecution.executed_at, WorkflowExecution.id),
        )

        collaborator_id = getattr(RecordCollaborator, f"{kind}_id")
        collaborators = rows(
            db,
            select(
                RecordCollaborator.id,
                collaborator_id.label("record_id"),
                RecordCollaborator.user_id,
                RecordCollaborator.membership_id,
                RecordCollaborator.granted_by_user_id,
                RecordCollaborator.created_at,
            ).where(
                RecordCollaborator.organization_id == org_id, collaborator_id.in_(ids)
            ),
        )
        review_id = getattr(RecordScopeMigrationReview, f"{kind}_id")
        reviews = rows(
            db,
            select(
                RecordScopeMigrationReview.id,
                review_id.label("record_id"),
                RecordScopeMigrationReview.retained_user_id,
                RecordScopeMigrationReview.reviewed_by_user_id,
                RecordScopeMigrationReview.reviewed_at,
                enum_value(
                    RecordScopeMigrationReview.decision,
                    ("retain_verified_owner", "no_verified_owner"),
                    "decision",
                ),
                RecordScopeMigrationReview.record_fingerprint,
                (
                    RecordScopeMigrationReview.evidence_reference.is_not(None)
                    & (RecordScopeMigrationReview.evidence_reference != "")
                ).label("has_evidence_reference"),
            ).where(
                RecordScopeMigrationReview.organization_id == org_id, review_id.in_(ids)
            ),
        )
        groups = []
        for collection in (
            history_rows,
            activity_rows,
            audits,
            workflow_rows,
            collaborators,
            reviews,
        ):
            # SQL history/event queries retain chronology; unordered relationship
            # rows need stable ordering for a reproducible private ledger digest.
            if collection is collaborators or collection is reviews:
                collection.sort(key=lambda item: item["id"])
            indexed = defaultdict(list)
            for row in collection:
                indexed[row["record_id"]].append(row)
            groups.append(indexed)
        for row in candidates:
            require(row["post"] or not row["pre"], "canonical_phase_query_disagreement")
            record_id = row["id"]
            fp = scopes._record_fingerprint(kind, SimpleNamespace(**row))
            review = groups[5][record_id][0] if groups[5][record_id] else None
            if review:
                review["fingerprint_matches"] = review.pop("record_fingerprint") == fp
            record = {
                "kind": kind,
                "record_id": record_id,
                "record_number": row["record_number"],
                "record_fingerprint": fp,
                "stage_id": row["stage_id"],
                "paused_from_stage_id": row["paused_from_stage_id"],
                "phase_requires_review": not row["post"] and not row["pre"],
                "created_at": row["created_at"],
                "is_archived": row["is_archived"],
                "current_owner": {"type": row["owner_type"], "id": row["owner_id"]},
                "status_history": groups[0][record_id],
                "ownership_activity": groups[1][record_id],
                "ownership_audit_observations": groups[2][record_id],
                "workflow_owner_observations": groups[3][record_id],
                "collaborators": groups[4][record_id],
                "existing_review": review,
            }
            record["review_classification"] = classify_record(
                record, members, role_events
            )
            record["evidence_fingerprint"] = fingerprint(record)
            records.append(record)
    ledger = {
        "schema_version": 1,
        "organization_id": str(org_id),
        "source_commit": source_commit,
        "records": records,
        "members": sorted(member_rows, key=lambda row: row["user_id"]),
        "role_history": role_history,
        "stages": sorted(stage_rows, key=lambda row: row["id"]),
        "limitations": list(LIMITATIONS),
        "read_only": True,
        "complete_within_bounds": True,
        "grant_decisions_made": False,
    }
    ledger["evidence_fingerprint"] = fingerprint(ledger)
    return ledger


def normalize_ownership(row, kind):
    """Normalize only documented event shapes, retaining source row references."""
    event = row["event_type"]
    if kind == "donor":
        before = (row["from_owner_type"], row["from_owner_id"])
        after = (row["to_owner_type"], row["to_owner_id"])
        valid = all(before) and all(after)
    elif event == "assigned":
        before = ("user", row["from_user_id"]) if row["from_user_id"] else (None, None)
        after = ("user", row["to_user_id"])
        valid = row["to_user_id"] is not None
    elif event == "surrogate_claimed":
        before, after = ("queue", row["from_queue_id"]), ("user", row["to_user_id"])
        valid = bool(before[1] and after[1])
    elif event == "surrogate_released":
        before, after = ("user", row["from_user_id"]), ("queue", row["to_queue_id"])
        valid = bool(before[1] and after[1])
    elif event == "surrogate_assigned_to_queue":
        before, after = (
            (row["from_owner_type"], row["from_owner_id"]),
            ("queue", row["to_queue_id"]),
        )
        valid = bool(all(before) and after[1])
    else:
        before, after = ("user", row["from_user_id"]), (None, None)
        valid = row["from_user_id"] is not None
    row.update(
        from_type=before[0],
        from_id=before[1],
        to_type=after[0],
        to_id=after[1],
        required_references_valid=valid,
    )


def aggregate_summary(ledger):
    """Identifier-free stdout option; never include arbitrary record values."""
    classification = Counter()
    reasons = Counter()
    direct = 0
    for record in ledger["records"]:
        review = record["review_classification"]
        classification[review["historical_classification"]] += 1
        reasons.update(review["reasons"])
        direct += int(review["current_direct_owner"]["scope_preservation_candidate"])
    return {
        "schema_version": 1,
        "handoff_records": len(ledger["records"]),
        "historical_classification": dict(sorted(classification.items())),
        "reason_counts": dict(sorted(reasons.items())),
        "current_direct_owner_preservation_candidates": direct,
        "role_audit_observations": len(ledger["role_history"]),
        "read_only": True,
        "grant_decisions_made": False,
    }
