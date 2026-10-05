"""Canonical approval boundaries and atomic retained Intake access."""

import hashlib
import json

from sqlalchemy import and_, or_

from app.db.models import (
    Donor,
    Membership,
    Pipeline,
    PipelineStage,
    Queue,
    RecordScopeMigrationReview,
    Surrogate,
    User,
)
from app.schemas.auth import UserSession
from app.services import permission_policy_service, permission_service, record_scope_service

# Intended parents have no applicant approval gate; their record scope has no phases.
APPROVAL_MODULES = {"surrogate": "surrogates", "donor": "donors"}


class SharedSurrogatePoolError(ValueError):
    """A shared post-approval record cannot acquire an exclusive owner."""


def is_shared_surrogate_pool(db, record) -> bool:
    return (
        permission_policy_service.is_enabled(db, record.organization_id)
        and record_scope_service.record_phase(db, record.organization_id, "surrogate", record)
        == "post_approval"
    )


def require_surrogate_owner_allowed(db, record, owner_type, owner_id) -> None:
    if not is_shared_surrogate_pool(db, record):
        return
    from app.services import queue_service

    pool = (
        db.query(Queue)
        .filter_by(
            organization_id=record.organization_id, name=queue_service.SURROGATE_POOL_QUEUE_NAME
        )
        .first()
    )
    if owner_type == "queue" and pool is not None and owner_id == pool.id:
        return
    raise SharedSurrogatePoolError(
        "Post-approval surrogates stay in the shared Surrogate Pool. Use collaborators instead."
    )


def _move_surrogate_to_pool(db, record, actor_user_id=None) -> bool:
    from app.db.enums import AuditEventType, SurrogateActivityType
    from app.services import activity_service, audit_service, queue_service

    previous_pool = (
        db.query(Queue)
        .filter_by(
            organization_id=record.organization_id, name=queue_service.SURROGATE_POOL_QUEUE_NAME
        )
        .first()
    )
    reactivated = previous_pool is not None and not previous_pool.is_active
    pool = queue_service.get_or_create_surrogate_pool_queue(db, record.organization_id)
    if reactivated:
        audit_service.log_event(
            db,
            org_id=record.organization_id,
            event_type=AuditEventType.SETTINGS_ORG_UPDATED,
            actor_user_id=actor_user_id,
            target_type="queue",
            target_id=pool.id,
            details={"operation": "reactivate_shared_surrogate_pool"},
        )
    if record.owner_type == "queue" and record.owner_id == pool.id and record.assigned_at is None:
        return False
    old_owner_type, old_owner_id = record.owner_type, record.owner_id
    review = (
        db.query(RecordScopeMigrationReview)
        .filter_by(
            organization_id=record.organization_id,
            surrogate_id=record.id,
            record_fingerprint=record_scope_service._record_fingerprint("surrogate", record),
        )
        .first()
    )
    if old_owner_type == "user":
        record_scope_service.retain_intake_owner_at_handoff(
            db,
            record.organization_id,
            "surrogate",
            record,
            old_owner_id,
            actor_user_id=actor_user_id,
        )
    record.owner_type, record.owner_id, record.assigned_at = "queue", pool.id, None
    # Ownership normalization preserves a review of the same stage and verified history.
    if review is not None:
        review.record_fingerprint = record_scope_service._record_fingerprint("surrogate", record)
    details = {
        "from_owner_type": old_owner_type,
        "from_owner_id": str(old_owner_id) if old_owner_id else None,
        "to_queue_id": str(pool.id),
        "reason": "shared_post_approval_pool",
    }
    activity_service.log_activity(
        db=db,
        surrogate_id=record.id,
        organization_id=record.organization_id,
        activity_type=SurrogateActivityType.SURROGATE_ASSIGNED_TO_QUEUE,
        actor_user_id=actor_user_id,
        details=details,
    )
    audit_service.log_event(
        db,
        org_id=record.organization_id,
        event_type=AuditEventType.SURROGATE_ASSIGNED,
        actor_user_id=actor_user_id,
        target_type="surrogate",
        target_id=record.id,
        details=details,
    )
    db.flush()
    return True


def normalize_shared_surrogate_pool(db, record, actor_user_id=None) -> bool:
    """Normalize a current post-approval record in the caller's transaction."""
    permission_policy_service.lock_configuration(db, record.organization_id)
    if not is_shared_surrogate_pool(db, record):
        return False
    return _move_surrogate_to_pool(db, record, actor_user_id)


def build_surrogate_pool_transfer_plan(db, org_id) -> list[dict]:
    """Preview only current ownership; never infer a former Intake assignee."""
    from app.services import queue_service

    pool = (
        db.query(Queue)
        .filter_by(organization_id=org_id, name=queue_service.SURROGATE_POOL_QUEUE_NAME)
        .first()
    )
    query = (
        db.query(
            Surrogate.id,
            Surrogate.surrogate_number,
            Surrogate.stage_id,
            Surrogate.paused_from_stage_id,
            Surrogate.owner_type,
            Surrogate.owner_id,
            Surrogate.assigned_at,
            Surrogate.updated_at,
            Membership.role,
            Membership.is_active.label("member_active"),
            User.is_active.label("user_active"),
        )
        .outerjoin(
            Membership,
            and_(
                Membership.organization_id == Surrogate.organization_id,
                Membership.user_id == Surrogate.owner_id,
                Surrogate.owner_type == "user",
            ),
        )
        .outerjoin(User, User.id == Membership.user_id)
        .filter(
            Surrogate.organization_id == org_id,
            record_scope_service.build_phase_filter(org_id, "surrogate", "post_approval"),
        )
    )
    if pool is not None and pool.is_active:
        query = query.filter(
            or_(
                Surrogate.owner_type != "queue",
                Surrogate.owner_id != pool.id,
                Surrogate.assigned_at.isnot(None),
            )
        )
    plan = []
    for row in query.order_by(Surrogate.id).all():
        fingerprint = hashlib.sha256(
            json.dumps(
                [str(value) if value is not None else None for value in row]
                + [str(pool.id) if pool else None, pool.is_active if pool else None],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        plan.append(
            {
                "record_id": str(row.id),
                "record_number": row.surrogate_number,
                "expected_fingerprint": fingerprint,
                "owner_type": row.owner_type,
                "owner_id": str(row.owner_id),
                "retained_intake_user_id": str(row.owner_id)
                if row.role == "intake_specialist" and row.member_active and row.user_active
                else None,
            }
        )
    return plan


def apply_surrogate_pool_transfers(db, org_id, actor_user_id, plan: list[dict]) -> int:
    """Apply exactly the reviewed plan, without committing any part of activation."""
    from uuid import UUID

    permission_policy_service.lock_configuration(db, org_id)
    if not permission_policy_service.is_enabled(db, org_id):
        raise ValueError("Shared Surrogate Pool requires the upgraded permission model")
    records = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.id.in_([UUID(row["record_id"]) for row in plan]),
        )
        .order_by(Surrogate.id)
        .with_for_update()
        .populate_existing()
        .all()
    )
    if build_surrogate_pool_transfer_plan(db, org_id) != plan:
        raise ValueError("Surrogate Pool transfer plan changed. Review a new preview.")
    for record in records:
        _move_surrogate_to_pool(db, record, actor_user_id)
    return len(records)


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
    permission_policy_service.lock_configuration(db, record.organization_id)
    if not permission_policy_service.is_enabled(db, record.organization_id):
        return
    if not crosses_approval(db, record, target_stage):
        return
    if kind == "surrogate":
        _move_surrogate_to_pool(db, record, actor_user_id)
        return
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

    pool = (
        db.query(Queue).filter_by(organization_id=record.organization_id, name="Donor Pool").first()
    )
    if pool is None:
        pool = queue_service.create_queue(db, record.organization_id, "Donor Pool")
    pool.is_active = True
    record.owner_type = "queue"
    record.owner_id = pool.id


def authorize_stage_change(
    db, *, record, kind, target_stage, user_id, execution_permissions=None, lock_configuration=True
) -> bool:
    if lock_configuration:
        permission_policy_service.lock_configuration(db, record.organization_id)
    if not permission_policy_service.is_enabled(db, record.organization_id):
        return False
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
    if f"change_{kind}_status" not in allowed:
        raise ValueError("Stage change permission required")
    module = APPROVAL_MODULES.get(kind)
    if module and crosses_approval(db, record, target_stage) and f"approve_{module}" not in allowed:
        raise ValueError("Applicant approval permission required")
    return True


def _donor_claim_pool(db, org_id, donor):
    if donor.organization_id != org_id or donor.is_archived or donor.owner_type != "queue":
        return None
    return (
        db.query(Queue)
        .filter_by(id=donor.owner_id, organization_id=org_id, name="Donor Pool", is_active=True)
        .first()
    )


def can_claim_donor(db, session, donor):
    return (
        permission_policy_service.is_enabled(db, session.org_id)
        and permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, "assign_donors"
        )
        and record_scope_service.can_access_record(db, session, "donor", donor)
        and _donor_claim_pool(db, session.org_id, donor) is not None
    )


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
    pool = _donor_claim_pool(db, session.org_id, donor)
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
