"""Audit router - API endpoints for viewing audit logs."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.db.enums import AuditEventType, Role, ROLES_CAN_VIEW_AUDIT
from app.db.models import AuditLog, User
from app.schemas.auth import UserSession

router = APIRouter(prefix="/audit", tags=["Audit"])


# ============================================================================
# Schemas
# ============================================================================

class AuditLogRead(BaseModel):
    """Audit log entry for API response."""
    id: UUID
    event_type: str
    actor_user_id: UUID | None
    actor_name: str | None
    target_type: str | None
    target_id: UUID | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated audit log response."""
    items: list[AuditLogRead]
    total: int
    page: int
    per_page: int


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    event_type: str | None = Query(None, description="Filter by event type"),
    actor_user_id: UUID | None = Query(None, description="Filter by actor"),
    start_date: datetime | None = Query(None, description="Filter events after this date"),
    end_date: datetime | None = Query(None, description="Filter events before this date"),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles(list(ROLES_CAN_VIEW_AUDIT))),
) -> AuditLogListResponse:
    """
    List audit log entries for the organization.
    
    Requires: Manager or Developer role
    Filters: event_type, actor_user_id, date range
    """
    query = db.query(AuditLog).filter(
        AuditLog.organization_id == session.org_id
    )
    
    # Apply filters
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if actor_user_id:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)
    
    # Count total
    total = query.count()
    
    # Paginate (newest first)
    offset = (page - 1) * per_page
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(per_page).all()
    
    # Resolve actor names
    actor_ids = {log.actor_user_id for log in logs if log.actor_user_id}
    actor_names = {}
    if actor_ids:
        actors = db.query(User).filter(User.id.in_(actor_ids)).all()
        actor_names = {actor.id: actor.display_name for actor in actors}
    
    items = [
        AuditLogRead(
            id=log.id,
            event_type=log.event_type,
            actor_user_id=log.actor_user_id,
            actor_name=actor_names.get(log.actor_user_id) if log.actor_user_id else None,
            target_type=log.target_type,
            target_id=log.target_id,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in logs
    ]
    
    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/event-types")
def list_event_types(
    session: UserSession = Depends(require_roles(list(ROLES_CAN_VIEW_AUDIT))),
) -> list[str]:
    """List available audit event types for filtering."""
    return [e.value for e in AuditEventType]
