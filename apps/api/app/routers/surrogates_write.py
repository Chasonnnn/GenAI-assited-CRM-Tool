"""Surrogates write routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.core.surrogate_access import can_modify_surrogate, check_surrogate_access
from app.db.enums import OwnerType, Role
from app.schemas.auth import UserSession
from app.schemas.surrogate import (
    BulkAssign,
    SurrogateAssign,
    SurrogateCreate,
    SurrogateRead,
    SurrogateUpdate,
)
from app.services import membership_service, queue_service, surrogate_service

from .surrogates_shared import _surrogate_to_read

router = APIRouter()


def create_surrogate(
    data: SurrogateCreate,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
    db: Session = Depends(get_db),
) -> SurrogateRead:
    """Create a new surrogate."""
    try:
        surrogate = surrogate_service.create_surrogate(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            data=data,
            emit_events=True,
        )
    except Exception as e:
        if "uq_surrogate_email_hash_active" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=409, detail="A surrogate with this email already exists"
            )
        raise

    return _surrogate_to_read(surrogate, db)


@router.post(
    "/{surrogate_id:uuid}/claim",
    response_model=dict,
    dependencies=[Depends(require_csrf_header)],
)
def claim_surrogate(
    surrogate_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
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
    surrogate_id: UUID,
    data: SurrogateUpdate,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
    db: Session = Depends(get_db),
):
    """Update surrogate fields."""
    from app.services import pipeline_service, surrogate_status_service

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    if not can_modify_surrogate(surrogate, str(session.user_id), session.role):
        raise HTTPException(status_code=403, detail="Not authorized to update this surrogate")

    was_delivery_date_empty = surrogate.actual_delivery_date is None
    update_data = data.model_dump(exclude_unset=True)
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
        if current_stage and current_stage.slug != "delivered":
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

    return _surrogate_to_read(surrogate, db)


@router.patch(
    "/{surrogate_id:uuid}/assign",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def assign_surrogate(
    surrogate_id: UUID,
    data: SurrogateAssign,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["assign"])),
    db: Session = Depends(get_db),
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
    return _surrogate_to_read(surrogate, db)


@router.post("/bulk-assign", dependencies=[Depends(require_csrf_header)])
def bulk_assign_surrogates(
    data: BulkAssign,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["assign"])),
    db: Session = Depends(get_db),
):
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

    results = {"assigned": 0, "failed": []}
    surrogates = surrogate_service.get_surrogates_by_ids(db, session.org_id, data.surrogate_ids)
    surrogates_map = {s.id: s for s in surrogates}

    for s_id in data.surrogate_ids:
        surrogate = surrogates_map.get(s_id)
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

    return results


@router.post(
    "/{surrogate_id:uuid}/archive",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def archive_surrogate(
    surrogate_id: UUID,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["archive"])),
    db: Session = Depends(get_db),
):
    """Soft-delete (archive) a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    surrogate = surrogate_service.archive_surrogate(
        db, surrogate, session.user_id, emit_events=True
    )
    return _surrogate_to_read(surrogate, db)


@router.post(
    "/{surrogate_id:uuid}/restore",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def restore_surrogate(
    surrogate_id: UUID,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["archive"])),
    db: Session = Depends(get_db),
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

    return _surrogate_to_read(surrogate, db)


@router.delete(
    "/{surrogate_id:uuid}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_surrogate(
    surrogate_id: UUID,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["delete"])),
    db: Session = Depends(get_db),
):
    """Permanently delete a surrogate (requires prior archive)."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    if not surrogate.is_archived:
        raise HTTPException(
            status_code=400, detail="Surrogate must be archived before permanent deletion"
        )

    surrogate_service.hard_delete_surrogate(db, surrogate, emit_events=True)
    return None
