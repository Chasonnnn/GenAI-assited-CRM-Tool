"""Router for status change request approval workflow."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.services import status_change_request_service


router = APIRouter(prefix="/status-change-requests", tags=["Status Change Requests"])


# ============================================================================
# Schemas
# ============================================================================


class StatusChangeRequestRead(BaseModel):
    """Response schema for a status change request."""

    id: UUID
    organization_id: UUID
    entity_type: str
    entity_id: UUID
    target_stage_id: UUID | None
    target_status: str | None
    effective_at: str  # ISO datetime
    reason: str
    requested_by_user_id: UUID | None
    requested_at: str  # ISO datetime
    status: str
    approved_by_user_id: UUID | None = None
    approved_at: str | None = None
    rejected_by_user_id: UUID | None = None
    rejected_at: str | None = None
    cancelled_by_user_id: UUID | None = None
    cancelled_at: str | None = None

    model_config = {"from_attributes": True}


class StatusChangeRequestDetail(BaseModel):
    """Response schema for a status change request with details."""

    request: StatusChangeRequestRead
    entity_name: str | None
    entity_number: str | None
    requester_name: str | None
    target_stage_label: str | None
    current_stage_label: str | None


class StatusChangeRequestListResponse(BaseModel):
    """Paginated list response for status change requests."""

    items: list[StatusChangeRequestDetail]
    total: int
    page: int
    per_page: int
    pages: int


class RejectRequest(BaseModel):
    """Request body for rejecting a status change request."""

    reason: str | None = None


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=StatusChangeRequestListResponse,
)
def list_pending_requests(
    entity_type: str | None = None,
    page: int = 1,
    per_page: int = 20,
    session: UserSession = Depends(
        require_permission(POLICIES["status_change_requests"].actions["view_requests"])
    ),
    db: Session = Depends(get_db),
):
    """
    List pending status change requests (admin only).

    Returns requests that need approval for stage/status regressions.
    """
    requests, total = status_change_request_service.get_pending_requests(
        db=db,
        org_id=session.org_id,
        entity_type=entity_type,
        page=page,
        per_page=per_page,
    )

    # Get details for each request
    items = []
    for req in requests:
        details = status_change_request_service.get_request_with_details(db, req.id)
        if details:
            items.append(
                StatusChangeRequestDetail(
                    request=StatusChangeRequestRead(
                        id=req.id,
                        organization_id=req.organization_id,
                        entity_type=req.entity_type,
                        entity_id=req.entity_id,
                        target_stage_id=req.target_stage_id,
                        target_status=req.target_status,
                        effective_at=req.effective_at.isoformat(),
                        reason=req.reason,
                        requested_by_user_id=req.requested_by_user_id,
                        requested_at=req.requested_at.isoformat(),
                        status=req.status,
                        approved_by_user_id=req.approved_by_user_id,
                        approved_at=req.approved_at.isoformat() if req.approved_at else None,
                        rejected_by_user_id=req.rejected_by_user_id,
                        rejected_at=req.rejected_at.isoformat() if req.rejected_at else None,
                        cancelled_by_user_id=req.cancelled_by_user_id,
                        cancelled_at=req.cancelled_at.isoformat() if req.cancelled_at else None,
                    ),
                    entity_name=details["entity_name"],
                    entity_number=details["entity_number"],
                    requester_name=details["requester_name"],
                    target_stage_label=details["target_stage_label"],
                    current_stage_label=details["current_stage_label"],
                )
            )

    pages = (total + per_page - 1) // per_page

    return StatusChangeRequestListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get(
    "/{request_id}",
    response_model=StatusChangeRequestDetail,
)
def get_request(
    request_id: UUID,
    session: UserSession = Depends(
        require_permission(POLICIES["status_change_requests"].actions["view_requests"])
    ),
    db: Session = Depends(get_db),
):
    """Get a status change request by ID."""
    details = status_change_request_service.get_request_with_details(db, request_id)
    if not details:
        raise HTTPException(status_code=404, detail="Request not found")

    req = details["request"]

    # Verify org access
    if req.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Request not found")

    return StatusChangeRequestDetail(
        request=StatusChangeRequestRead(
            id=req.id,
            organization_id=req.organization_id,
            entity_type=req.entity_type,
            entity_id=req.entity_id,
            target_stage_id=req.target_stage_id,
            target_status=req.target_status,
            effective_at=req.effective_at.isoformat(),
            reason=req.reason,
            requested_by_user_id=req.requested_by_user_id,
            requested_at=req.requested_at.isoformat(),
            status=req.status,
            approved_by_user_id=req.approved_by_user_id,
            approved_at=req.approved_at.isoformat() if req.approved_at else None,
            rejected_by_user_id=req.rejected_by_user_id,
            rejected_at=req.rejected_at.isoformat() if req.rejected_at else None,
            cancelled_by_user_id=req.cancelled_by_user_id,
            cancelled_at=req.cancelled_at.isoformat() if req.cancelled_at else None,
        ),
        entity_name=details["entity_name"],
        entity_number=details["entity_number"],
        requester_name=details["requester_name"],
        target_stage_label=details["target_stage_label"],
        current_stage_label=details["current_stage_label"],
    )


@router.post(
    "/{request_id}/approve",
    response_model=StatusChangeRequestRead,
    dependencies=[Depends(require_csrf_header)],
)
def approve_request(
    request_id: UUID,
    session: UserSession = Depends(
        require_permission(POLICIES["status_change_requests"].actions["approve_requests"])
    ),
    db: Session = Depends(get_db),
):
    """
    Approve a pending status change request.

    Applies the requested stage/status change and records the approval.
    """
    # Verify request belongs to org
    req = status_change_request_service.get_request(db, request_id)
    if not req or req.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Request not found")

    try:
        result = status_change_request_service.approve_request(
            db=db,
            request_id=request_id,
            admin_user_id=session.user_id,
            admin_role=session.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StatusChangeRequestRead(
        id=result.id,
        organization_id=result.organization_id,
        entity_type=result.entity_type,
        entity_id=result.entity_id,
        target_stage_id=result.target_stage_id,
        target_status=result.target_status,
        effective_at=result.effective_at.isoformat(),
        reason=result.reason,
        requested_by_user_id=result.requested_by_user_id,
        requested_at=result.requested_at.isoformat(),
        status=result.status,
        approved_by_user_id=result.approved_by_user_id,
        approved_at=result.approved_at.isoformat() if result.approved_at else None,
        rejected_by_user_id=result.rejected_by_user_id,
        rejected_at=result.rejected_at.isoformat() if result.rejected_at else None,
        cancelled_by_user_id=result.cancelled_by_user_id,
        cancelled_at=result.cancelled_at.isoformat() if result.cancelled_at else None,
    )


@router.post(
    "/{request_id}/reject",
    response_model=StatusChangeRequestRead,
    dependencies=[Depends(require_csrf_header)],
)
def reject_request(
    request_id: UUID,
    data: RejectRequest | None = None,
    session: UserSession = Depends(
        require_permission(POLICIES["status_change_requests"].actions["approve_requests"])
    ),
    db: Session = Depends(get_db),
):
    """
    Reject a pending status change request.

    The requested stage/status change is NOT applied.
    """
    # Verify request belongs to org
    req = status_change_request_service.get_request(db, request_id)
    if not req or req.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Request not found")

    try:
        result = status_change_request_service.reject_request(
            db=db,
            request_id=request_id,
            admin_user_id=session.user_id,
            admin_role=session.role,
            reason=data.reason if data else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StatusChangeRequestRead(
        id=result.id,
        organization_id=result.organization_id,
        entity_type=result.entity_type,
        entity_id=result.entity_id,
        target_stage_id=result.target_stage_id,
        target_status=result.target_status,
        effective_at=result.effective_at.isoformat(),
        reason=result.reason,
        requested_by_user_id=result.requested_by_user_id,
        requested_at=result.requested_at.isoformat(),
        status=result.status,
        approved_by_user_id=result.approved_by_user_id,
        approved_at=result.approved_at.isoformat() if result.approved_at else None,
        rejected_by_user_id=result.rejected_by_user_id,
        rejected_at=result.rejected_at.isoformat() if result.rejected_at else None,
        cancelled_by_user_id=result.cancelled_by_user_id,
        cancelled_at=result.cancelled_at.isoformat() if result.cancelled_at else None,
    )


@router.post(
    "/{request_id}/cancel",
    response_model=StatusChangeRequestRead,
    dependencies=[Depends(require_csrf_header)],
)
def cancel_request(
    request_id: UUID,
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
    db: Session = Depends(get_db),
):
    """
    Cancel a pending status change request.

    Only the requester can cancel their own request.
    """
    # Verify request belongs to org
    req = status_change_request_service.get_request(db, request_id)
    if not req or req.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Request not found")

    try:
        result = status_change_request_service.cancel_request(
            db=db,
            request_id=request_id,
            user_id=session.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StatusChangeRequestRead(
        id=result.id,
        organization_id=result.organization_id,
        entity_type=result.entity_type,
        entity_id=result.entity_id,
        target_stage_id=result.target_stage_id,
        target_status=result.target_status,
        effective_at=result.effective_at.isoformat(),
        reason=result.reason,
        requested_by_user_id=result.requested_by_user_id,
        requested_at=result.requested_at.isoformat(),
        status=result.status,
        approved_by_user_id=result.approved_by_user_id,
        approved_at=result.approved_at.isoformat() if result.approved_at else None,
        rejected_by_user_id=result.rejected_by_user_id,
        rejected_at=result.rejected_at.isoformat() if result.rejected_at else None,
        cancelled_by_user_id=result.cancelled_by_user_id,
        cancelled_at=result.cancelled_at.isoformat() if result.cancelled_at else None,
    )
