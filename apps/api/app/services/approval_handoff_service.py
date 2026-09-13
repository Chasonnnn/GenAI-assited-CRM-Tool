"""Canonical approval boundaries and atomic retained Intake access."""

from app.db.models import Donor, Membership, Pipeline, PipelineStage, Queue, User
from app.schemas.auth import UserSession
from app.services import permission_policy_service, permission_service, record_scope_service


def crosses_approval(db, record, target_stage) -> bool:
    if target_stage is None:
        return False
    current = (
        db.query(PipelineStage)
        .join(Pipeline)
        .filter(
            PipelineStage.id == record.stage_id,
            Pipeline.organization_id == record.organization_id,
        )
        .first()
    )
    if current is None or current.pipeline_id != target_stage.pipeline_id:
        return False
    gate = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == current.pipeline_id,
            PipelineStage.stage_key == "approved",
            PipelineStage.is_active.is_(True),
        )
        .first()
    )
    if gate is None:
        return False
    if target_stage.stage_type in {"paused", "terminal"} or target_stage.order < gate.order:
        return False
    kind = "donor" if isinstance(record, Donor) else "surrogate"
    phase = record_scope_service.record_phase(db, record.organization_id, kind, record)
    # Unknown historical phase cannot authorize entering an approved stage.
    return phase != "post_approval"


def retain_at_approval(db, *, record, kind, target_stage, actor_user_id=None) -> None:
    if not permission_policy_service.is_enabled(db, record.organization_id):
        return
    if not crosses_approval(db, record, target_stage):
        return
    permission_policy_service.lock_configuration(db, record.organization_id)
    owner = None
    if record.owner_type == "user":
        owner = (
            db.query(Membership)
            .filter_by(
                organization_id=record.organization_id, user_id=record.owner_id, is_active=True
            )
            .first()
        )
        record_scope_service.retain_intake_owner_at_handoff(
            db,
            record.organization_id,
            kind,
            record,
            record.owner_id,
            actor_user_id=actor_user_id,
        )
    if owner and owner.role in {"case_manager", "admin", "developer"}:
        return
    from app.services import queue_service

    if kind == "surrogate":
        pool = queue_service.get_or_create_surrogate_pool_queue(db, record.organization_id)
    else:
        pool = (
            db.query(Queue)
            .filter_by(organization_id=record.organization_id, name="Donor Pool")
            .first()
        )
        if pool is None:
            pool = queue_service.create_queue(db, record.organization_id, "Donor Pool")
        pool.is_active = True
    record.owner_type = "queue"
    record.owner_id = pool.id


def authorize_stage_change(
    db, *, record, kind, target_stage, user_id, execution_permissions=None
) -> bool:
    if not permission_policy_service.is_enabled(db, record.organization_id):
        return False
    permission_policy_service.lock_configuration(db, record.organization_id)
    if execution_permissions is None:
        member = (
            db.query(Membership)
            .join(User, User.id == Membership.user_id)
            .filter(
                Membership.organization_id == record.organization_id,
                Membership.user_id == user_id,
                Membership.is_active.is_(True),
                User.is_active.is_(True),
            )
            .populate_existing()
            .first()
        )
        if member is None:
            raise ValueError("Active organization membership required")
        session = UserSession(
            org_id=record.organization_id,
            user_id=user_id,
            role=member.role,
            email="",
            display_name="",
        )
        if not record_scope_service.can_access_record(db, session, kind, record):
            raise ValueError("Record is outside your access scope")
        allowed = permission_service.get_effective_permissions(
            db, record.organization_id, user_id, member.role
        )
    else:
        allowed = execution_permissions
    module = "surrogates" if kind == "surrogate" else "donors"
    if f"change_{kind}_status" not in allowed:
        raise ValueError("Stage change permission required")
    if crosses_approval(db, record, target_stage) and f"approve_{module}" not in allowed:
        raise ValueError("Applicant approval permission required")
    return True


def claim_donor(db, session, donor_id):
    from app.db.enums import AuditEventType
    from app.services import audit_service

    if not permission_policy_service.is_enabled(db, session.org_id):
        raise ValueError("Donor claiming requires the upgraded permission model")
    permission_policy_service.lock_configuration(db, session.org_id)
    membership = permission_service.get_membership_for_user(db, session.org_id, session.user_id)
    if membership is None:
        raise PermissionError("Active organization membership required")
    from app.db.enums import Role

    session.role = Role(membership.role)
    donor = (
        db.query(Donor)
        .filter_by(id=donor_id, organization_id=session.org_id, is_archived=False)
        .with_for_update()
        .first()
    )
    if donor is None or not record_scope_service.can_access_record(db, session, "donor", donor):
        raise LookupError("Donor not found")
    if not permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, "assign_donors"
    ):
        raise PermissionError("Donor assignment permission required")
    if donor.owner_type != "queue":
        raise ValueError("Donor has already been claimed")
    pool = (
        db.query(Queue)
        .filter_by(
            id=donor.owner_id, organization_id=session.org_id, name="Donor Pool", is_active=True
        )
        .first()
    )
    if pool is None:
        raise ValueError("Donor is outside the approved pool")
    previous_owner = donor.owner_id
    donor.owner_type = "user"
    donor.owner_id = session.user_id
    audit_service.log_event(
        db,
        org_id=session.org_id,
        event_type=AuditEventType.DONOR_UPDATED,
        actor_user_id=session.user_id,
        target_type="donor",
        target_id=donor.id,
        details={"operation": "claim", "from_queue_id": str(previous_owner)},
    )
    db.flush()
    return donor
