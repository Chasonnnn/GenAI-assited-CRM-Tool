"""Surrogates write routes."""

from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.core.surrogate_access import (
    can_modify_surrogate,
    check_surrogate_access,
    ensure_can_manage_surrogate_priority,
)
from app.db.enums import AuditEventType, OwnerType, Role
from app.db.models import Surrogate
from app.schemas.auth import UserSession
from app.schemas.surrogate import (
    BulkAssign,
    BulkStageChange,
    BulkStageChangeResult,
    InterviewOutcomeCreate,
    SurrogateActivityRead,
    SurrogateAssign,
    SurrogateCreate,
    SurrogateRead,
    SurrogateUpdate,
)
from app.services import audit_service, membership_service, queue_service, surrogate_service

from .surrogates_shared import _surrogate_to_read

router = APIRouter()


def create_surrogate(
    request: Request,
    data: SurrogateCreate,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
    db: Session = Depends(get_db),
) -> SurrogateRead:
    """Create a new surrogate."""
    if data.is_priority:
        ensure_can_manage_surrogate_priority(session.role)

    try:
        surrogate = surrogate_service.create_surrogate(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            data=data,
            emit_events=True,
        )
    except IntegrityError as exc:
        if surrogate_service.is_duplicate_email_conflict(exc):
            raise HTTPException(
                status_code=409, detail="A surrogate with this email already exists"
            )
        if surrogate_service.is_surrogate_number_conflict(exc):
            raise HTTPException(
                status_code=503,
                detail="Unable to allocate a new surrogate number. Please retry.",
            )
        raise

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.SURROGATE_CREATED,
        actor_user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        details={
            "source": surrogate.source,
            "owner_type": surrogate.owner_type,
            "owner_id": str(surrogate.owner_id) if surrogate.owner_id else None,
        },
        request=request,
    )
    db.commit()

    return _surrogate_to_read(surrogate, db)


@router.post(
    "/{surrogate_id:uuid}/claim",
    response_model=dict[str, object],
    dependencies=[Depends(require_csrf_header)],
)
def claim_surrogate(
    request: Request,
    surrogate_id: UUID,
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """
    Claim a surrogate from a queue (atomic).

    - Intake specialists: only allowed to claim from the system Unassigned queue.
    - Case managers/admin/developer: must have assign_surrogates permission (can claim from any queue).
    """
    from app.services import permission_service
    from app.services.queue_service import (
        NotAllowedQueueError,
        NotQueueMemberError,
        SurrogateAlreadyClaimedError,
        SurrogateNotFoundError,
    )

    role_str = session.role.value if hasattr(session.role, "value") else session.role

    allowed_queue_ids = None
    if session.role == Role.INTAKE_SPECIALIST:
        default_queue = queue_service.get_or_create_default_queue(db, session.org_id)
        allowed_queue_ids = {default_queue.id}
    else:
        # Respect per-user permission overrides (revoke > grant > role default).
        if not permission_service.check_permission(
            db,
            session.org_id,
            session.user_id,
            role_str,
            "assign_surrogates",
        ):
            raise HTTPException(status_code=403, detail="Missing permission: assign_surrogates")

    try:
        surrogate = queue_service.claim_surrogate(
            db=db,
            org_id=session.org_id,
            surrogate_id=surrogate_id,
            claimer_user_id=session.user_id,
            allowed_queue_ids=allowed_queue_ids,
        )
        audit_service.log_event(
            db=db,
            org_id=session.org_id,
            event_type=AuditEventType.SURROGATE_CLAIMED,
            actor_user_id=session.user_id,
            target_type="surrogate",
            target_id=surrogate.id,
            details={
                "owner_type": surrogate.owner_type,
                "owner_id": str(surrogate.owner_id) if surrogate.owner_id else None,
            },
            request=request,
        )
        db.commit()
        return {"message": "Surrogate claimed", "surrogate_id": str(surrogate.id)}
    except SurrogateNotFoundError:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    except NotAllowedQueueError:
        raise HTTPException(
            status_code=403,
            detail="Only surrogates in the Unassigned queue can be claimed by intake specialists",
        )
    except NotQueueMemberError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except SurrogateAlreadyClaimedError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch(
    "/{surrogate_id:uuid}",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_surrogate(
    request: Request,
    surrogate_id: UUID,
    data: SurrogateUpdate,
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """Update surrogate fields."""
    from app.services import permission_service, pipeline_service, surrogate_status_service

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    update_data = data.model_dump(exclude_unset=True)
    priority_value = update_data.get("is_priority")
    is_priority_change = (
        "is_priority" in update_data
        and priority_value is not None
        and priority_value != surrogate.is_priority
    )
    if is_priority_change:
        ensure_can_manage_surrogate_priority(session.role)

    is_priority_only_update = bool(update_data) and set(update_data.keys()) <= {"is_priority"}

    has_edit_permission = permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        session.role.value,
        POLICIES["surrogates"].actions["edit"].value,
    )
    if not is_priority_only_update and not has_edit_permission:
        raise HTTPException(
            status_code=403,
            detail=f"Missing permission: {POLICIES['surrogates'].actions['edit'].value}",
        )

    if not is_priority_only_update and not can_modify_surrogate(
        surrogate,
        str(session.user_id),
        session.role,
        db=db,
        org_id=session.org_id,
    ):
        raise HTTPException(status_code=403, detail="Not authorized to update this surrogate")

    was_delivery_date_empty = surrogate.actual_delivery_date is None
    is_setting_delivery_date = (
        "actual_delivery_date" in update_data
        and update_data["actual_delivery_date"] is not None
        and was_delivery_date_empty
    )
    delivery_date_value = (
        update_data.get("actual_delivery_date") if is_setting_delivery_date else None
    )

    try:
        surrogate = surrogate_service.update_surrogate(
            db,
            surrogate,
            data,
            user_id=session.user_id,
            org_id=session.org_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if is_setting_delivery_date and surrogate.stage_id:
        current_stage = pipeline_service.get_stage_by_id(db, surrogate.stage_id)
        if current_stage and not pipeline_service.stage_matches_key(current_stage, "delivered"):
            delivered_stage = pipeline_service.get_stage_by_slug(
                db, current_stage.pipeline_id, "delivered"
            )
            if delivered_stage:
                try:
                    from datetime import datetime, time

                    effective_at = (
                        datetime.combine(delivery_date_value, time(0, 0))
                        if delivery_date_value
                        else None
                    )

                    surrogate_status_service.change_status(
                        db=db,
                        surrogate=surrogate,
                        new_stage_id=delivered_stage.id,
                        user_id=session.user_id,
                        user_role=session.role,
                        reason="Auto-advanced: Actual delivery date was recorded",
                        effective_at=effective_at,
                    )
                    db.refresh(surrogate)
                except ValueError:
                    pass

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.SURROGATE_UPDATED,
        actor_user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        details={
            "updated_fields": sorted(update_data.keys()),
            "priority_only": is_priority_only_update,
        },
        request=request,
    )
    db.commit()

    return _surrogate_to_read(surrogate, db)


@router.post(
    "/{surrogate_id:uuid}/interview-outcomes",
    response_model=SurrogateActivityRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def log_interview_outcome(
    surrogate_id: UUID,
    data: InterviewOutcomeCreate,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["edit"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """Log a structured interview outcome for a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        item, _ = surrogate_service.log_interview_outcome(
            db=db,
            surrogate=surrogate,
            data=data,
            user=session,
        )
        db.commit()
        return SurrogateActivityRead(
            id=item["id"],
            activity_type=item["activity_type"],
            actor_user_id=item["actor_user_id"],
            actor_name=item["actor_name"],
            details=item["details"],
            created_at=item["created_at"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/{surrogate_id:uuid}/assign",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def assign_surrogate(
    request: Request,
    surrogate_id: UUID,
    data: SurrogateAssign,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["assign"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """Assign surrogate to a user or queue."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    if data.owner_type == OwnerType.USER:
        membership = membership_service.get_membership_for_org(db, session.org_id, data.owner_id)
        if not membership:
            raise HTTPException(status_code=400, detail="User not found in organization")
    elif data.owner_type == OwnerType.QUEUE:
        queue = queue_service.get_queue(db, session.org_id, data.owner_id)
        if not queue or not queue.is_active:
            raise HTTPException(status_code=400, detail="Queue not found or inactive")
    else:
        raise HTTPException(status_code=400, detail="Invalid owner_type")

    surrogate = surrogate_service.assign_surrogate(
        db, surrogate, data.owner_type, data.owner_id, session.user_id
    )
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.SURROGATE_ASSIGNED,
        actor_user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        details={
            "owner_type": surrogate.owner_type,
            "owner_id": str(surrogate.owner_id) if surrogate.owner_id else None,
        },
        request=request,
    )
    db.commit()
    return _surrogate_to_read(surrogate, db)


@router.post("/bulk-assign", dependencies=[Depends(require_csrf_header)])
def bulk_assign_surrogates(
    request: Request,
    data: BulkAssign,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["assign"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> object:
    """Bulk assign multiple surrogates to a user or queue."""
    if data.owner_type == OwnerType.USER:
        membership = membership_service.get_membership_for_org(db, session.org_id, data.owner_id)
        if not membership:
            raise HTTPException(status_code=400, detail="User not found in organization")
    elif data.owner_type == OwnerType.QUEUE:
        queue = queue_service.get_queue(db, session.org_id, data.owner_id)
        if not queue or not queue.is_active:
            raise HTTPException(status_code=400, detail="Queue not found or inactive")
    else:
        raise HTTPException(status_code=400, detail="Invalid owner_type")

    surrogate_state_rows = (
        db.query(Surrogate.id, Surrogate.is_archived)
        .filter(
            Surrogate.organization_id == session.org_id,
            Surrogate.id.in_(data.surrogate_ids),
        )
        .all()
    )
    surrogate_archived_by_id = {
        surrogate_id: is_archived for surrogate_id, is_archived in surrogate_state_rows
    }
    active_surrogate_ids = [
        surrogate_id
        for surrogate_id, is_archived in surrogate_archived_by_id.items()
        if not is_archived
    ]
    surrogate_map = {
        surrogate.id: surrogate
        for surrogate in (
            db.query(Surrogate)
            .filter(
                Surrogate.organization_id == session.org_id,
                Surrogate.id.in_(active_surrogate_ids),
                Surrogate.is_archived.is_(False),
            )
            .all()
        )
    }

    results = {"assigned": 0, "failed": []}
    for s_id in data.surrogate_ids:
        surrogate = surrogate_map.get(s_id)
        if not surrogate:
            results["failed"].append({"surrogate_id": str(s_id), "reason": "Surrogate not found"})
            continue

        try:
            surrogate_service.assign_surrogate(
                db, surrogate, data.owner_type, data.owner_id, session.user_id
            )
            results["assigned"] += 1
        except Exception as e:
            results["failed"].append({"surrogate_id": str(s_id), "reason": str(e)})

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.SURROGATE_BULK_ASSIGNED,
        actor_user_id=session.user_id,
        target_type="surrogate",
        details={
            "requested_count": len(data.surrogate_ids),
            "assigned_count": results["assigned"],
            "failed_count": len(results["failed"]),
            "owner_type": data.owner_type.value
            if hasattr(data.owner_type, "value")
            else str(data.owner_type),
            "owner_id": str(data.owner_id),
        },
        request=request,
    )
    db.commit()

    return results


@router.post(
    "/bulk-change-stage",
    response_model=BulkStageChangeResult,
    dependencies=[Depends(require_csrf_header)],
)
def bulk_change_surrogates_stage(
    request: Request,
    data: BulkStageChange,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> BulkStageChangeResult:
    """Bulk change stage for explicitly selected surrogates."""
    from app.services import (
        pipeline_service,
        pipeline_semantics_service,
        surrogate_stage_context,
        surrogate_status_service,
    )

    if session.role not in {Role.ADMIN, Role.DEVELOPER}:
        raise HTTPException(
            status_code=403,
            detail="Only admins and developers can bulk change surrogate stages",
        )

    surrogate_pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        session.org_id,
    )
    target_stage = pipeline_service.get_stage_by_id(db, data.stage_id)
    if (
        not target_stage
        or not target_stage.is_active
        or target_stage.pipeline_id != surrogate_pipeline.id
    ):
        raise HTTPException(status_code=400, detail="Invalid or inactive stage")

    target_semantics = pipeline_semantics_service.get_stage_semantics(target_stage)
    if (
        target_semantics.pause_behavior != "none"
        or target_semantics.capabilities.requires_delivery_details
    ):
        raise HTTPException(
            status_code=400,
            detail="Bulk stage changes only support immediate stages",
        )

    surrogate_state_rows = (
        db.query(Surrogate.id, Surrogate.is_archived)
        .filter(
            Surrogate.organization_id == session.org_id,
            Surrogate.id.in_(data.surrogate_ids),
        )
        .all()
    )
    surrogate_archived_by_id = {
        surrogate_id: is_archived for surrogate_id, is_archived in surrogate_state_rows
    }
    failed: list[dict[str, str]] = []
    applied = 0

    for surrogate_id in data.surrogate_ids:
        if surrogate_id not in surrogate_archived_by_id:
            failed.append({"surrogate_id": str(surrogate_id), "reason": "Surrogate not found"})
            continue

        if surrogate_archived_by_id.get(surrogate_id):
            failed.append(
                {
                    "surrogate_id": str(surrogate_id),
                    "reason": "Cannot change status of archived surrogate",
                }
            )
            continue
        db.expunge_all()
        surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
        if surrogate is None:
            failed.append({"surrogate_id": str(surrogate_id), "reason": "Surrogate not found"})
            continue
        if surrogate.is_archived:
            failed.append(
                {
                    "surrogate_id": str(surrogate_id),
                    "reason": "Cannot change status of archived surrogate",
                }
            )
            continue

        stage_context = surrogate_stage_context.get_stage_context(db, surrogate)
        if stage_context.is_on_hold:
            failed.append(
                {
                    "surrogate_id": str(surrogate_id),
                    "reason": "Cannot bulk change stage for surrogates currently on hold",
                }
            )
            continue
        if surrogate.stage_id == data.stage_id:
            failed.append(
                {
                    "surrogate_id": str(surrogate_id),
                    "reason": "Target stage is same as current stage",
                }
            )
            continue
        if (
            stage_context.effective_stage is not None
            and target_stage.order < stage_context.effective_stage.order
        ):
            failed.append(
                {
                    "surrogate_id": str(surrogate_id),
                    "reason": "Bulk stage changes do not support regressions",
                }
            )
            continue

        try:
            result = surrogate_status_service.change_status(
                db=db,
                surrogate=surrogate,
                new_stage_id=data.stage_id,
                user_id=session.user_id,
                user_role=session.role,
                emit_events=True,
            )
        except ValueError as exc:
            db.rollback()
            failed.append({"surrogate_id": str(surrogate_id), "reason": str(exc)})
            continue

        if result["status"] == "applied":
            applied += 1
            continue

        failed.append(
            {
                "surrogate_id": str(surrogate_id),
                "reason": result.get("message") or "Stage change was not applied",
            }
        )

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.SURROGATE_BULK_STATUS_CHANGED,
        actor_user_id=session.user_id,
        target_type="surrogate",
        details={
            "requested_count": len(data.surrogate_ids),
            "applied_count": applied,
            "failed_count": len(failed),
            "target_stage_id": str(data.stage_id),
            "target_stage_slug": target_stage.slug,
        },
        request=request,
    )
    db.commit()

    return BulkStageChangeResult(
        requested=len(data.surrogate_ids),
        applied=applied,
        failed=failed,
    )


@router.post(
    "/{surrogate_id:uuid}/archive",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def archive_surrogate(
    request: Request,
    surrogate_id: UUID,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["archive"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """Soft-delete (archive) a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    surrogate = surrogate_service.archive_surrogate(
        db, surrogate, session.user_id, emit_events=True
    )
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.SURROGATE_ARCHIVED,
        actor_user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        request=request,
    )
    db.commit()
    return _surrogate_to_read(surrogate, db)


@router.post(
    "/{surrogate_id:uuid}/restore",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def restore_surrogate(
    request: Request,
    surrogate_id: UUID,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["archive"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """Restore an archived surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    surrogate, error = surrogate_service.restore_surrogate(
        db, surrogate, session.user_id, emit_events=True
    )
    if error:
        raise HTTPException(status_code=409, detail=error)

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.SURROGATE_RESTORED,
        actor_user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        request=request,
    )
    db.commit()

    return _surrogate_to_read(surrogate, db)


@router.delete(
    "/{surrogate_id:uuid}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_surrogate(
    request: Request,
    surrogate_id: UUID,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["delete"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> Response:
    """Permanently delete a surrogate (requires prior archive)."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    if not surrogate.is_archived:
        raise HTTPException(
            status_code=400, detail="Surrogate must be archived before permanent deletion"
        )

    surrogate_service.hard_delete_surrogate(db, surrogate, emit_events=True)
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.SURROGATE_DELETED,
        actor_user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate_id,
        request=request,
    )
    db.commit()
    return None
