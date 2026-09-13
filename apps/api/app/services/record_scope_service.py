"""Shared SQL record visibility and retained Intake collaboration.

Record rules select the same records for viewing and editing. Action permissions
are checked separately. Configuration writes and their audit entries are atomic.
"""

from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import and_, case, false, func, literal, or_, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.stage_definitions import PROTECTED_SYSTEM_STAGES_BY_ENTITY
from app.db.enums import AuditEventType, Role
from app.db.models import (
    Donor,
    IntendedParent,
    Membership,
    Pipeline,
    PipelineStage,
    Surrogate,
    User,
)
from app.db.models.record_access import (
    RecordCollaborator,
    RecordScopeMigrationReview,
    RoleRecordScope,
    UserRecordScopeAddition,
)
from app.schemas.record_scope import RecordAccessExplanation, RecordScopeRule

RECORDS = {
    "surrogate": (Surrogate, "surrogates", ("surrogate",)),
    "donor": (Donor, "donors", ("egg_donor", "sperm_donor")),
    "intended_parent": (IntendedParent, "intended_parents", ("intended_parent",)),
}
MODULE_KINDS = {definition[1]: kind for kind, definition in RECORDS.items()}
PROTECTED_ROLES = {Role.ADMIN.value, Role.DEVELOPER.value}


def _role(role) -> str:
    return role.value if hasattr(role, "value") else str(role)


def _enabled(db, org_id) -> bool:
    from app.services import permission_policy_service

    return permission_policy_service.is_enabled(db, org_id)


def default_rule(role, module: str) -> RecordScopeRule:
    role = _role(role)
    if role in PROTECTED_ROLES or role == "operations":
        return RecordScopeRule(assignment="all")
    if role == Role.CASE_MANAGER.value:
        return RecordScopeRule(
            assignment="all", phase="all" if module == "intended_parents" else "post_approval"
        )
    if role == Role.INTAKE_SPECIALIST.value:
        return RecordScopeRule(
            assignment="assigned", phase="all" if module == "intended_parents" else "pre_approval"
        )
    return RecordScopeRule(assignment="none")


def get_role_scope(db: Session, org_id: UUID, role, module: str) -> RecordScopeRule:
    if module not in MODULE_KINDS:
        raise ValueError("Unknown record module")
    if _role(role) in PROTECTED_ROLES:
        return default_rule(role, module)
    row = (
        db.query(RoleRecordScope)
        .filter_by(organization_id=org_id, role=_role(role), module=module)
        .first()
    )
    return (
        RecordScopeRule.model_validate(row, from_attributes=True)
        if row
        else default_rule(role, module)
    )


def _member(db, org_id, user_id, *, include_inactive=False) -> Membership:
    query = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == org_id,
            Membership.user_id == user_id,
        )
    )
    if not include_inactive:
        query = query.filter(Membership.is_active.is_(True), User.is_active.is_(True))
    member = query.first()
    if member is None:
        raise LookupError("Member not found")
    return member


def _active_member_filter(session):
    return (
        select(literal(1))
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.organization_id == session.org_id,
            Membership.user_id == session.user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .exists()
    )


def _assigned(model, user_id):
    return and_(model.owner_type == "user", model.owner_id == user_id)


def _collaborator_filter(session, kind, model):
    if kind == "intended_parent":
        return false()
    subject = getattr(RecordCollaborator, f"{kind}_id")
    return (
        select(literal(1))
        .select_from(RecordCollaborator)
        .join(Membership, Membership.id == RecordCollaborator.membership_id)
        .where(
            RecordCollaborator.organization_id == session.org_id,
            RecordCollaborator.user_id == session.user_id,
            subject == model.id,
            Membership.organization_id == session.org_id,
            Membership.user_id == session.user_id,
            Membership.is_active.is_(True),
        )
        .exists()
    )


def _stage_filter(session, kind, model, rule):
    if rule.phase == "all" and not rule.stage_ids:
        return true()
    current = PipelineStage.__table__.alias("scope_current")
    effective = PipelineStage.__table__.alias("scope_effective")
    pipeline = Pipeline.__table__.alias("scope_pipeline")
    if rule.phase == "all":
        return (
            select(literal(1))
            .select_from(current.join(pipeline, pipeline.c.id == current.c.pipeline_id))
            .where(
                current.c.id == model.stage_id,
                current.c.id.in_(rule.stage_ids),
                current.c.is_active.is_(True),
                pipeline.c.organization_id == session.org_id,
            )
            .exists()
        )
    effective_id = model.stage_id
    if kind in {"surrogate", "donor"}:
        from app.db.models import DonorStatusHistory, SurrogateStatusHistory

        history_model = SurrogateStatusHistory if kind == "surrogate" else DonorStatusHistory
        history = history_model.__table__.alias("scope_history")
        prior = PipelineStage.__table__.alias("scope_history_prior")
        following = PipelineStage.__table__.alias("scope_history_following")
        before_id = history.c.from_stage_id if kind == "surrogate" else history.c.old_stage_id
        after_id = history.c.to_stage_id if kind == "surrogate" else history.c.new_stage_id
        known_stage = case(
            (
                and_(
                    following.c.stage_type.notin_(["paused", "terminal"]),
                    following.c.pipeline_id == current.c.pipeline_id,
                ),
                following.c.id,
            ),
            (
                and_(
                    prior.c.stage_type.notin_(["paused", "terminal"]),
                    prior.c.pipeline_id == current.c.pipeline_id,
                ),
                prior.c.id,
            ),
        )
        historical_stage = (
            select(known_stage)
            .select_from(
                history.outerjoin(prior, prior.c.id == before_id).outerjoin(
                    following, following.c.id == after_id
                )
            )
            .where(
                history.c.organization_id == session.org_id,
                getattr(history.c, f"{kind}_id") == model.id,
                known_stage.isnot(None),
            )
            .order_by(history.c.recorded_at.desc(), history.c.id.desc())
            .limit(1)
            .correlate_except(history, prior, following)
            .scalar_subquery()
        )
        effective_id = case(
            (
                current.c.stage_type == "paused",
                func.coalesce(model.paused_from_stage_id, historical_stage),
            ),
            (current.c.stage_type == "terminal", historical_stage),
            else_=model.stage_id,
        )
    source = current.outerjoin(effective, effective.c.id == effective_id).join(
        pipeline, pipeline.c.id == current.c.pipeline_id
    )
    conditions = [
        current.c.id == model.stage_id,
        current.c.is_active.is_(True),
        or_(current.c.pipeline_id == effective.c.pipeline_id, effective.c.id.is_(None)),
        pipeline.c.organization_id == session.org_id,
        or_(effective.c.is_active.is_(True), effective.c.id.is_(None)),
    ]
    if rule.stage_ids:
        conditions.append(current.c.id.in_(rule.stage_ids))
    conditions.append(
        or_(effective.c.stage_type.notin_(["paused", "terminal"]), effective.c.id.is_(None))
    )
    if rule.phase != "all":
        gate = PipelineStage.__table__.alias("scope_approval_gate")
        gate_keys = {
            key
            for entity in RECORDS[kind][2]
            for key, definition in PROTECTED_SYSTEM_STAGES_BY_ENTITY.get(entity, {}).items()
            if definition.system_role == "approval_gate"
        }
        # Older donor pipelines have phase categories before an approval gate is installed.
        if gate_keys:
            gate_order = (
                select(gate.c.order)
                .where(
                    gate.c.pipeline_id == effective.c.pipeline_id,
                    gate.c.stage_key.in_(gate_keys),
                    gate.c.is_active.is_(True),
                )
                .limit(1)
                .scalar_subquery()
            )
            post = effective.c.order >= gate_order
            pre = effective.c.order < gate_order
        else:
            post = effective.c.stage_type == "post_approval"
            pre = effective.c.stage_type == "intake"
        phase = post if rule.phase == "post_approval" else pre
        if kind in {"surrogate", "donor"}:
            reviewed_phase = (
                select(literal(1))
                .select_from(RecordScopeMigrationReview)
                .where(
                    RecordScopeMigrationReview.organization_id == session.org_id,
                    getattr(RecordScopeMigrationReview, f"{kind}_id") == model.id,
                    RecordScopeMigrationReview.reviewed_stage_id == model.stage_id,
                    RecordScopeMigrationReview.resolved_phase == rule.phase,
                    RecordScopeMigrationReview.evidence_reference.isnot(None),
                )
                .exists()
            )
            phase = or_(phase, and_(effective.c.id.is_(None), reviewed_phase))
        conditions.append(phase)
    return select(literal(1)).select_from(source).where(*conditions).exists()


def record_phase(db: Session, org_id: UUID, kind: str, record) -> str | None:
    """Resolve the same canonical approval phase used by scoped lists."""
    if kind not in RECORDS or record.organization_id != org_id:
        return None
    model = RECORDS[kind][0]
    context = SimpleNamespace(org_id=org_id)
    row = (
        db.query(
            _stage_filter(
                context, kind, model, RecordScopeRule(assignment="all", phase="pre_approval")
            ),
            _stage_filter(
                context, kind, model, RecordScopeRule(assignment="all", phase="post_approval")
            ),
        )
        .filter(model.organization_id == org_id, model.id == record.id)
        .first()
    )
    if row and row[0]:
        return "pre_approval"
    if row and row[1]:
        return "post_approval"
    return None


def _rule_filter(session, kind, model, rule):
    if rule.assignment == "none":
        return false()
    assignment = _assigned(model, session.user_id) if rule.assignment == "assigned" else true()
    return and_(assignment, _stage_filter(session, kind, model, rule))


def _routes(db, session, kind, model):
    module = RECORDS[kind][1]
    rule = get_role_scope(db, session.org_id, session.role, module)
    routes = [("role", _rule_filter(session, kind, model, rule))]
    additions = (
        db.query(UserRecordScopeAddition)
        .join(Membership, Membership.id == UserRecordScopeAddition.membership_id)
        .filter(
            UserRecordScopeAddition.organization_id == session.org_id,
            UserRecordScopeAddition.user_id == session.user_id,
            UserRecordScopeAddition.module == module,
            Membership.organization_id == session.org_id,
            Membership.user_id == session.user_id,
            Membership.is_active.is_(True),
        )
        .all()
    )
    for addition in additions:
        rule = RecordScopeRule.model_validate(addition, from_attributes=True)
        routes.append((f"individual:{addition.id}", _rule_filter(session, kind, model, rule)))
    routes.append(("intake_collaborator", _collaborator_filter(session, kind, model)))
    return routes


def _boundary_filter(session, model, *, allow_archived=False):
    boundary = and_(model.organization_id == session.org_id, _active_member_filter(session))
    if not allow_archived and _role(session.role) not in PROTECTED_ROLES:
        boundary = and_(boundary, model.is_archived.is_(False))
    return boundary


def build_visibility_filter(
    db: Session, session, kind: str, *, model=None, personal_only=False, allow_archived=False
):
    if kind not in RECORDS or not session.user_id:
        return false()
    model = model if model is not None else RECORDS[kind][0]
    model = getattr(model, "c", model)
    if not _enabled(db, session.org_id):
        if kind == "surrogate":
            from app.core.surrogate_access import build_surrogate_visibility_filter

            legacy = build_surrogate_visibility_filter(
                db, session.org_id, session.role, session.user_id, surrogate_model=model
            )
        else:
            legacy = true()
        return and_(
            model.organization_id == session.org_id,
            legacy,
            _assigned(model, session.user_id) if personal_only else true(),
        )
    routes = _routes(db, session, kind, model)
    result = and_(
        _boundary_filter(session, model, allow_archived=allow_archived),
        or_(*(condition for _, condition in routes)),
    )
    if personal_only:
        result = and_(
            result,
            or_(_assigned(model, session.user_id), _collaborator_filter(session, kind, model)),
        )
    return result


def can_access_record(
    db: Session, session, kind: str, record, *, personal_only=False, allow_archived=False
) -> bool:
    if kind not in RECORDS or record.organization_id != session.org_id:
        return False
    model = RECORDS[kind][0]
    return (
        db.query(model.id)
        .filter(
            model.id == record.id,
            build_visibility_filter(
                db, session, kind, personal_only=personal_only, allow_archived=allow_archived
            ),
        )
        .first()
        is not None
    )


def explain_record_access(
    db: Session, session, kind: str, record, *, personal_only=False, allow_archived=False
) -> RecordAccessExplanation:
    if kind not in RECORDS or record.organization_id != session.org_id:
        return RecordAccessExplanation(allowed=False, reason="Record not found")
    if not _enabled(db, session.org_id):
        allowed = can_access_record(
            db, session, kind, record, personal_only=personal_only, allow_archived=allow_archived
        )
        return RecordAccessExplanation(
            allowed=allowed,
            sources=["legacy"] if allowed else [],
            reason=None if allowed else "Outside record scope",
        )
    model = RECORDS[kind][0]
    routes = _routes(db, session, kind, model)
    boundary = _boundary_filter(session, model, allow_archived=allow_archived)
    if personal_only:
        boundary = and_(
            boundary,
            or_(_assigned(model, session.user_id), _collaborator_filter(session, kind, model)),
        )
    row = db.execute(
        select(*(condition.label(f"route_{index}") for index, (_, condition) in enumerate(routes)))
        .select_from(model)
        .where(model.id == record.id, boundary)
    ).first()
    sources = (
        [name for (name, _), granted in zip(routes, row, strict=True) if granted] if row else []
    )
    return RecordAccessExplanation(
        allowed=bool(sources), sources=sources, reason=None if sources else "Outside record scope"
    )


def _require_admin(session):
    if _role(session.role) not in PROTECTED_ROLES:
        raise PermissionError("Only admins and developers can configure record scope")


def _refresh_actor(db, session):
    """Recheck authority after acquiring the organization configuration lock."""
    member = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == session.org_id,
            Membership.user_id == session.user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .populate_existing()
        .first()
    )
    if member is None:
        raise PermissionError("Active organization membership required")
    session.role = Role(member.role)


def _validate_rule(db, org_id, module, rule):
    if module not in MODULE_KINDS:
        raise ValueError("Unknown record module")
    if module == "intended_parents" and rule.phase != "all":
        raise ValueError("Intended parent scope has no applicant approval phase")
    if rule.stage_ids:
        entities = RECORDS[MODULE_KINDS[module]][2]
        found = (
            db.query(PipelineStage.id)
            .join(Pipeline)
            .filter(
                Pipeline.organization_id == org_id,
                Pipeline.entity_type.in_(entities),
                PipelineStage.id.in_(rule.stage_ids),
                PipelineStage.is_active.is_(True),
            )
            .all()
        )
        if {row.id for row in found} != set(rule.stage_ids):
            raise ValueError("Stages must belong to this organization's record module")


def _audit(db, session, target_type, target_id, operation, details=None):
    from app.services import audit_service

    audit_service.log_event(
        db,
        session.org_id,
        AuditEventType.SETTINGS_ORG_UPDATED,
        actor_user_id=session.user_id,
        target_type=target_type,
        target_id=target_id,
        details={"operation": operation, **(details or {})},
    )


def save_role_scope(db, session, role, module, rule, *, commit=True):
    _lock(db, session.org_id)
    _refresh_actor(db, session)
    _require_admin(session)
    if _role(role) in PROTECTED_ROLES:
        raise PermissionError("Admin and Dev record scope is protected")
    if not Role.has_value(_role(role)):
        raise ValueError("Unknown role")
    _validate_rule(db, session.org_id, module, rule)
    row = (
        db.query(RoleRecordScope)
        .filter_by(organization_id=session.org_id, role=_role(role), module=module)
        .first()
    )
    if row is None:
        row = RoleRecordScope(organization_id=session.org_id, role=_role(role), module=module)
        db.add(row)
    row.assignment, row.phase = rule.assignment, rule.phase
    row.stage_ids = [str(value) for value in rule.stage_ids]
    db.flush()
    _audit(db, session, "role_record_scope", row.id, "set", {"role": _role(role), "module": module})
    if commit:
        db.commit()
    return rule


def list_scope_additions(db, org_id, user_id):
    _member(db, org_id, user_id, include_inactive=True)
    return (
        db.query(UserRecordScopeAddition)
        .filter_by(organization_id=org_id, user_id=user_id)
        .order_by(UserRecordScopeAddition.created_at)
        .all()
    )


def add_scope_addition(db, session, user_id, data):
    _lock(db, session.org_id)
    _refresh_actor(db, session)
    _require_admin(session)
    member = _member(db, session.org_id, user_id)
    _validate_rule(db, session.org_id, data.module, data)
    row = UserRecordScopeAddition(
        organization_id=session.org_id,
        membership_id=member.id,
        user_id=user_id,
        module=data.module,
        assignment=data.assignment,
        phase=data.phase,
        stage_ids=[str(value) for value in data.stage_ids],
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        session,
        "user_record_scope",
        row.id,
        "add",
        {"user_id": str(user_id), "module": data.module},
    )
    db.commit()
    return row


def remove_scope_addition(db, session, user_id, addition_id):
    _lock(db, session.org_id)
    _refresh_actor(db, session)
    _require_admin(session)
    _member(db, session.org_id, user_id, include_inactive=True)
    row = (
        db.query(UserRecordScopeAddition)
        .filter_by(organization_id=session.org_id, user_id=user_id, id=addition_id)
        .first()
    )
    if row is None:
        raise LookupError("Scope addition not found")
    _audit(db, session, "user_record_scope", row.id, "remove", {"user_id": str(user_id)})
    db.delete(row)
    db.commit()


def _collaboration_record(db, session, kind, record_id, *, manage=False):
    from app.services.record_access_service import get_record_with_access

    if kind not in {"surrogate", "donor"}:
        raise ValueError("Intake collaborators are supported for surrogates and donors")
    if manage and _role(session.role) not in {*PROTECTED_ROLES, Role.CASE_MANAGER.value}:
        raise PermissionError("Only case managers, admins and developers can manage collaborators")
    return get_record_with_access(db, session, kind, record_id, allow_archived=True)


def list_collaborators(db, session, kind, record_id):
    _collaboration_record(db, session, kind, record_id)
    return (
        db.query(RecordCollaborator)
        .filter(
            RecordCollaborator.organization_id == session.org_id,
            getattr(RecordCollaborator, f"{kind}_id") == record_id,
        )
        .order_by(RecordCollaborator.created_at)
        .all()
    )


def _grant_collaborator(db, org_id, kind, record, member, actor_user_id):
    if record.organization_id != org_id or member.organization_id != org_id:
        raise LookupError("Record or member not found")
    field = f"{kind}_id"
    values = dict(
        organization_id=org_id,
        membership_id=member.id,
        user_id=member.user_id,
        granted_by_user_id=actor_user_id,
        **{field: record.id},
    )
    db.execute(insert(RecordCollaborator).values(**values).on_conflict_do_nothing())
    db.flush()
    return (
        db.query(RecordCollaborator)
        .filter_by(organization_id=org_id, user_id=member.user_id, **{field: record.id})
        .one()
    )


def grant_collaborator(db, session, kind, record_id, user_id):
    _lock(db, session.org_id)
    _refresh_actor(db, session)
    record = _collaboration_record(db, session, kind, record_id, manage=True)
    member = _member(db, session.org_id, user_id)
    if member.role != Role.INTAKE_SPECIALIST.value:
        raise ValueError("Intake collaborators must have the Intake Specialist role")
    row = _grant_collaborator(db, session.org_id, kind, record, member, session.user_id)
    _audit(
        db,
        session,
        "record_collaborator",
        row.id,
        "grant",
        {"user_id": str(user_id), "kind": kind, "record_id": str(record_id)},
    )
    db.commit()
    return row


def remove_collaborator(db, session, kind, record_id, user_id):
    _lock(db, session.org_id)
    _refresh_actor(db, session)
    _collaboration_record(db, session, kind, record_id, manage=True)
    row = (
        db.query(RecordCollaborator)
        .filter(
            RecordCollaborator.organization_id == session.org_id,
            RecordCollaborator.user_id == user_id,
            getattr(RecordCollaborator, f"{kind}_id") == record_id,
        )
        .first()
    )
    if row is not None:
        _audit(db, session, "record_collaborator", row.id, "remove", {"user_id": str(user_id)})
        db.delete(row)
        db.commit()


def retain_intake_owner_at_handoff(db, org_id, kind, record, intake_user_id, *, actor_user_id=None):
    """Retain only the actual Intake owner supplied by the handoff, without committing."""
    if not _enabled(db, org_id) or not intake_user_id or kind not in {"surrogate", "donor"}:
        return None
    _lock(db, org_id)
    if record.organization_id != org_id:
        raise LookupError("Record not found")
    try:
        member = _member(db, org_id, intake_user_id)
    except LookupError:
        return None
    if member.role != Role.INTAKE_SPECIALIST.value:
        return None
    row = _grant_collaborator(db, org_id, kind, record, member, actor_user_id)
    _audit(
        db,
        SimpleNamespace(org_id=org_id, user_id=actor_user_id),
        "record_collaborator",
        row.id,
        "retain_at_handoff",
        {"user_id": str(intake_user_id), "kind": kind, "record_id": str(record.id)},
    )
    return row


def _lock(db, org_id):
    from app.services import permission_policy_service

    permission_policy_service.lock_configuration(db, org_id)


def explain_member_access(db, org_id, data):
    from app.core.policies import POLICIES
    from app.services import permission_service

    member = _member(db, org_id, data.user_id)
    session = SimpleNamespace(org_id=org_id, user_id=data.user_id, role=member.role)
    model, module, _ = RECORDS[data.kind]
    record = db.query(model).filter_by(organization_id=org_id, id=data.record_id).first()
    if record is None:
        raise LookupError("Record not found")
    permission = POLICIES[module].default
    if not permission_service.check_permission(
        db, org_id, data.user_id, member.role, permission.value
    ):
        return RecordAccessExplanation(
            allowed=False, reason=f"Missing permission: {permission.value}"
        )
    return explain_record_access(db, session, data.kind, record, personal_only=data.personal_only)


def apply_member_access_review(db, org_id, user_id, *, retain_additions, retain_collaborators):
    """Apply explicitly reviewed record grants during a role change, without committing."""
    _lock(db, org_id)
    if not retain_additions:
        db.query(UserRecordScopeAddition).filter_by(organization_id=org_id, user_id=user_id).delete(
            synchronize_session="fetch"
        )
    if not retain_collaborators:
        db.query(RecordCollaborator).filter_by(organization_id=org_id, user_id=user_id).delete(
            synchronize_session="fetch"
        )
    db.flush()


def _fingerprint(value):
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _record_fingerprint(kind, record):
    return _fingerprint(
        {
            "kind": kind,
            "id": str(record.id),
            "stage_id": str(record.stage_id),
            "paused_from_stage_id": str(getattr(record, "paused_from_stage_id", None)),
            "owner_type": record.owner_type,
            "owner_id": str(record.owner_id),
        }
    )


def _handoff_candidates(db, org_id):
    candidates = []
    session = SimpleNamespace(org_id=org_id, user_id=None, role="admin")
    for kind in ("surrogate", "donor"):
        model = RECORDS[kind][0]
        post = _stage_filter(
            session, kind, model, RecordScopeRule(assignment="all", phase="post_approval")
        )
        pre = _stage_filter(
            session, kind, model, RecordScopeRule(assignment="all", phase="pre_approval")
        )
        rows = (
            db.query(model, post.label("post"), pre.label("pre"))
            .filter(
                model.organization_id == org_id,
                or_(post, and_(~pre, ~post)),
            )
            .order_by(model.id)
            .all()
        )
        for record, is_post, is_pre in rows:
            candidates.append(
                {
                    "kind": kind,
                    "record_id": str(record.id),
                    "record_number": getattr(record, f"{kind}_number"),
                    "fingerprint": _record_fingerprint(kind, record),
                    "phase_requires_review": not is_post and not is_pre,
                    "owner_user_id": str(record.owner_id) if record.owner_type == "user" else None,
                }
            )
    return candidates


def _legacy_pool_rows(db, org_id):
    from app.db.models import IntakePoolAccessGrant

    rows = (
        db.query(IntakePoolAccessGrant)
        .filter_by(organization_id=org_id)
        .order_by(IntakePoolAccessGrant.id)
        .all()
    )
    result = []
    for row in rows:
        record_ids = [
            str(item.id)
            for item in db.query(Surrogate.id)
            .filter(
                Surrogate.organization_id == org_id,
                Surrogate.owner_type == "user",
                Surrogate.owner_id == row.source_user_id,
            )
            .order_by(Surrogate.id)
            .all()
        ]
        data = {
            "id": str(row.id),
            "source_user_id": str(row.source_user_id),
            "grantee_user_id": str(row.grantee_user_id),
            "current_record_ids": record_ids,
            "choices": ["remove", "replace_with_scope_addition"],
        }
        result.append({**data, "fingerprint": _fingerprint(data)})
    return result


def get_policy_scope_snapshot(db, org_id) -> dict:
    """Deterministic activation input; unresolved legacy grants and handoffs block activation."""
    from app.db.models.record_access import RecordScopeMigrationReview

    roles = (
        db.query(RoleRecordScope)
        .filter_by(organization_id=org_id)
        .order_by(RoleRecordScope.role, RoleRecordScope.module)
        .all()
    )
    additions = (
        db.query(UserRecordScopeAddition)
        .filter_by(organization_id=org_id)
        .order_by(UserRecordScopeAddition.id)
        .all()
    )
    collaborators = (
        db.query(RecordCollaborator)
        .filter_by(organization_id=org_id)
        .order_by(RecordCollaborator.id)
        .all()
    )
    record_numbers = {}
    for kind in ("surrogate", "donor"):
        model = RECORDS[kind][0]
        record_ids = {getattr(row, f"{kind}_id") for row in collaborators}
        record_numbers.update(
            dict(
                db.query(model.id, getattr(model, f"{kind}_number"))
                .filter(
                    model.organization_id == org_id,
                    model.id.in_(record_ids - {None}),
                )
                .all()
            )
        )
    reviews = (
        db.query(RecordScopeMigrationReview)
        .filter_by(organization_id=org_id)
        .order_by(RecordScopeMigrationReview.id)
        .all()
    )
    review_map = {
        (str(row.surrogate_id) if row.surrogate_id else str(row.donor_id)): row for row in reviews
    }
    candidates = _handoff_candidates(db, org_id)
    unresolved = []
    for candidate in candidates:
        review = review_map.get(candidate["record_id"])
        resolved = review is not None and review.record_fingerprint == candidate["fingerprint"]
        if candidate["phase_requires_review"]:
            resolved = False
        if resolved and review.decision == "retain_verified_owner":
            resolved = any(
                row.user_id == review.retained_user_id
                and str(getattr(row, f"{candidate['kind']}_id")) == candidate["record_id"]
                for row in collaborators
            )
        candidate["resolved"] = bool(resolved)
        if not resolved:
            unresolved.append(candidate)
    missing_gates = []
    for pipeline in (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == org_id,
            Pipeline.entity_type.in_(["surrogate", "egg_donor", "sperm_donor"]),
        )
        .order_by(Pipeline.id)
        .all()
    ):
        gate_keys = [
            key
            for key, definition in PROTECTED_SYSTEM_STAGES_BY_ENTITY.get(
                pipeline.entity_type, {}
            ).items()
            if definition.system_role == "approval_gate"
        ]
        found = (
            db.query(PipelineStage.id)
            .filter(
                PipelineStage.pipeline_id == pipeline.id,
                PipelineStage.stage_key.in_(gate_keys),
                PipelineStage.is_active.is_(True),
            )
            .first()
        )
        if found is None:
            missing_gates.append(str(pipeline.id))
    pools = _legacy_pool_rows(db, org_id)
    scope_differences, record_state_digest = _scope_count_preview(db, org_id)
    return {
        "ready": not unresolved and not pools and not missing_gates,
        "default_role_scopes": {
            role.value: {
                module: default_rule(role, module).model_dump(mode="json")
                for module in MODULE_KINDS
            }
            for role in Role
        },
        "role_scopes": [
            {
                "role": row.role,
                "module": row.module,
                "assignment": row.assignment,
                "phase": row.phase,
                "stage_ids": sorted(row.stage_ids),
            }
            for row in roles
        ],
        "individual_scopes": [
            {
                "id": str(row.id),
                "user_id": str(row.user_id),
                "module": row.module,
                "assignment": row.assignment,
                "phase": row.phase,
                "stage_ids": sorted(row.stage_ids),
            }
            for row in additions
        ],
        "collaborators": [
            {
                "id": str(row.id),
                "record_number": record_numbers.get(row.surrogate_id or row.donor_id),
                "user_id": str(row.user_id),
                "surrogate_id": str(row.surrogate_id) if row.surrogate_id else None,
                "donor_id": str(row.donor_id) if row.donor_id else None,
            }
            for row in collaborators
        ],
        "handoff_candidates": candidates,
        "unresolved_handoffs": unresolved,
        "missing_approval_gate_pipeline_ids": missing_gates,
        "legacy_pool_grants": pools,
        "member_record_scope_differences": scope_differences,
        "record_state_digest": record_state_digest,
        "resolutions": [
            {
                "id": str(row.id),
                "record_id": str(row.surrogate_id or row.donor_id),
                "decision": row.decision,
                "retained_user_id": str(row.retained_user_id) if row.retained_user_id else None,
                "record_fingerprint": row.record_fingerprint,
                "reviewed_by_user_id": str(row.reviewed_by_user_id),
                "evidence_reference": row.evidence_reference,
                "resolved_phase": row.resolved_phase,
                "reviewed_stage_id": str(row.reviewed_stage_id) if row.reviewed_stage_id else None,
            }
            for row in reviews
        ],
    }


def resolve_handoff_migration(db, session, kind, record_id, data):
    from app.db.models.record_access import RecordScopeMigrationReview

    _lock(db, session.org_id)
    _refresh_actor(db, session)
    _require_admin(session)
    if kind not in {"surrogate", "donor"}:
        raise ValueError("Only applicant handoffs require review")
    model = RECORDS[kind][0]
    record = (
        db.query(model)
        .filter_by(organization_id=session.org_id, id=record_id)
        .with_for_update()
        .first()
    )
    if record is None:
        raise LookupError("Record not found")
    fingerprint = _record_fingerprint(kind, record)
    _validate_rule(
        db,
        session.org_id,
        RECORDS[kind][1],
        RecordScopeRule(assignment="all", stage_ids=[record.stage_id]),
    )
    if data.expected_fingerprint != fingerprint:
        raise ValueError("Record changed; refresh the migration review")
    if data.resolved_phase and (not data.evidence_reference or not data.evidence_reference.strip()):
        raise ValueError("Phase resolution requires an evidence reference")
    if data.decision == "retain_verified_owner":
        if (
            not data.intake_user_id
            or not data.evidence_reference
            or not data.evidence_reference.strip()
        ):
            raise ValueError("A verified Intake owner and evidence reference are required")
        member = _member(db, session.org_id, data.intake_user_id)
        if member.role != Role.INTAKE_SPECIALIST.value:
            raise ValueError("Verified owner must be an active Intake Specialist")
        _grant_collaborator(db, session.org_id, kind, record, member, session.user_id)
    elif data.intake_user_id is not None:
        raise ValueError("No verified owner review cannot specify an Intake owner")
    field = f"{kind}_id"
    row = (
        db.query(RecordScopeMigrationReview)
        .filter_by(organization_id=session.org_id, **{field: record_id})
        .first()
    )
    if row is None:
        row = RecordScopeMigrationReview(organization_id=session.org_id, **{field: record_id})
        db.add(row)
    row.reviewed_by_user_id, row.retained_user_id = session.user_id, data.intake_user_id
    row.decision, row.evidence_reference = data.decision, data.evidence_reference
    row.resolved_phase = data.resolved_phase
    row.reviewed_stage_id = record.stage_id if data.resolved_phase else None
    row.record_fingerprint = fingerprint
    from datetime import UTC, datetime

    row.reviewed_at = datetime.now(UTC)
    db.flush()
    _audit(
        db,
        session,
        "record_scope_migration_review",
        row.id,
        data.decision,
        {
            "kind": kind,
            "record_id": str(record_id),
            "retained_user_id": str(data.intake_user_id) if data.intake_user_id else None,
            "resolved_phase": data.resolved_phase,
        },
    )
    db.commit()
    return {"record_id": str(record_id), "decision": row.decision, "resolved": True}


def resolve_legacy_pool_grant(db, session, grant_id, data):
    from app.db.models import IntakePoolAccessGrant

    _lock(db, session.org_id)
    _refresh_actor(db, session)
    _require_admin(session)
    grant = (
        db.query(IntakePoolAccessGrant)
        .filter_by(organization_id=session.org_id, id=grant_id)
        .first()
    )
    if grant is None:
        raise LookupError("Legacy pool grant not found")
    current = next(
        row for row in _legacy_pool_rows(db, session.org_id) if row["id"] == str(grant_id)
    )
    if data.expected_fingerprint != current["fingerprint"]:
        raise ValueError("Pool ownership changed; refresh the migration review")
    if data.decision == "replace_with_scope_addition":
        if data.replacement is None or data.replacement.module != "surrogates":
            raise ValueError("A surrogate scope addition is required")
        member = _member(db, session.org_id, grant.grantee_user_id)
        _validate_rule(db, session.org_id, "surrogates", data.replacement)
        db.add(
            UserRecordScopeAddition(
                organization_id=session.org_id,
                membership_id=member.id,
                user_id=member.user_id,
                module="surrogates",
                assignment=data.replacement.assignment,
                phase=data.replacement.phase,
                stage_ids=[str(value) for value in data.replacement.stage_ids],
            )
        )
    elif data.replacement is not None:
        raise ValueError("Removal cannot contain a replacement scope")
    _audit(
        db,
        session,
        "legacy_intake_pool_grant",
        grant.id,
        data.decision,
        {
            "grantee_user_id": str(grant.grantee_user_id),
            "source_user_id": str(grant.source_user_id),
            "replacement": data.replacement.model_dump(mode="json") if data.replacement else None,
        },
    )
    db.delete(grant)
    db.commit()
    return {"resolved": True}


def _scope_count_preview(db, org_id):
    """Exact row-scope counts; action-key differences are reported by permission policy."""
    from app.core.surrogate_access import _build_legacy_surrogate_visibility_filter

    active = _enabled(db, org_id)
    members = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .order_by(Membership.id)
        .all()
    )
    differences = []
    record_state = []
    stage_state = (
        db.query(
            PipelineStage.id,
            PipelineStage.pipeline_id,
            PipelineStage.stage_key,
            PipelineStage.stage_type,
            PipelineStage.order,
            PipelineStage.is_active,
        )
        .join(Pipeline)
        .filter(
            Pipeline.organization_id == org_id,
            Pipeline.entity_type.in_(
                tuple(entity for _, _, entities in RECORDS.values() for entity in entities)
            ),
        )
        .order_by(PipelineStage.id)
        .all()
    )
    record_state.append(("stages", [tuple(row) for row in stage_state]))
    for kind, (model, module, _) in RECORDS.items():
        columns = [model.id, model.stage_id, model.owner_type, model.owner_id, model.is_archived]
        if kind in {"surrogate", "donor"}:
            columns.append(model.paused_from_stage_id)
        rows = db.query(*columns).filter(model.organization_id == org_id).order_by(model.id).all()
        record_state.append((kind, [tuple(row) for row in rows]))
        for member in members:
            session = SimpleNamespace(org_id=org_id, user_id=member.user_id, role=member.role)
            boundary = _boundary_filter(session, model)
            proposed = func.coalesce(
                or_(*(condition for _, condition in _routes(db, session, kind, model))), false()
            )
            if active:
                current = proposed
            elif kind == "surrogate":
                current = func.coalesce(
                    _build_legacy_surrogate_visibility_filter(
                        member.role, member.user_id, surrogate_model=model
                    ),
                    false(),
                )
            else:
                current = true()
            gained, lost = and_(proposed, ~current), and_(current, ~proposed)
            counts = (
                db.query(
                    func.count().filter(current),
                    func.count().filter(proposed),
                    func.count().filter(gained),
                    func.count().filter(lost),
                )
                .select_from(model)
                .filter(boundary)
                .one()
            )
            gained_ids = (
                [
                    str(row.id)
                    for row in db.query(model.id)
                    .filter(boundary, gained)
                    .order_by(model.id)
                    .limit(10)
                ]
                if counts[2]
                else []
            )
            lost_ids = (
                [
                    str(row.id)
                    for row in db.query(model.id)
                    .filter(boundary, lost)
                    .order_by(model.id)
                    .limit(10)
                ]
                if counts[3]
                else []
            )
            differences.append(
                {
                    "membership_id": str(member.id),
                    "user_id": str(member.user_id),
                    "role": member.role,
                    "module": module,
                    "scope_only": True,
                    "current_count": counts[0],
                    "proposed_count": counts[1],
                    "gained_count": counts[2],
                    "lost_count": counts[3],
                    "gained_record_id_samples": gained_ids,
                    "lost_record_id_samples": lost_ids,
                }
            )
    return differences, _fingerprint(record_state)


def build_linked_visibility_filter(db, session, resource, *, permissions=None):
    """Every present record subject must be visible, including both parties of a match."""
    from app.core.policies import POLICIES
    from app.db.models import Match
    from app.services import permission_service

    resource = getattr(resource, "c", resource)
    if not _enabled(db, session.org_id):
        return true()
    if permissions is None:
        permissions = permission_service.get_effective_permissions(
            db, session.org_id, session.user_id, _role(session.role)
        )
    conditions = [resource.organization_id == session.org_id]
    for kind, (model, module, _) in RECORDS.items():
        subject_id = getattr(resource, f"{kind}_id", None)
        if subject_id is None:
            continue
        if POLICIES[module].default.value not in permissions:
            conditions.append(subject_id.is_(None))
            continue
        allowed = select(model.id).where(build_visibility_filter(db, session, kind))
        conditions.append(or_(subject_id.is_(None), subject_id.in_(allowed)))
    match_id = getattr(resource, "match_id", None)
    if match_id is not None:
        if POLICIES["matches"].default.value not in permissions:
            conditions.append(match_id.is_(None))
        else:
            visible_matches = select(Match.id).where(
                build_linked_visibility_filter(db, session, Match, permissions=permissions)
            )
            conditions.append(or_(match_id.is_(None), match_id.in_(visible_matches)))
    return and_(*conditions)


def collaborator_options(db, session, kind, record_id):
    _collaboration_record(db, session, kind, record_id, manage=True)
    return [
        {"user_id": user_id, "display_name": name}
        for user_id, name in db.query(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == session.org_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
            Membership.role == Role.INTAKE_SPECIALIST.value,
        )
        .order_by(User.display_name, User.id)
    ]


def collaborator_details(db, session, kind, record_id):
    from app.schemas.record_scope import CollaboratorRead

    rows = list_collaborators(db, session, kind, record_id)
    names = dict(
        db.query(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == session.org_id, User.id.in_([row.user_id for row in rows])
        )
        .all()
    )
    return [
        CollaboratorRead.model_validate(row).model_copy(
            update={"display_name": names.get(row.user_id)}
        )
        for row in rows
    ]


def require_mutation_scope(db, session, kind, record_id):
    """Lock the subject before claim or reassignment changes its visibility."""
    if not _enabled(db, session.org_id):
        return
    from fastapi import HTTPException

    model = RECORDS[kind][0]
    record = (
        db.query(model)
        .filter(model.organization_id == session.org_id, model.id == record_id)
        .with_for_update()
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"{kind.replace('_', ' ').title()} not found")
    if not can_access_record(db, session, kind, record):
        raise HTTPException(
            status_code=403, detail=f"You don't have access to this {kind.replace('_', ' ')}"
        )
