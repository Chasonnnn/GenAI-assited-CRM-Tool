"""Workflow metrics router for UI instrumentation events."""

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header
from app.db.enums import AuditEventType
from app.schemas.auth import UserSession
from app.services import audit_service
from app.types import JsonObject

WorkflowMetricEventType = Literal[
    "workflow_path_dashboard_viewed",
    "workflow_path_unassigned_queue_viewed",
    "workflow_path_surrogate_viewed",
    "workflow_path_first_contact_logged",
    "workflow_setup_started",
    "workflow_setup_completed",
]


class WorkflowMetricEventCreate(BaseModel):
    event_type: WorkflowMetricEventType
    target_type: str | None = Field(default=None, max_length=64)
    target_id: UUID | None = None
    details: dict[str, Any] | None = None


class WorkflowMetricEventResponse(BaseModel):
    success: bool = True


router = APIRouter(prefix="/workflow-metrics", tags=["workflow-metrics"])


@router.post(
    "/events",
    status_code=202,
    response_model=WorkflowMetricEventResponse,
    dependencies=[Depends(require_csrf_header)],
)
def record_workflow_metric_event(
    payload: WorkflowMetricEventCreate,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> WorkflowMetricEventResponse:
    """Record a workflow instrumentation event for baseline/throughput analysis."""
    details: JsonObject | None = payload.details

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType(payload.event_type),
        actor_user_id=session.user_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        details=details,
        request=request,
    )
    db.commit()
    return WorkflowMetricEventResponse()
