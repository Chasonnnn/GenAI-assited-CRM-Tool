"""Clone-only permission V2 rehearsal. Standard output contains aggregate JSON only.

Run with the repository's Python/dependencies and apps/api on PYTHONPATH.
ENV=test, DATABASE_URL, EXPECTED_CLONE_IP and REHEARSAL_RUN_ID are required.
The bootstrap must install the matching permission_rehearsal_guard sentinel.
No production encryption keys, provider credentials, workers or web app are needed.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

SOURCE_COMMIT = "c9b0018a418b01362f71a21a27f20f582473b029"
# Reuse the original clone identity without changing its sentinel.
CLONE_SOURCE_COMMIT = "00dc316eba4bb7261a9498d0ab7803407d226efc"
MAX_ORGS = 100
MAX_MEMBERS = 500
MAX_RECORDS = 250_000
PHASE = "startup"


class RehearsalBlocked(Exception):
    """A static, safe-to-print rehearsal condition; never wrap raw exception text."""


def require(condition, code):
    if not condition:
        raise RehearsalBlocked(code)


def emit(value):
    print(json.dumps(value, sort_keys=True, default=str), flush=True)


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def deny_crypto(*_args, **_kwargs):
    raise RehearsalBlocked("encrypted_field_access_blocked")


def restrict_statement(statement):
    """Defer ciphertext fields instead of decrypting unused ORM entity columns."""
    from sqlalchemy import inspect
    from sqlalchemy.orm import Load

    from app.db.types import EncryptedDate, EncryptedString

    options = []
    seen = set()
    for description in statement.column_descriptions:
        entity = description.get("entity")
        if entity is None or entity in seen or description.get("expr") is not entity:
            continue
        seen.add(entity)
        mapper = inspect(entity).mapper
        option = Load(entity)
        for attribute in mapper.column_attrs:
            if any(
                isinstance(column.type, (EncryptedDate, EncryptedString))
                for column in attribute.columns
            ):
                option = option.defer(getattr(entity, attribute.key), raiseload=True)
        options.append(option)
    return statement.options(*options) if options else statement


def restrict_orm_reads(state):
    if state.is_select:
        state.statement = restrict_statement(state.statement)


def install_guards():
    from app.core import encryption
    from app.db import types

    for name in (
        "decrypt_value",
        "encrypt_value",
        "decrypt_token",
        "encrypt_token",
        "get_fernet",
        "get_data_fernet",
    ):
        setattr(encryption, name, deny_crypto)
    types.decrypt_value = deny_crypto
    types.encrypt_value = deny_crypto


def check_clone(db):
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    expected_ip = os.environ.get("EXPECTED_CLONE_IP")
    run_id = os.environ.get("REHEARSAL_RUN_ID")
    require(bool(expected_ip and run_id), "missing_clone_identity")
    url = make_url(os.environ["DATABASE_URL"])
    require(url.host == expected_ip and (url.port or 5432) == 5432, "clone_host_mismatch")
    require(db.scalar(text("SELECT current_database()")) == url.database, "clone_database_mismatch")
    marker = db.execute(
        text("SELECT run_id, source_commit FROM public.permission_rehearsal_guard")
    ).all()
    require(
        len(marker) == 1 and tuple(marker[0]) == (run_id, CLONE_SOURCE_COMMIT),
        "clone_sentinel_mismatch",
    )


def policy_versions(db):
    from app.db.models import OrganizationPermissionPolicy

    return [
        tuple(row)
        for row in db.query(
            OrganizationPermissionPolicy.organization_id,
            OrganizationPermissionPolicy.version,
            OrganizationPermissionPolicy.configuration_revision,
        ).order_by(OrganizationPermissionPolicy.organization_id)
    ]


def member_rows(db, org_id):
    from app.db.models import Membership, User

    rows = (
        db.query(Membership.user_id, Membership.role, Membership.is_active, User.is_active)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.organization_id == org_id)
        .order_by(Membership.id)
        .all()
    )
    require(len(rows) <= MAX_MEMBERS, "member_limit_exceeded")
    return rows


def record_counts(db, org_id):
    from sqlalchemy import func

    from app.services import record_scope_service as scopes

    result = {}
    for kind, (model, _, _) in scopes.RECORDS.items():
        total, archived = (
            db.query(func.count(), func.count().filter(model.is_archived.is_(True)))
            .select_from(model)
            .filter(model.organization_id == org_id)
            .one()
        )
        require(total <= MAX_RECORDS, "record_limit_exceeded")
        result[kind] = {"total": total, "archived": archived}
    return result


def summarize(db, org_id, preview):
    from app.core.permissions import PERMISSION_REGISTRY

    members = member_rows(db, org_id)
    action_groups = defaultdict(lambda: {"members": 0, "gained": Counter(), "lost": Counter()})
    for row in preview.members:
        group = action_groups[row.role]
        group["members"] += 1
        group["gained"].update(row.gained)
        group["lost"].update(row.lost)
    scope_groups = defaultdict(
        lambda: {"members": 0, "current": 0, "proposed": 0, "gained": 0, "lost": 0}
    )
    scope = preview.scope_review
    for row in scope["member_record_scope_differences"]:
        group = scope_groups[f"{row['role']}:{row['module']}"]
        group["members"] += 1
        for key in ("current", "proposed", "gained", "lost"):
            group[key] += row[f"{key}_count"]
    unresolved_revokes = {str(value) for value in preview.unresolved_revoke_ids}
    return {
        "org_id": str(org_id),
        "source_commit": SOURCE_COMMIT,
        "version": preview.current_version,
        "ready": preview.ready,
        "digest": preview.digest,
        "records": record_counts(db, org_id),
        "members": {
            "active_by_role": dict(
                Counter(
                    role
                    for _, role, member_active, user_active in members
                    if member_active and user_active
                )
            ),
            "inactive": sum(not (ma and ua) for _, _, ma, ua in members),
        },
        "action_changes_by_role": dict(action_groups),
        "scope_member_record_access_pairs_by_role_module": dict(scope_groups),
        "existing_collaborators": len(scope["collaborators"]),
        "historical_reviews_by_decision": dict(
            Counter(row["decision"] for row in scope["resolutions"])
        ),
        "blockers": {
            "handoffs_by_kind": dict(Counter(row["kind"] for row in scope["unresolved_handoffs"])),
            "unknown_phase_by_kind": dict(
                Counter(
                    row["kind"]
                    for row in scope["unresolved_handoffs"]
                    if row["phase_requires_review"]
                )
            ),
            "legacy_pool_grants": len(scope["legacy_pool_grants"]),
            "missing_approval_gates": len(scope["missing_approval_gate_pipeline_ids"]),
            "revokes_by_role_permission": dict(
                Counter(
                    f"{row.role or 'missing_role'}:{row.permission if row.permission in PERMISSION_REGISTRY else 'unknown_permission'}"
                    for row in preview.revokes
                    if str(row.override_id) in unresolved_revokes
                )
            ),
            "execution_items_by_type": dict(
                Counter(row["item_type"] for row in preview.execution_review)
            ),
            "unreviewed_workflow_executions": sum(
                len(row.get("unreviewed_execution_ids", [])) for row in preview.execution_review
            ),
            "running_campaign_runs": sum(
                len(row.get("runs", [])) for row in preview.execution_review
            ),
        },
    }


def decision_template(preview, org_id):
    """Identifiers stay in an optional private file; ambiguous decisions remain null."""
    scope = preview.scope_review
    return {
        "source_commit": SOURCE_COMMIT,
        "run_id": os.environ["REHEARSAL_RUN_ID"],
        "org_id": str(org_id),
        "reviewed": False,
        "base_digest": preview.digest,
        "changes": {
            "role_permissions": {},
            "revoke_resolutions": [
                {"override_id": str(row.override_id), "action": None} for row in preview.revokes
            ],
            "execution_resolutions": [
                {"item_type": row["item_type"], "id": row["id"], "action": "pause"}
                for row in preview.execution_review
            ],
        },
        "handoffs": [
            {
                "kind": row["kind"],
                "record_id": row["record_id"],
                "request": {
                    "expected_fingerprint": row["fingerprint"],
                    "decision": None,
                    "intake_user_id": None,
                    "evidence_reference": None,
                    "resolved_phase": None,
                },
            }
            for row in scope["unresolved_handoffs"]
        ],
        "pool_grants": [
            {
                "id": row["id"],
                "request": {
                    "expected_fingerprint": row["fingerprint"],
                    "decision": None,
                    "replacement": None,
                },
            }
            for row in scope["legacy_pool_grants"]
        ],
    }


def recorded_assignment_classification(events, approvals, active_intake_ids):
    """Classify recorded evidence only; event coverage cannot establish ownership."""
    if len(approvals) != 1:
        return (
            "no_explicit_approval_transition" if not approvals else "multiple_approval_transitions",
            "not_evaluated",
            "not_evaluated",
            "not_evaluated",
            "not_evaluated",
        )

    def utc(value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    recorded_at, effective_at = approvals[0]
    cutoff = utc(recorded_at)
    before = [event for event in events if utc(event.created_at) <= cutoff]
    assignments = [
        event
        for event in before
        if event.activity_type in {"assigned", "surrogate_claimed"}
        and event.to_user_id in active_intake_ids
    ]
    targets = {event.to_user_id for event in assignments}
    latest = max((utc(event.created_at) for event in assignments), default=None)
    later = latest is not None and any(utc(event.created_at) > latest for event in before)
    ambiguous_time = any(utc(event.created_at) == cutoff for event in before) or (
        latest is not None and sum(utc(event.created_at) == latest for event in before) > 1
    )
    return (
        "single_explicit_approval_transition",
        "no_active_intake_assignment_target"
        if not targets
        else "one_active_intake_assignment_target"
        if len(targets) == 1
        else "multiple_active_intake_assignment_targets",
        "not_evaluated"
        if latest is None
        else "later_owner_event"
        if later
        else "no_later_recorded_owner_event",
        "same_timestamp_order_uncertain" if ambiguous_time else "distinct_recorded_timestamps",
        "effective_time_missing"
        if effective_at is None
        else "effective_time_differs"
        if utc(effective_at) != cutoff
        else "recorded_and_effective_time_equal",
    )


def intake_owner_candidate_evidence(db, org_id, candidate_ids, records, members, approvals):
    """Project only UUID-shaped owner references from recognized activity payloads."""
    from sqlalchemy import any_, case, cast
    from sqlalchemy.dialects.postgresql import ARRAY
    from sqlalchemy.dialects.postgresql import UUID as PgUUID

    from app.db.models import SurrogateActivityLog as Activity

    active_intake_ids = {
        user_id
        for user_id, (role, active) in members.items()
        if role == "intake_specialist" and active
    }
    events = defaultdict(list)
    event_types = {
        "assigned",
        "unassigned",
        "surrogate_claimed",
        "surrogate_released",
        "surrogate_assigned_to_queue",
    }
    uuid_pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

    def owner_uuid(key):
        value = Activity.details[key].astext
        return case((value.op("~")(uuid_pattern), cast(value, PgUUID(as_uuid=True)))).label(key)

    owner_type = Activity.details["from_owner_type"].astext
    statement = (
        db.query(
            Activity.surrogate_id,
            Activity.activity_type,
            Activity.created_at,
            *(
                owner_uuid(key)
                for key in (
                    "from_user_id",
                    "to_user_id",
                    "from_owner_id",
                    "from_queue_id",
                    "to_queue_id",
                )
            ),
            case((owner_type.in_(["user", "queue"]), owner_type)).label("from_owner_type"),
        )
        .filter(
            Activity.organization_id == org_id,
            Activity.surrogate_id == any_(cast(list(candidate_ids), ARRAY(PgUUID(as_uuid=True)))),
            Activity.activity_type.in_(event_types),
        )
        .order_by(Activity.created_at, Activity.id)
    )
    activity_counts = Counter()
    for row in statement.yield_per(1000):
        activity_counts["recognized_events"] += 1
        require(
            activity_counts["recognized_events"] <= MAX_RECORDS * 10,
            "activity_limit_exceeded",
        )
        required_refs = {
            "assigned": (row.to_user_id,),
            "unassigned": (row.from_user_id,),
            "surrogate_claimed": (row.from_queue_id, row.to_user_id),
            "surrogate_released": (row.from_user_id, row.to_queue_id),
            "surrogate_assigned_to_queue": (
                row.from_owner_type,
                row.from_owner_id,
                row.to_queue_id,
            ),
        }[row.activity_type]
        if any(value is None for value in required_refs):
            activity_counts["events_with_missing_or_non_uuid_required_owner_reference"] += 1
        events[row.surrogate_id].append(row)
    groups = Counter(
        recorded_assignment_classification(
            events[record_id], approvals.get(record_id, []), active_intake_ids
        )
        for record_id in candidate_ids
    )
    return {
        "surrogate_handoff_review_records": len(candidate_ids),
        "current_active_intake_owner_records": sum(
            records[record_id].owner_type == "user"
            and records[record_id].owner_id in active_intake_ids
            for record_id in candidate_ids
        ),
        "records_with_recognized_ownership_events": sum(
            bool(events[record_id]) for record_id in candidate_ids
        ),
        "activity_counts": dict(activity_counts),
        "recorded_assignment_evidence_groups": [
            {
                "approval_history": key[0],
                "assignment_targets": key[1],
                "later_recorded_ownership_evidence": key[2],
                "timestamp_order": key[3],
                "approval_timestamp_comparison": key[4],
                "records": count,
            }
            for key, count in sorted(groups.items())
        ],
        "historical_owner_inference_performed": False,
        "limitations": [
            "Some workflow and approval owner changes emit no ownership activity; continuous ownership cannot be verified.",
            "Current active Intake membership does not prove membership or role at the historical event.",
            "Activity created_at is compared with approval recorded_at, not the approval effective time.",
            "Only an explicit transition from an active operational stage below the current approval gate into that gate is counted.",
            "Current stage configuration does not establish historical stage ordering.",
            "Missing or malformed owner references and equal timestamps remain ambiguous.",
            "Current owner candidates and recorded assignment targets are not verified past owners.",
        ],
    }


def phase_context_agreement(group):
    post, pre = group["scalar_selected_post"], group["scalar_selected_pre"]
    full = (group["scalar_full_org_post"], group["scalar_full_org_pre"])
    entity = (group["entity_handoff_post"], group["entity_handoff_pre"])
    unknown = post is False and pre is False
    handoff = post is True or unknown
    phase = "pre_approval" if pre is True else "post_approval" if post is True else None
    raw_pairs = [(post, pre), full]
    if group["entity_handoff_included"]:
        raw_pairs.append(entity)
    return {
        "raw_phases_valid": all(
            all(isinstance(value, bool) for value in pair) and not all(pair) for pair in raw_pairs
        ),
        "scalar_contexts_match": full == (post, pre),
        "record_phase_matches": group["record_phase"] == phase,
        "count_filters_match": (group["post_filter_count"], group["pre_filter_count"])
        == (int(post is True), int(pre is True)),
        "handoff_inclusion_matches": group["entity_handoff_included"] == handoff,
        "handoff_values_match": entity == ((post, pre) if handoff else (None, None)),
        "snapshot_matches": group["snapshot_candidate"] == handoff
        and group["snapshot_phase_requires_review"] == (unknown if handoff else None),
    }


def phase_contexts(db, org_id, *, include_plans=False):
    """Compare unmodified service predicates across query contexts; emit no identities."""
    from time import perf_counter

    from sqlalchemy import and_, or_, text
    from sqlalchemy.orm import aliased

    from app.db.models import Pipeline, PipelineStage, Surrogate
    from app.schemas.record_scope import RecordScopeRule
    from app.services import record_scope_service as scopes

    started = perf_counter()
    require(
        db.query(Surrogate.id).filter(Surrogate.organization_id == org_id).count() <= MAX_RECORDS,
        "record_limit_exceeded",
    )
    current, origin = aliased(PipelineStage), aliased(PipelineStage)
    selected = {
        row.id
        for row in db.query(Surrogate.id)
        .join(current, current.id == Surrogate.stage_id)
        .join(origin, origin.id == Surrogate.paused_from_stage_id)
        .join(Pipeline, Pipeline.id == current.pipeline_id)
        .filter(
            Surrogate.organization_id == org_id,
            Pipeline.organization_id == org_id,
            current.is_active.is_(True),
            current.stage_type == "paused",
            origin.is_active.is_(True),
            origin.pipeline_id == current.pipeline_id,
            origin.stage_type.in_(["paused", "terminal"]),
        )
    }
    context = SimpleNamespace(org_id=org_id, user_id=None, role="admin")
    post, pre = (
        scopes._stage_filter(
            context, "surrogate", Surrogate, RecordScopeRule(assignment="all", phase=phase)
        )
        for phase in ("post_approval", "pre_approval")
    )
    snapshot = scopes.get_policy_scope_snapshot(db, org_id)
    candidates = {
        UUID(row["record_id"]): row
        for row in snapshot["handoff_candidates"]
        if row["kind"] == "surrogate" and UUID(row["record_id"]) in selected
    }
    # Keep the service's full-org entity query and handoff WHERE exactly intact.
    # The session privacy guard defers encrypted columns before execution.
    entity_handoff = {
        record.id: (is_post, is_pre)
        for record, is_post, is_pre in db.query(Surrogate, post.label("post"), pre.label("pre"))
        .filter(
            Surrogate.organization_id == org_id,
            or_(post, and_(~pre, ~post)),
        )
        .order_by(Surrogate.id)
        .all()
        if record.id in selected
    }
    scalar_query = db.query(Surrogate.id, post.label("post"), pre.label("pre")).filter(
        Surrogate.organization_id == org_id
    )
    full_org = {
        record_id: (is_post, is_pre)
        for record_id, is_post, is_pre in scalar_query.all()
        if record_id in selected
    }
    selected_query = {
        record_id: (is_post, is_pre)
        for record_id, is_post, is_pre in scalar_query.filter(Surrogate.id.in_(selected)).all()
    }
    require(set(full_org) == selected == set(selected_query), "phase_context_record_set_changed")
    groups = Counter()
    for record_id in sorted(selected):
        record = SimpleNamespace(id=record_id, organization_id=org_id)
        phase = scopes.record_phase(db, org_id, "surrogate", record)
        counts = tuple(
            db.query(Surrogate.id)
            .filter(Surrogate.organization_id == org_id, Surrogate.id == record_id, predicate)
            .count()
            for predicate in (post, pre)
        )
        require(all(count in {0, 1} for count in counts), "phase_context_count_invalid")
        candidate = candidates.get(record_id)
        entity = entity_handoff.get(record_id)
        groups[
            (
                candidate is not None,
                candidate["phase_requires_review"] if candidate else None,
                candidate["resolved"] if candidate else None,
                entity is not None,
                *(entity if entity is not None else (None, None)),
                *full_org[record_id],
                *selected_query[record_id],
                phase,
                *counts,
            )
        ] += 1
    fields = (
        "snapshot_candidate",
        "snapshot_phase_requires_review",
        "snapshot_resolved",
        "entity_handoff_included",
        "entity_handoff_post",
        "entity_handoff_pre",
        "scalar_full_org_post",
        "scalar_full_org_pre",
        "scalar_selected_post",
        "scalar_selected_pre",
        "record_phase",
        "post_filter_count",
        "pre_filter_count",
    )
    context_groups = []
    for values, count in sorted(groups.items(), key=lambda item: repr(item[0])):
        group = {**dict(zip(fields, values, strict=True)), "count": count}
        checks = phase_context_agreement(group)
        context_groups.append(
            {**group, "agreement_checks": checks, "contexts_agree": all(checks.values())}
        )
    result = {
        "org_id": str(org_id),
        "source_commit": SOURCE_COMMIT,
        "server_version": db.scalar(text("SHOW server_version")),
        "selected_records": len(selected),
        "selection": "active_paused_with_active_same_pipeline_paused_or_terminal_origin",
        "context_groups": context_groups,
        "contexts_agree": all(group["contexts_agree"] for group in context_groups),
        "phase_contexts_elapsed_ms": round((perf_counter() - started) * 1000, 2),
        "write_free": True,
    }
    if include_plans:
        result["plan_summaries"] = {
            "full_org_scalar": phase_plan_summary(db, scalar_query.statement),
            "selected_scalar": phase_plan_summary(
                db, scalar_query.filter(Surrogate.id.in_(selected)).statement
            ),
        }
    return result


def phase_plan_summary(db, statement):
    """Keep only whitelisted plan categories and cache-key counts, never expressions."""
    compiled = statement.compile(
        dialect=db.get_bind().dialect, compile_kwargs={"render_postcompile": True}
    )
    plan = (
        db.connection()
        .exec_driver_sql("EXPLAIN (FORMAT JSON) " + str(compiled), compiled.params)
        .scalar_one()
    )
    if isinstance(plan, str):
        plan = json.loads(plan)
    allowed_nodes = {
        "Result",
        "ProjectSet",
        "Append",
        "Merge Append",
        "Recursive Union",
        "BitmapAnd",
        "BitmapOr",
        "Gather",
        "Gather Merge",
        "Seq Scan",
        "Sample Scan",
        "Index Scan",
        "Index Only Scan",
        "Bitmap Index Scan",
        "Bitmap Heap Scan",
        "Tid Scan",
        "Tid Range Scan",
        "Subquery Scan",
        "Function Scan",
        "Table Function Scan",
        "Values Scan",
        "CTE Scan",
        "Named Tuplestore Scan",
        "WorkTable Scan",
        "Foreign Scan",
        "Custom Scan",
        "Nested Loop",
        "Merge Join",
        "Hash Join",
        "Materialize",
        "Memoize",
        "Sort",
        "Incremental Sort",
        "Group",
        "Aggregate",
        "WindowAgg",
        "Unique",
        "SetOp",
        "LockRows",
        "Limit",
        "Hash",
    }
    nodes, joins, subplans, cache_keys = Counter(), Counter(), Counter(), Counter()
    pending = [entry["Plan"] for entry in plan]
    visited = 0
    while pending:
        node = pending.pop()
        visited += 1
        require(visited <= 10_000, "explain_node_limit_exceeded")
        node_type = node.get("Node Type")
        nodes[node_type if node_type in allowed_nodes else "other"] += 1
        join = node.get("Join Type")
        if join is not None:
            joins[
                join if join in {"Inner", "Left", "Full", "Right", "Semi", "Anti"} else "other"
            ] += 1
        subplan = node.get("Subplan Name")
        if subplan is not None:
            name = re.match(r"^(InitPlan|SubPlan) \d+(?: |$)", subplan)
            subplans[name[1] if name else "other"] += 1
        if "Cache Key" in node:
            cache_keys["nodes_with_cache_key"] += 1
            if isinstance(node["Cache Key"], list):
                cache_keys["cache_key_items"] += len(node["Cache Key"])
            else:
                cache_keys["opaque_cache_key_values"] += 1
        pending.extend(node.get("Plans", []))
    return {
        "node_types": dict(nodes),
        "join_types": dict(joins),
        "subplan_types": dict(subplans),
        "cache_key_counts": dict(cache_keys),
        "expressions_omitted": True,
    }


def planner_contexts(db, org_id):
    """Compare fixed planner settings only inside the caller's read-only transaction."""
    from sqlalchemy import text

    original = {
        "jit": db.scalar(text("SHOW jit")),
        "enable_memoize": db.scalar(text("SHOW enable_memoize")),
        "enable_hashjoin": db.scalar(text("SHOW enable_hashjoin")),
        "enable_mergejoin": db.scalar(text("SHOW enable_mergejoin")),
        "plan_cache_mode": db.scalar(text("SHOW plan_cache_mode")),
    }
    require(
        all(value in {"on", "off"} for key, value in original.items() if key != "plan_cache_mode")
        and original["plan_cache_mode"] in {"auto", "force_custom_plan", "force_generic_plan"},
        "unexpected_planner_setting",
    )
    jit_above_cost = db.scalar(text("SHOW jit_above_cost"))
    require(
        bool(re.fullmatch(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", jit_above_cost)),
        "unexpected_jit_cost_setting",
    )
    variants = (
        ("baseline", {}),
        ("jit_off", {"jit": "off"}),
        ("memoize_off", {"enable_memoize": "off"}),
        ("jit_and_memoize_off", {"jit": "off", "enable_memoize": "off"}),
        (
            "joins_off",
            {
                "enable_hashjoin": "off",
                "enable_mergejoin": "off",
                "enable_memoize": "off",
                "jit": "off",
            },
        ),
        ("force_custom_plan", {"plan_cache_mode": "force_custom_plan"}),
    )
    results = []
    for name, overrides in variants:
        try:
            for setting, value in overrides.items():
                db.scalar(
                    text("SELECT set_config(:setting, :value, true)"),
                    {"setting": setting, "value": value},
                )
            actual = {setting: db.scalar(text(f"SHOW {setting}")) for setting in original}
            require(actual == {**original, **overrides}, "planner_override_not_applied")
            results.append(
                {
                    "variant": name,
                    "settings": {**actual, "jit_above_cost": jit_above_cost},
                    **phase_contexts(db, org_id, include_plans=True),
                }
            )
        finally:
            for setting, value in original.items():
                db.scalar(
                    text("SELECT set_config(:setting, :value, true)"),
                    {"setting": setting, "value": value},
                )
        require(
            all(db.scalar(text(f"SHOW {setting}")) == value for setting, value in original.items()),
            "planner_settings_not_restored",
        )
    return {"variants": results, "settings_restored": True, "write_free": True}


def query_trial(db, org_id, changes, org_ids):
    from importlib.util import module_from_spec, spec_from_file_location
    from time import perf_counter

    from app.schemas.permission_policy import PermissionPolicyChanges
    from app.services import permission_policy_service as policy
    from app.services import record_scope_service as scopes

    candidate_path = Path(__file__).with_name("phase_filter_candidate.py")
    candidate_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    spec = spec_from_file_location("_permission_phase_trial", candidate_path)
    require(spec is not None and spec.loader is not None, "query_candidate_not_loadable")
    candidate = module_from_spec(spec)
    spec.loader.exec_module(candidate)
    require(
        hashlib.sha256(candidate_path.read_bytes()).hexdigest() == candidate_hash,
        "query_candidate_changed_while_loading",
    )
    baseline = planner_contexts(db, org_id)
    original = scopes._stage_filter
    try:
        scopes._stage_filter = candidate._stage_filter
        phase_result = phase_contexts(db, org_id, include_plans=True)
        started = perf_counter()
        previews = [
            summarize(
                db,
                selected_id,
                policy.preview(
                    db, selected_id, changes if selected_id == org_id else PermissionPolicyChanges()
                ),
            )
            for selected_id in org_ids
        ]
        preview_elapsed_ms = round((perf_counter() - started) * 1000, 2)
    finally:
        scopes._stage_filter = original
    return {
        "baseline_planner_contexts": baseline,
        "candidate_sha256": candidate_hash,
        "candidate_phase_contexts": phase_result,
        "candidate_previews": previews,
        "candidate_preview_elapsed_ms": preview_elapsed_ms,
        "phase_filter_restored": scopes._stage_filter is original,
        "write_free": True,
        "activation_performed": False,
    }


def diagnose(db, org_id, preview):
    from sqlalchemy import false, func, or_

    from app.core.stage_definitions import SURROGATE_DEFAULT_COLORS
    from app.core.surrogate_access import _build_legacy_surrogate_visibility_filter
    from app.db.models import (
        AutomationWorkflow,
        IntendedParent,
        Pipeline,
        PipelineStage,
        Surrogate,
        SurrogateStatusHistory,
    )
    from app.schemas.record_scope import RecordScopeRule
    from app.services import record_scope_service as scopes
    from app.services.workflow_routing_retirement import GENERATED_ROUTING_PREFIX

    members = {user_id: (role, ma and ua) for user_id, role, ma, ua in member_rows(db, org_id)}

    def member_kind(user_id):
        if user_id is None:
            return "none"
        role, active = members.get(user_id, ("outside_org_or_missing", False))
        return f"active_{role}" if active else "inactive_or_missing"

    stages = {
        row.id: row
        for row in db.query(
            PipelineStage.id,
            PipelineStage.pipeline_id,
            PipelineStage.stage_key,
            PipelineStage.stage_type,
            PipelineStage.order,
            PipelineStage.is_active,
        )
        .join(Pipeline)
        .filter(Pipeline.organization_id == org_id)
    }

    def stage_kind(stage_id):
        stage = stages.get(stage_id)
        if stage is None:
            return "missing"
        key = (
            stage.stage_key if stage.stage_key in SURROGATE_DEFAULT_COLORS else "custom_or_unknown"
        )
        kind = (
            stage.stage_type
            if stage.stage_type in {"intake", "post_approval", "paused", "terminal"}
            else "other"
        )
        return f"{key}:{kind}:order={stage.order}:active={stage.is_active}"

    context = SimpleNamespace(org_id=org_id)
    phases = [
        scopes._stage_filter(
            context,
            "surrogate",
            Surrogate,
            RecordScopeRule(assignment="all", phase=phase),
        ).label(phase)
        for phase in ("pre_approval", "post_approval")
    ]
    records = {
        row.id: row
        for row in db.query(
            Surrogate.id,
            Surrogate.stage_id,
            Surrogate.paused_from_stage_id,
            Surrogate.created_by_user_id,
            Surrogate.owner_type,
            Surrogate.owner_id,
            Surrogate.is_archived,
            *phases,
        )
        .filter(Surrogate.organization_id == org_id)
        .limit(MAX_RECORDS + 1)
    }
    require(len(records) <= MAX_RECORDS, "record_limit_exceeded")
    handoff_ids = {
        UUID(row["record_id"])
        for row in preview.scope_review["unresolved_handoffs"]
        if row["kind"] == "surrogate"
    }
    historical, intake_actors, approvals = {}, defaultdict(set), defaultdict(list)
    history = (
        db.query(
            SurrogateStatusHistory.surrogate_id,
            SurrogateStatusHistory.from_stage_id,
            SurrogateStatusHistory.to_stage_id,
            SurrogateStatusHistory.changed_by_user_id,
            SurrogateStatusHistory.recorded_at,
            SurrogateStatusHistory.effective_at,
        )
        .filter(SurrogateStatusHistory.organization_id == org_id)
        .order_by(SurrogateStatusHistory.recorded_at.desc(), SurrogateStatusHistory.id.desc())
        .yield_per(1000)
    )
    for record_id, before, after, actor_id, recorded_at, effective_at in history:
        record = records.get(record_id)
        current = stages.get(record.stage_id) if record else None
        prior, following = stages.get(before), stages.get(after)
        if (
            record_id in handoff_ids
            and prior
            and following
            and prior.is_active
            and following.is_active
            and prior.pipeline_id == following.pipeline_id
            and following.stage_key == "approved"
            and prior.stage_type not in {"paused", "terminal"}
            and prior.order < following.order
        ):
            approvals[record_id].append((recorded_at, effective_at))
        if member_kind(actor_id) == "active_intake_specialist":
            intake_actors[record_id].add(actor_id)
        for stage_id in (after, before):
            stage = stages.get(stage_id)
            if (
                current
                and stage
                and stage.pipeline_id == current.pipeline_id
                and stage.stage_type not in {"paused", "terminal"}
            ):
                historical.setdefault(record_id, stage_id)
                break
    losses, rules, ip_rules = Counter(), {}, {}
    creator_totals = Counter(
        {
            "all_created": 0,
            "archived_created": 0,
            "nonarchived_created": 0,
            "visible_v1": 0,
            "visible_v2": 0,
        }
    )
    for user_id, (role, active) in members.items():
        if not active or role not in {"case_manager", "intake_specialist"}:
            continue
        actor = SimpleNamespace(org_id=org_id, user_id=user_id, role=role)
        rule = scopes.get_role_scope(db, org_id, role, "surrogates")
        rules[role] = {
            "assignment": rule.assignment,
            "phase": rule.phase,
            "stage_filter_count": len(rule.stage_ids),
        }
        ip_rule = scopes.get_role_scope(db, org_id, role, "intended_parents")
        ip_rules[role] = {
            "assignment": ip_rule.assignment,
            "phase": ip_rule.phase,
            "stage_filter_count": len(ip_rule.stage_ids),
        }
        if role == "case_manager":
            created = [
                record for record in records.values() if record.created_by_user_id == user_id
            ]
            creator_totals.update(
                {
                    "all_created": len(created),
                    "archived_created": sum(record.is_archived for record in created),
                }
            )
        current = func.coalesce(_build_legacy_surrogate_visibility_filter(role, user_id), false())
        proposed = func.coalesce(
            or_(*(condition for _, condition in scopes._routes(db, actor, "surrogate", Surrogate))),
            false(),
        )
        for record_id, was_visible, will_be_visible in db.query(
            Surrogate.id, current, proposed
        ).filter(scopes._boundary_filter(actor, Surrogate)):
            record = records[record_id]
            if role == "case_manager" and record.created_by_user_id == user_id:
                creator_totals.update(
                    {
                        "nonarchived_created": 1,
                        "visible_v1": int(was_visible),
                        "visible_v2": int(will_be_visible),
                    }
                )
            if not was_visible or will_be_visible:
                continue
            stage = stages.get(record.stage_id)
            paused_from = stages.get(record.paused_from_stage_id)
            nested_pause_or_terminal = (
                stage
                and paused_from
                and paused_from.is_active
                and paused_from.pipeline_id == stage.pipeline_id
                and paused_from.stage_type in {"paused", "terminal"}
            )
            effective = (
                historical.get(record_id)
                if stage and stage.stage_type == "terminal"
                else historical.get(record_id)
                if stage and stage.stage_type == "paused" and nested_pause_or_terminal
                else (record.paused_from_stage_id or historical.get(record_id))
                if stage and stage.stage_type == "paused"
                else record.stage_id
            )
            phase = (
                "pre_approval"
                if record.pre_approval
                else "post_approval"
                if record.post_approval
                else "unknown"
            )
            creator = (
                "self"
                if record.created_by_user_id == user_id
                else member_kind(record.created_by_user_id)
            )
            losses[
                (
                    role,
                    stage_kind(record.stage_id),
                    stage_kind(record.paused_from_stage_id or record.stage_id),
                    stage_kind(effective),
                    phase,
                    creator,
                )
            ] += 1
    evidence = Counter()
    for candidate in preview.scope_review["unresolved_handoffs"]:
        if candidate["kind"] != "surrogate":
            evidence[("other_record_kind",)] += 1
            continue
        record = records[UUID(candidate["record_id"])]
        owner = (
            member_kind(record.owner_id) if record.owner_type == "user" else "queue_or_unassigned"
        )
        actors = len(intake_actors[record.id])
        evidence[
            (
                "unknown_phase" if candidate["phase_requires_review"] else "known_post_approval",
                "archived" if record.is_archived else "active",
                owner,
                "no_intake_stage_actor"
                if actors == 0
                else "one_intake_stage_actor"
                if actors == 1
                else "multiple_intake_stage_actors",
            )
        ] += 1
    workflow_ids = [
        UUID(row["id"]) for row in preview.execution_review if row["item_type"] == "workflow"
    ]
    workflows = Counter()
    for enabled, system, key, authority_missing in db.query(
        AutomationWorkflow.is_enabled,
        AutomationWorkflow.is_system_workflow,
        AutomationWorkflow.system_key,
        AutomationWorkflow.execution_authority.is_(None),
    ).filter(
        AutomationWorkflow.organization_id == org_id,
        AutomationWorkflow.id.in_(workflow_ids),
    ):
        workflows.update(
            {
                "review_items": 1,
                "enabled": int(enabled),
                "system_workflow": int(system),
                "generated_routing_key": int(
                    bool(key and key.startswith(GENERATED_ROUTING_PREFIX))
                ),
                "authority_missing": int(authority_missing),
            }
        )
    workflows["pending_unreviewed_executions"] = sum(
        len(row.get("unreviewed_execution_ids", [])) for row in preview.execution_review
    )
    ip_owners = Counter(
        member_kind(owner_id) if owner_type == "user" else "queue_or_unassigned"
        for owner_type, owner_id in db.query(
            IntendedParent.owner_type, IntendedParent.owner_id
        ).filter(IntendedParent.organization_id == org_id)
    )
    return {
        "org_id": str(org_id),
        "surrogate_role_rules": rules,
        "intended_parent_role_rules": ip_rules,
        "lost_scope_groups": [
            {
                "role": key[0],
                "current_stage": key[1],
                "v1_effective_stage": key[2],
                "v2_effective_stage_evidence": key[3],
                "canonical_v2_phase": key[4],
                "creator_membership": key[5],
                "member_record_pairs": count,
            }
            for key, count in sorted(losses.items())
        ],
        "case_manager_creator_counts": dict(creator_totals),
        "handoff_evidence_groups": [
            {"classification": list(key), "records": count}
            for key, count in sorted(evidence.items())
        ],
        "status_actor_is_not_verified_owner": True,
        "intake_owner_candidate_evidence": intake_owner_candidate_evidence(
            db, org_id, handoff_ids, records, members, approvals
        ),
        "workflow_review": dict(workflows),
        "intended_parent_owner_membership": dict(ip_owners),
    }


def preserved_state(db, org_id):
    """Identity/access metadata only; never read applicant content or credentials."""
    from app.db.models import (
        Membership,
        OrganizationPermissionPolicy,
        RecordCollaborator,
        RolePermission,
        RoleRecordScope,
        UserPermissionOverride,
        UserRecordScopeAddition,
    )
    from app.services import record_scope_service as scopes

    result = {}
    for kind, (model, _, _) in scopes.RECORDS.items():
        fields = [
            model.id,
            model.organization_id,
            model.stage_id,
            model.owner_type,
            model.owner_id,
            model.is_archived,
        ]
        if kind == "surrogate":
            fields.append(model.created_by_user_id)
        if kind in {"surrogate", "donor"}:
            fields.append(model.paused_from_stage_id)
        rows = db.query(*fields).order_by(model.id).all()
        require(len(rows) <= MAX_RECORDS, "record_limit_exceeded")
        result[kind] = digest([tuple(row) for row in rows])
    for model in (Membership, RecordCollaborator):
        result[model.__tablename__] = digest(
            [tuple(row) for row in db.query(*model.__table__.columns).order_by(model.id).all()]
        )
    for model in (
        OrganizationPermissionPolicy,
        RolePermission,
        RoleRecordScope,
        UserPermissionOverride,
        UserRecordScopeAddition,
    ):
        ordering = model.organization_id if model is OrganizationPermissionPolicy else model.id
        result[f"other_orgs:{model.__tablename__}"] = digest(
            [
                tuple(row)
                for row in db.query(*model.__table__.columns)
                .filter(model.organization_id != org_id)
                .order_by(ordering)
                .all()
            ]
        )
    return result


def activation_invariants(db, org_id, reviewed):
    from sqlalchemy import false, func

    from app.core.permissions import PROTECTED_ROLES
    from app.db.models import Surrogate
    from app.services import permission_service
    from app.services import record_scope_service as scopes

    expected_actions = {row.user_id: set(row.proposed) for row in reviewed.members}
    expected_scopes = {
        (UUID(row["user_id"]), row["module"]): row["proposed_count"]
        for row in reviewed.scope_review["member_record_scope_differences"]
    }
    counters = Counter()
    for user_id, role, member_active, user_active in member_rows(db, org_id):
        actor = SimpleNamespace(org_id=org_id, user_id=user_id, role=role)
        active = member_active and user_active
        actual_actions = permission_service.get_effective_permissions(db, org_id, user_id, role)
        require(
            actual_actions == (expected_actions[user_id] if active else set()),
            "effective_permissions_differ_from_preview",
        )
        counters["member_permission_sets_checked"] += 1
        for kind, (model, module, _) in scopes.RECORDS.items():
            visible = scopes.build_visibility_filter(db, actor, kind)
            count = db.query(func.count()).select_from(model).filter(visible).scalar()
            require(
                count == (expected_scopes[(user_id, module)] if active else 0),
                "record_scope_count_differs_from_preview",
            )
            require(
                db.query(model.id).filter(visible, model.organization_id != org_id).first() is None,
                "cross_tenant_scope_detected",
            )
            if role not in PROTECTED_ROLES:
                require(
                    db.query(model.id).filter(visible, model.is_archived.is_(True)).first() is None,
                    "archived_scope_detected",
                )
            personal = scopes.build_visibility_filter(db, actor, kind, personal_only=True)
            require(
                db.query(model.id).filter(personal, ~func.coalesce(visible, false())).first()
                is None,
                "personal_scope_exceeds_record_scope",
            )
            counters["member_module_scopes_checked"] += 1
        if active and role == "case_manager":
            visible = scopes.build_visibility_filter(db, actor, "surrogate")
            missing = (
                db.query(Surrogate.id)
                .filter(
                    Surrogate.organization_id == org_id,
                    Surrogate.created_by_user_id == user_id,
                    Surrogate.is_archived.is_(False),
                    ~func.coalesce(visible, false()),
                )
                .first()
            )
            require(missing is None, "creator_scope_missing_after_activation")
            counters["case_manager_creator_scopes_checked"] += 1
    return dict(counters)


def resolve_explicit(db, actor, plan):
    from app.schemas.permission_policy import PermissionPolicyChanges
    from app.schemas.record_scope import HandoffMigrationReviewRequest, LegacyPoolResolutionRequest
    from app.services import permission_policy_service as policy
    from app.services import record_scope_service as scopes

    require(
        policy.preview(db, actor.org_id, PermissionPolicyChanges()).digest
        == plan.get("base_digest"),
        "base_preview_changed",
    )
    # Validate all request shapes before the services make their individual commits.
    handoffs = [
        (
            row["kind"],
            UUID(row["record_id"]),
            HandoffMigrationReviewRequest.model_validate(row["request"]),
        )
        for row in plan.get("handoffs", [])
    ]
    pools = [
        (UUID(row["id"]), LegacyPoolResolutionRequest.model_validate(row["request"]))
        for row in plan.get("pool_grants", [])
    ]
    for kind, record_id, request in handoffs:
        scopes.resolve_handoff_migration(db, actor, kind, record_id, request)
    for grant_id, request in pools:
        scopes.resolve_legacy_pool_grant(db, actor, grant_id, request)
    return {"handoff_decisions_applied": len(handoffs), "pool_decisions_applied": len(pools)}


def self_check():
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from app.db import types
    from app.db.models import Donor, Surrogate

    for model in (Surrogate, Donor):
        statement = restrict_statement(select(model))
        sql = str(statement.compile(dialect=postgresql.dialect()))
        require(
            not re.search(rf"\b{model.__tablename__}\.email\b", sql), "encrypted_email_was_selected"
        )
        require(
            not re.search(rf"\b{model.__tablename__}\.phone\b", sql), "encrypted_phone_was_selected"
        )
        require(f"{model.__tablename__}.owner_id" in sql, "required_metadata_missing")
    for operation in (types.decrypt_value, types.encrypt_value):
        try:
            operation("synthetic guard probe")
        except RehearsalBlocked:
            continue
        raise RehearsalBlocked("crypto_guard_failed")
    emit(
        {
            "status": "self_check_passed",
            "database_contacted": False,
            "orm_encrypted_columns_deferred": True,
            "crypto_denied": True,
        }
    )


def run(args):
    global PHASE
    from sqlalchemy import event, text
    from sqlalchemy.orm import Session

    from app.core.config import settings
    from app.db.models import Organization
    from app.db.session import engine
    from app.schemas.permission_policy import PermissionPolicyChanges
    from app.services import permission_policy_service as policy

    install_guards()
    if args.self_check:
        self_check()
        return
    require(settings.ENV == "test", "rehearsal_requires_test_environment")
    require(not Path(".env").exists(), "dotenv_file_not_allowed")
    for key in (
        "DATA_ENCRYPTION_KEY",
        "META_ENCRYPTION_KEY",
        "FERNET_KEY",
        "PII_HASH_KEY",
        "VERSION_ENCRYPTION_KEY",
    ):
        require(
            not getattr(settings, key).get_secret_value(), "production_crypto_material_not_allowed"
        )
    org_id = UUID(os.environ["ORG_ID"]) if os.environ.get("ORG_ID") else None
    plan = json.loads(Path(args.decision_file).read_text()) if args.decision_file else None
    if plan is not None:
        require(
            org_id is not None and plan.get("org_id") == str(org_id),
            "decision_organization_mismatch",
        )
        require(
            plan.get("source_commit") == SOURCE_COMMIT
            and plan.get("run_id") == os.environ.get("REHEARSAL_RUN_ID"),
            "decision_rehearsal_mismatch",
        )
    changes = (
        PermissionPolicyChanges.model_validate(plan.get("changes", {}))
        if plan
        else PermissionPolicyChanges()
    )
    with Session(engine, autoflush=False) as db:
        event.listen(db, "do_orm_execute", restrict_orm_reads)
        PHASE = "clone_guard"
        if args.mode in {
            "preview",
            "diagnose",
            "phase-contexts",
            "planner-contexts",
            "query-trial",
        }:
            db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text("SET LOCAL statement_timeout = '120s'"))
        db.execute(text("SET LOCAL lock_timeout = '10s'"))
        check_clone(db)
        original_versions = policy_versions(db)
        org_ids = [row.id for row in db.query(Organization.id).order_by(Organization.id)]
        require(len(org_ids) <= MAX_ORGS, "organization_limit_exceeded")
        require(org_id is None or org_id in org_ids, "organization_not_found")
        if args.mode in {
            "diagnose",
            "assert-blocked",
            "phase-contexts",
            "planner-contexts",
            "query-trial",
        }:
            require(org_id is not None, "diagnosis_requires_one_organization")
            require(policy.get_version(db, org_id) == 1, "organization_already_active")
            PHASE = args.mode
            if args.mode == "phase-contexts":
                result = phase_contexts(db, org_id)
            elif args.mode == "planner-contexts":
                result = planner_contexts(db, org_id)
            elif args.mode == "query-trial":
                result = query_trial(db, org_id, changes, org_ids)
            else:
                preview = policy.preview(db, org_id, changes)
            if args.mode == "diagnose":
                result = diagnose(db, org_id, preview)
            elif args.mode == "assert-blocked":
                require(not preview.ready, "activation_not_blocked_do_not_probe")
                actors = [
                    user_id
                    for user_id, role, ma, ua in member_rows(db, org_id)
                    if ma and ua and role in {"admin", "developer"}
                ]
                require(bool(actors), "active_administrator_required")
                try:
                    policy.activate(db, org_id, actors[0], changes, preview.digest)
                except policy.PermissionPolicyConflict as error:
                    require(
                        str(error)
                        == "Resolve all legacy revokes, record-scope review items, and unreviewed execution first",
                        "unexpected_activation_conflict",
                    )
                else:
                    raise RehearsalBlocked("unready_activation_unexpectedly_succeeded")
                result = {"activation_blocked_by_unresolved_review": True}
            db.rollback()
            db.execute(text("SET TRANSACTION READ ONLY"))
            require(policy_versions(db) == original_versions, "diagnosis_changed_policy_versions")
            db.rollback()
            emit({"status": f"{args.mode}_complete", "policy_versions_unchanged": True, **result})
            return result
        if args.mode == "preview":
            PHASE = "preview"
            selected = (
                org_ids
                if getattr(args, "preview_all_orgs", False)
                else [org_id]
                if org_id
                else org_ids
            )
            require(
                not args.template_file or len(selected) == 1, "template_requires_one_organization"
            )
            summaries = []
            for selected_id in selected:
                member_rows(db, selected_id)
                record_counts(db, selected_id)
                preview = policy.preview(
                    db,
                    selected_id,
                    changes
                    if selected_id == org_id or org_id is None
                    else PermissionPolicyChanges(),
                )
                summaries.append(summarize(db, selected_id, preview))
                if args.template_file:
                    with os.fdopen(
                        os.open(args.template_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                        "w",
                    ) as handle:
                        json.dump(decision_template(preview, selected_id), handle, indent=2)
            db.rollback()
            db.execute(text("SET TRANSACTION READ ONLY"))
            require(policy_versions(db) == original_versions, "preview_changed_policy_versions")
            db.rollback()
            emit({"status": "preview_complete", "write_free": True, "organizations": summaries})
            return
        require(
            org_id is not None and plan is not None and plan.get("reviewed") is True,
            "explicit_reviewed_decisions_required",
        )
        actor_id = UUID(os.environ["ACTOR_USER_ID"])
        policy.require_administrator(db, org_id, actor_id)
        require(policy.get_version(db, org_id) == 1, "organization_already_active")
        actor = SimpleNamespace(org_id=org_id, user_id=actor_id, role="admin")
        if args.mode == "resolve-explicit":
            PHASE = "explicit_scope_resolutions"
            result = resolve_explicit(db, actor, plan)
            emit(
                {"status": "explicit_resolutions_applied", **result, "activation_performed": False}
            )
            return
        PHASE = "activation_preview"
        reviewed = policy.preview(db, org_id, changes)
        require(reviewed.ready, "unresolved_migration_blockers")
        require(
            bool(args.reviewed_digest) and reviewed.digest == args.reviewed_digest,
            "activation_preview_changed",
        )
        before = preserved_state(db, org_id)
        PHASE = "activation"
        policy.activate(db, org_id, actor_id, changes, reviewed.digest)
        db.commit()
        PHASE = "post_activation_invariants"
        require(policy.get_version(db, org_id) == 2, "activation_version_missing")
        require(
            before == preserved_state(db, org_id),
            "preserved_identity_or_other_tenant_state_changed",
        )
        checks = activation_invariants(db, org_id, reviewed)
        emit(
            {
                "status": "clone_activation_verified",
                "org_id": str(org_id),
                "source_commit": SOURCE_COMMIT,
                "reviewed_digest": reviewed.digest,
                "invariants": checks,
                "production_activated": False,
            }
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=(
            "preview",
            "diagnose",
            "phase-contexts",
            "planner-contexts",
            "query-trial",
            "assert-blocked",
            "recheck",
            "resolve-explicit",
            "activate",
        ),
        default=os.environ.get("REHEARSAL_MODE", "preview"),
    )
    parser.add_argument("--decision-file", default=os.environ.get("DECISION_FILE"))
    parser.add_argument("--template-file", default=os.environ.get("TEMPLATE_FILE"))
    parser.add_argument("--reviewed-digest", default=os.environ.get("REVIEWED_DIGEST"))
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        if args.mode == "recheck" and not args.self_check:
            require(bool(os.environ.get("ORG_ID")), "recheck_requires_one_organization")
            modes = ("preview", "diagnose", "phase-contexts", "assert-blocked")
            for mode in modes:
                result = run(
                    argparse.Namespace(
                        **{**vars(args), "mode": mode, "preview_all_orgs": mode == "preview"}
                    )
                )
                if mode == "phase-contexts":
                    require(result["contexts_agree"], "phase_contexts_disagree")
            emit(
                {
                    "status": "recheck_complete",
                    "modes": list(modes),
                    "resolutions_applied": False,
                }
            )
        else:
            run(args)
    except Exception as error:
        emit(
            {
                "status": "blocked",
                "phase": PHASE,
                "condition": str(error)
                if isinstance(error, RehearsalBlocked)
                else type(error).__name__,
                "mutations_may_have_committed": args.mode
                not in {"preview", "diagnose", "phase-contexts", "planner-contexts", "query-trial"},
            }
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
