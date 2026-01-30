"""AI bulk task creation routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.core.surrogate_access import check_surrogate_access
from app.schemas.ai_tasks import BulkTaskCreateRequest, BulkTaskCreateResponse
from app.schemas.auth import UserSession
from app.services import ai_task_service, ip_service, match_service, surrogate_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/create-bulk-tasks",
    response_model=BulkTaskCreateResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def create_bulk_tasks(
    body: BulkTaskCreateRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.TASKS_CREATE)),
) -> BulkTaskCreateResponse:
    """
    Create multiple tasks in a single transaction (all-or-nothing).

    Uses request_id for idempotency - same request_id returns cached result.
    Tasks can be linked to case, surrogate, intended parent, or match.
    """
    cached_response = ai_task_service.get_cached_bulk_response(
        db,
        session.org_id,
        session.user_id,
        body.request_id,
    )
    if cached_response:
        logger.info("Returning cached result for request_id=%s", body.request_id)
        return cached_response

    # Verify entity exists and belongs to org
    entity_type = None
    entity_id = None
    match = None
    surrogate_for_access = None

    surrogate_id = body.surrogate_id
    if surrogate_id:
        surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
        if not surrogate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
        surrogate_for_access = surrogate
        entity_type = "case"
        entity_id = surrogate_id
    elif body.intended_parent_id:
        parent = ip_service.get_intended_parent(db, body.intended_parent_id, session.org_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intended parent not found",
            )
        entity_type = "intended_parent"
        entity_id = body.intended_parent_id
    elif body.match_id:
        match = match_service.get_match(db, body.match_id, session.org_id)
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        entity_type = "match"
        entity_id = body.match_id

        # Enforce access to the associated surrogate (when present)
        if match.surrogate_id:
            surrogate_for_access = surrogate_service.get_surrogate(
                db, session.org_id, match.surrogate_id
            )

    # Surrogate access enforcement (owner/role-based). For IP-only tasks, there may be no surrogate to check.
    if surrogate_for_access:
        check_surrogate_access(
            surrogate=surrogate_for_access,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )

    task_surrogate_id = surrogate_id
    task_ip_id = body.intended_parent_id

    # If creating from match, link to both case and intended_parent from the match
    if body.match_id and entity_type == "match":
        task_surrogate_id = match.surrogate_id if match else None
        task_ip_id = match.intended_parent_id if match else None

    activity_surrogate_id = None
    if entity_type in {"match", "case"}:
        activity_surrogate_id = task_surrogate_id

    return ai_task_service.create_bulk_tasks(
        db=db,
        session=session,
        body=body,
        entity_type=entity_type or "",
        entity_id=entity_id,
        task_surrogate_id=task_surrogate_id,
        task_intended_parent_id=task_ip_id,
        activity_surrogate_id=activity_surrogate_id,
    )
