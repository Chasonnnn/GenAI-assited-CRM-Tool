"""
Notifications Router - /me/notifications endpoints.

Provides notification listing, read status, and settings.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header
from app.schemas.auth import UserSession
from app.services import notification_service


router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class NotificationRead(BaseModel):
    """Notification response."""
    id: str
    type: str
    title: str
    body: str | None
    entity_type: str | None
    entity_id: str | None
    read_at: str | None
    created_at: str
    
    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Paginated notification list."""
    items: list[NotificationRead]
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Unread count only (for polling)."""
    count: int


class NotificationSettingsRead(BaseModel):
    """User notification settings."""
    case_assigned: bool
    case_status_changed: bool
    case_handoff: bool
    task_assigned: bool


class NotificationSettingsUpdate(BaseModel):
    """Update notification settings."""
    case_assigned: bool | None = None
    case_status_changed: bool | None = None
    case_handoff: bool | None = None
    task_assigned: bool | None = None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get user's notifications."""
    notifications = notification_service.get_notifications(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    
    unread_count = notification_service.get_unread_count(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
    )
    
    items = []
    for n in notifications:
        items.append(NotificationRead(
            id=str(n.id),
            type=n.type,
            title=n.title,
            body=n.body,
            entity_type=n.entity_type,
            entity_id=str(n.entity_id) if n.entity_id else None,
            read_at=n.read_at.isoformat() if n.read_at else None,
            created_at=n.created_at.isoformat(),
        ))
    
    return NotificationListResponse(items=items, unread_count=unread_count)


@router.get("/notifications/count", response_model=UnreadCountResponse)
def get_unread_count(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get unread notification count (for polling)."""
    count = notification_service.get_unread_count(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
    )
    return UnreadCountResponse(count=count)


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead,
    dependencies=[Depends(require_csrf_header)],
)
def mark_notification_read(
    notification_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Mark a notification as read."""
    notification = notification_service.mark_read(
        db=db,
        notification_id=notification_id,
        user_id=session.user_id,
    )
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return NotificationRead(
        id=str(notification.id),
        type=notification.type,
        title=notification.title,
        body=notification.body,
        entity_type=notification.entity_type,
        entity_id=str(notification.entity_id) if notification.entity_id else None,
        read_at=notification.read_at.isoformat() if notification.read_at else None,
        created_at=notification.created_at.isoformat(),
    )


@router.post(
    "/notifications/read-all",
    dependencies=[Depends(require_csrf_header)],
)
def mark_all_read(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read."""
    count = notification_service.mark_all_read(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
    )
    return {"marked_read": count}


@router.get("/settings/notifications", response_model=NotificationSettingsRead)
def get_notification_settings(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get user's notification settings."""
    settings = notification_service.get_user_settings(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
    )
    return NotificationSettingsRead(**settings)


@router.patch(
    "/settings/notifications",
    response_model=NotificationSettingsRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_notification_settings(
    data: NotificationSettingsUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update user's notification settings."""
    updates = data.model_dump(exclude_unset=True)
    settings = notification_service.update_user_settings(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        updates=updates,
    )
    return NotificationSettingsRead(**settings)
