"""Queue management API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    get_current_session,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.services import queue_service
from app.services.queue_service import (
    QueueNotFoundError,
    CaseNotFoundError,
    CaseAlreadyClaimedError,
    DuplicateQueueNameError,
    NotQueueMemberError,
    QueueMemberExistsError,
    QueueMemberNotFoundError,
    QueueMemberUserNotFoundError,
)

router = APIRouter(
    dependencies=[Depends(require_permission(POLICIES["cases"].actions["assign"]))],
)


# =============================================================================
# Schemas
# =============================================================================


class QueueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class QueueUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class QueueResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    is_active: bool
    member_ids: list[UUID] = []

    model_config = {"from_attributes": True}


class QueueMemberResponse(BaseModel):
    id: UUID
    queue_id: UUID
    user_id: UUID
    user_name: str | None = None
    user_email: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class QueueMemberAdd(BaseModel):
    user_id: UUID = Field(..., description="User ID to add to queue")


class ClaimRequest(BaseModel):
    """Empty body - claimer is the current user."""

    pass


class ReleaseRequest(BaseModel):
    queue_id: UUID = Field(..., description="Queue to release case to")


class AssignToQueueRequest(BaseModel):
    queue_id: UUID = Field(..., description="Queue to assign case to")


# =============================================================================
# Queue CRUD Endpoints
# =============================================================================


@router.get("", response_model=list[QueueResponse])
def list_queues(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    include_inactive: bool = False,
):
    """List all queues for the organization."""
    queues = queue_service.list_queues(db, session.org_id, include_inactive)
    return [_queue_to_response(q) for q in queues]


@router.get("/{queue_id}", response_model=QueueResponse)
def get_queue(
    queue_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get a specific queue."""
    queue = queue_service.get_queue(db, session.org_id, queue_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return _queue_to_response(queue)


@router.post(
    "",
    response_model=QueueResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_queue(
    data: QueueCreate,
    session: UserSession = Depends(require_permission(POLICIES["queues"].default)),
    db: Session = Depends(get_db),
):
    """Create a new queue."""

    try:
        queue = queue_service.create_queue(
            db, session.org_id, data.name, data.description
        )
        db.commit()
        return queue
    except DuplicateQueueNameError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch(
    "/{queue_id}",
    response_model=QueueResponse,
    dependencies=[Depends(require_csrf_header)],
)
def update_queue(
    queue_id: UUID,
    data: QueueUpdate,
    session: UserSession = Depends(require_permission(POLICIES["queues"].default)),
    db: Session = Depends(get_db),
):
    """Update a queue."""

    try:
        queue = queue_service.update_queue(
            db,
            session.org_id,
            queue_id,
            name=data.name,
            description=data.description,
            is_active=data.is_active,
        )
        db.commit()
        return queue
    except QueueNotFoundError:
        raise HTTPException(status_code=404, detail="Queue not found")
    except DuplicateQueueNameError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete(
    "/{queue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_queue(
    queue_id: UUID,
    session: UserSession = Depends(require_permission(POLICIES["queues"].default)),
    db: Session = Depends(get_db),
):
    """Soft-delete a queue (set inactive)."""

    try:
        queue_service.delete_queue(db, session.org_id, queue_id)
        db.commit()
    except QueueNotFoundError:
        raise HTTPException(status_code=404, detail="Queue not found")


# =============================================================================
# Claim / Release Endpoints (on cases)
# =============================================================================


@router.post(
    "/cases/{case_id}/claim",
    response_model=dict,
    dependencies=[Depends(require_csrf_header)],
)
def claim_case(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Claim a case from a queue.

    - Case must be in a queue (owner_type="queue")
    - Sets owner to current user
    - Returns 409 if already claimed by a user
    """
    try:
        case = queue_service.claim_case(db, session.org_id, case_id, session.user_id)
        db.commit()
        return {"message": "Case claimed", "case_id": str(case.id)}
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseAlreadyClaimedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except NotQueueMemberError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post(
    "/cases/{case_id}/release",
    response_model=dict,
    dependencies=[Depends(require_csrf_header)],
)
def release_case(
    case_id: UUID,
    data: ReleaseRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Release a case back to a queue.

    - Case must be owned by a user
    - Transfers ownership to specified queue
    """
    try:
        case = queue_service.release_case(
            db, session.org_id, case_id, data.queue_id, session.user_id
        )
        db.commit()
        return {"message": "Case released to queue", "case_id": str(case.id)}
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except QueueNotFoundError:
        raise HTTPException(status_code=404, detail="Queue not found or inactive")


@router.post(
    "/cases/{case_id}/assign",
    response_model=dict,
    dependencies=[Depends(require_csrf_header)],
)
def assign_case_to_queue(
    case_id: UUID,
    data: AssignToQueueRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Assign a case to a queue.

    Works whether case is currently user-owned or queue-owned.
    """
    try:
        case = queue_service.assign_to_queue(
            db, session.org_id, case_id, data.queue_id, session.user_id
        )
        db.commit()
        return {"message": "Case assigned to queue", "case_id": str(case.id)}
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except QueueNotFoundError:
        raise HTTPException(status_code=404, detail="Queue not found or inactive")


# =============================================================================
# Queue Member Management
# =============================================================================


@router.get("/{queue_id}/members", response_model=list[QueueMemberResponse])
def list_queue_members(
    queue_id: UUID,
    session: UserSession = Depends(require_permission(POLICIES["queues"].default)),
    db: Session = Depends(get_db),
):
    """List members of a queue."""
    queue = queue_service.get_queue(db, session.org_id, queue_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")

    return [
        QueueMemberResponse(
            id=m.id,
            queue_id=m.queue_id,
            user_id=m.user_id,
            user_name=m.user.full_name if m.user else None,
            user_email=m.user.email if m.user else None,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in queue.members
    ]


@router.post(
    "/{queue_id}/members",
    response_model=QueueMemberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def add_queue_member(
    queue_id: UUID,
    data: QueueMemberAdd,
    session: UserSession = Depends(require_permission(POLICIES["queues"].default)),
    db: Session = Depends(get_db),
):
    """Add a user to a queue."""

    queue = queue_service.get_queue(db, session.org_id, queue_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")

    try:
        member, user = queue_service.add_queue_member(
            db=db,
            org_id=session.org_id,
            queue_id=queue_id,
            user_id=data.user_id,
        )
    except QueueMemberUserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except QueueMemberExistsError:
        raise HTTPException(
            status_code=409, detail="User is already a member of this queue"
        )

    return QueueMemberResponse(
        id=member.id,
        queue_id=member.queue_id,
        user_id=member.user_id,
        user_name=user.full_name,
        user_email=user.email,
        created_at=member.created_at.isoformat() if member.created_at else None,
    )


@router.delete(
    "/{queue_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def remove_queue_member(
    queue_id: UUID,
    user_id: UUID,
    session: UserSession = Depends(require_permission(POLICIES["queues"].default)),
    db: Session = Depends(get_db),
):
    """Remove a user from a queue."""

    try:
        queue_service.remove_queue_member(db=db, queue_id=queue_id, user_id=user_id)
    except QueueMemberNotFoundError:
        raise HTTPException(status_code=404, detail="Member not found")


# =============================================================================
# Helpers
# =============================================================================


def _queue_to_response(queue) -> QueueResponse:
    """Convert queue model to response with member_ids."""
    return QueueResponse(
        id=queue.id,
        organization_id=queue.organization_id,
        name=queue.name,
        description=queue.description,
        is_active=queue.is_active,
        member_ids=[m.user_id for m in queue.members]
        if hasattr(queue, "members")
        else [],
    )
