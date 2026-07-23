"""Authenticated organization-scoped email operations API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db
from app.schemas.auth import UserSession
from app.schemas.email_operations import (
    EmailOperationMessageDetail,
    EmailOperationMessageListResponse,
    EmailOperationsReadinessResponse,
)
from app.services import email_operations_service


router = APIRouter(prefix="/email-operations", tags=["email-operations"])


@router.get("/readiness")
def get_readiness(
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> EmailOperationsReadinessResponse:
    """Return persisted send, tracking, and recent-activity readiness."""
    return email_operations_service.get_readiness(
        db,
        organization_id=session.org_id,
    )


@router.get("/messages")
def list_messages(
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
) -> EmailOperationMessageListResponse:
    """List sanitized outbound messages for the authenticated organization."""
    try:
        return email_operations_service.list_messages(
            db,
            organization_id=session.org_id,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


@router.get("/messages/{message_id}")
def get_message(
    message_id: UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> EmailOperationMessageDetail:
    """Return sanitized delivery diagnostics for one organization message."""
    message = email_operations_service.get_message(
        db,
        organization_id=session.org_id,
        message_id=message_id,
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Email message not found")
    return message
