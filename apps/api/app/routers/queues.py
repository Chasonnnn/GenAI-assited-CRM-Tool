"""Queue management API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_session, require_csrf_header
from app.schemas.auth import UserSession
from app.db.enums import Role
from app.services import queue_service
from app.services.queue_service import (
    QueueNotFoundError,
    CaseNotFoundError,
    CaseAlreadyClaimedError,
    CaseNotInQueueError,
    DuplicateQueueNameError,
)

router = APIRouter()


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

    model_config = {"from_attributes": True}


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
    return queues


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
    return queue


@router.post("", response_model=QueueResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf_header)])
def create_queue(
    data: QueueCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a new queue. Manager+ only."""
    if session.role not in [Role.ADMIN.value, Role.DEVELOPER.value]:
        raise HTTPException(status_code=403, detail="Manager role required")
    
    try:
        queue = queue_service.create_queue(
            db, session.org_id, data.name, data.description
        )
        db.commit()
        return queue
    except DuplicateQueueNameError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/{queue_id}", response_model=QueueResponse, dependencies=[Depends(require_csrf_header)])
def update_queue(
    queue_id: UUID,
    data: QueueUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update a queue. Manager+ only."""
    if session.role not in [Role.ADMIN.value, Role.DEVELOPER.value]:
        raise HTTPException(status_code=403, detail="Manager role required")
    
    try:
        queue = queue_service.update_queue(
            db, session.org_id, queue_id,
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


@router.delete("/{queue_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf_header)])
def delete_queue(
    queue_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Soft-delete a queue (set inactive). Manager+ only."""
    if session.role not in [Role.ADMIN.value, Role.DEVELOPER.value]:
        raise HTTPException(status_code=403, detail="Manager role required")
    
    try:
        queue_service.delete_queue(db, session.org_id, queue_id)
        db.commit()
    except QueueNotFoundError:
        raise HTTPException(status_code=404, detail="Queue not found")


# =============================================================================
# Claim / Release Endpoints (on cases)
# =============================================================================

@router.post("/cases/{case_id}/claim", response_model=dict, dependencies=[Depends(require_csrf_header)])
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
    if session.role not in [Role.CASE_MANAGER.value, Role.ADMIN.value, Role.DEVELOPER.value]:
        raise HTTPException(status_code=403, detail="Case manager role required")
    
    try:
        case = queue_service.claim_case(
            db, session.org_id, case_id, session.user_id
        )
        db.commit()
        return {"message": "Case claimed", "case_id": str(case.id)}
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail="Case not found")
    except CaseAlreadyClaimedError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/cases/{case_id}/release", response_model=dict, dependencies=[Depends(require_csrf_header)])
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
    if session.role not in [Role.CASE_MANAGER.value, Role.ADMIN.value, Role.DEVELOPER.value]:
        raise HTTPException(status_code=403, detail="Case manager role required")
    
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


@router.post("/cases/{case_id}/assign", response_model=dict, dependencies=[Depends(require_csrf_header)])
def assign_case_to_queue(
    case_id: UUID,
    data: AssignToQueueRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Assign a case to a queue. Manager+ only.
    
    Works whether case is currently user-owned or queue-owned.
    """
    if session.role not in [Role.ADMIN.value, Role.DEVELOPER.value]:
        raise HTTPException(status_code=403, detail="Manager role required")
    
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
