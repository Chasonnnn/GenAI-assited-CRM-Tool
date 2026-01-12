"""
Ops/Alerts endpoints for integration health and system alerts.

Manager+ access for viewing integration status and managing alerts.
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    get_current_session,
    get_db,
    require_permission,
    require_csrf_header,
)
from app.core.policies import POLICIES
from app.db.enums import AlertStatus, AlertSeverity
from app.schemas.auth import UserSession
from app.services import ops_service, alert_service, metrics_service


router = APIRouter(
    prefix="/ops",
    tags=["ops"],
    dependencies=[Depends(require_permission(POLICIES["ops"].default))],
)


# =============================================================================
# Pydantic Schemas
# =============================================================================


class IntegrationHealthResponse(BaseModel):
    id: str
    integration_type: str
    integration_key: Optional[str]
    status: str
    config_status: str
    last_success_at: Optional[str]
    last_error_at: Optional[str]
    last_error: Optional[str]
    error_count_24h: int


class AlertResponse(BaseModel):
    id: str
    alert_type: str
    severity: str
    status: str
    title: str
    message: Optional[str]
    integration_key: Optional[str]
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: Optional[datetime]


class AlertSummaryResponse(BaseModel):
    warn: int
    error: int
    critical: int


class AlertsListResponse(BaseModel):
    items: list[AlertResponse]
    total: int


class WorkflowSliResponse(BaseModel):
    workflow: str
    window_minutes: int
    prefixes: list[str]
    request_count: int
    success_rate: float
    error_rate: float
    avg_latency_ms: int
    slo_success_rate: float
    slo_avg_latency_ms: int
    meets_slo: bool


# Valid enum values for typed query params
AlertStatusParam = Literal["open", "acknowledged", "resolved", "snoozed"]
AlertSeverityParam = Literal["warn", "error", "critical"]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/health", response_model=list[IntegrationHealthResponse])
def get_integration_health(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get health status of all integrations."""
    return ops_service.list_integration_health(db, session.org_id)


@router.get("/alerts/summary", response_model=AlertSummaryResponse)
def get_alerts_summary(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get count of open alerts by severity."""
    summary = alert_service.get_alert_summary(db, session.org_id)
    return AlertSummaryResponse(**summary)


@router.get("/alerts", response_model=AlertsListResponse)
def list_alerts(
    status: Optional[AlertStatusParam] = Query(None, description="Filter by status"),
    severity: Optional[AlertSeverityParam] = Query(
        None, description="Filter by severity"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List system alerts with optional filters."""
    # FastAPI validates the Literal types, so these are safe
    status_enum = AlertStatus(status) if status else None
    severity_enum = AlertSeverity(severity) if severity else None

    alerts = alert_service.list_alerts(
        db=db,
        org_id=session.org_id,
        status=status_enum,
        severity=severity_enum,
        limit=limit,
        offset=offset,
    )

    # Pass severity to count_alerts for consistent pagination
    total = alert_service.count_alerts(db, session.org_id, status_enum, severity_enum)

    return AlertsListResponse(
        items=[
            AlertResponse(
                id=str(a.id),
                alert_type=a.alert_type,
                severity=a.severity,
                status=a.status,
                title=a.title,
                message=a.message,
                integration_key=a.integration_key,
                occurrence_count=a.occurrence_count,
                first_seen_at=a.first_seen_at,
                last_seen_at=a.last_seen_at,
                resolved_at=a.resolved_at,
            )
            for a in alerts
        ],
        total=total,
    )


@router.get("/sli", response_model=list[WorkflowSliResponse])
def get_workflow_sli(
    window_minutes: int = Query(
        settings.SLO_WINDOW_MINUTES, ge=5, le=1440, description="Window in minutes"
    ),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get SLI/SLO rollups for core workflows."""
    workflow_prefixes = {
        "cases": ["/cases", "/intended-parents", "/matches", "/notes", "/attachments"],
        "tasks": ["/tasks"],
        "dashboard": ["/dashboard", "/analytics"],
        "automation": ["/workflows", "/campaigns"],
    }

    results: list[WorkflowSliResponse] = []
    for workflow, prefixes in workflow_prefixes.items():
        rollup = metrics_service.get_sli_rollup(
            db=db,
            org_id=session.org_id,
            prefixes=prefixes,
            window_minutes=window_minutes,
        )
        meets_slo = rollup["success_rate"] >= settings.SLO_SUCCESS_RATE and (
            rollup["avg_latency_ms"] <= settings.SLO_AVG_LATENCY_MS
            or rollup["request_count"] == 0
        )
        results.append(
            WorkflowSliResponse(
                workflow=workflow,
                window_minutes=window_minutes,
                prefixes=prefixes,
                request_count=int(rollup["request_count"]),
                success_rate=float(rollup["success_rate"]),
                error_rate=float(rollup["error_rate"]),
                avg_latency_ms=int(rollup["avg_latency_ms"]),
                slo_success_rate=settings.SLO_SUCCESS_RATE,
                slo_avg_latency_ms=settings.SLO_AVG_LATENCY_MS,
                meets_slo=meets_slo,
            )
        )

    return results


@router.post("/alerts/{alert_id}/resolve", dependencies=[Depends(require_csrf_header)])
def resolve_alert(
    alert_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Resolve an alert."""
    # Verify alert belongs to org
    alert = alert_service.get_alert_for_org(db, session.org_id, alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert_service.resolve_alert(db, session.org_id, alert_id, session.user_id)
    return {"status": "resolved", "alert_id": str(alert_id)}


@router.post(
    "/alerts/{alert_id}/acknowledge", dependencies=[Depends(require_csrf_header)]
)
def acknowledge_alert(
    alert_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Acknowledge an alert (stops notifications but keeps open)."""
    # Verify alert belongs to org
    alert = alert_service.get_alert_for_org(db, session.org_id, alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert_service.acknowledge_alert(db, session.org_id, alert_id)
    return {"status": "acknowledged", "alert_id": str(alert_id)}


@router.post("/alerts/{alert_id}/snooze", dependencies=[Depends(require_csrf_header)])
def snooze_alert(
    alert_id: UUID,
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Snooze an alert for specified hours."""
    # Verify alert belongs to org
    alert = alert_service.get_alert_for_org(db, session.org_id, alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert_service.snooze_alert(db, session.org_id, alert_id, hours)
    return {"status": "snoozed", "alert_id": str(alert_id), "hours": hours}
