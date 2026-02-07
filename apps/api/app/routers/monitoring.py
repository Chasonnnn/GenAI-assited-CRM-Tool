"""External monitoring webhooks (internal, secret-protected)."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_secret
from app.core.structured_logging import build_log_context
from app.db.enums import AlertSeverity, AlertType, AlertStatus
from app.core.deps import get_db
from app.services import alert_service, membership_service
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/alerts", tags=["internal"])


def verify_internal_secret(
    x_internal_secret: str | None = Header(default=None),
) -> None:
    expected = settings.INTERNAL_SECRET if hasattr(settings, "INTERNAL_SECRET") else None
    if not expected:
        raise HTTPException(status_code=501, detail="INTERNAL_SECRET not configured")
    if not verify_secret(x_internal_secret, expected):
        raise HTTPException(status_code=403, detail="Invalid internal secret")
    return


class GCPMetric(BaseModel):
    labels: dict[str, str] | None = None
    type: str | None = None


class GCPIncident(BaseModel):
    incident_id: str | None = None
    state: str | None = None
    policy_name: str | None = None
    policy_display_name: str | None = None
    condition_name: str | None = None
    summary: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    severity: str | None = None
    metric: GCPMetric | None = None


class GCPAlertPayload(BaseModel):
    incident: GCPIncident


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _map_severity(value: str | None) -> AlertSeverity:
    if not value:
        return AlertSeverity.WARN
    normalized = value.lower()
    if normalized in {"critical", "crit"}:
        return AlertSeverity.CRITICAL
    if normalized in {"error", "err"}:
        return AlertSeverity.ERROR
    return AlertSeverity.WARN


@router.post("/gcp")
def receive_gcp_alert(
    payload: GCPAlertPayload,
    x_internal_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    verify_internal_secret(x_internal_secret)

    incident = payload.incident
    labels = incident.metric.labels if incident.metric and incident.metric.labels else {}
    event = labels.get("event")
    user_id = labels.get("user_id")
    org_id = labels.get("org_id")

    if not org_id and user_id:
        try:
            membership = membership_service.get_membership_by_user_id(db, UUID(user_id))
        except Exception:
            membership = None
        if membership:
            org_id = str(membership.organization_id)

    if not org_id:
        logger.warning(
            "gcp_alert_missing_org",
            extra={
                "event": "gcp_alert_missing_org",
                "policy_name": incident.policy_display_name or incident.policy_name,
                "incident_id": incident.incident_id,
            },
        )
        return {"status": "skipped", "reason": "org_id_missing"}

    try:
        org_uuid = UUID(org_id)
    except ValueError:
        logger.warning(
            "gcp_alert_invalid_org",
            extra={
                "event": "gcp_alert_invalid_org",
                "policy_name": incident.policy_display_name or incident.policy_name,
                "incident_id": incident.incident_id,
            },
        )
        return {"status": "skipped", "reason": "org_id_invalid"}

    alert_type = (
        AlertType.NOTIFICATION_PUSH_FAILED if event == "ws_send_failed" else AlertType.API_ERROR
    )
    severity = _map_severity(incident.severity or incident.state)

    title = incident.policy_display_name or "Monitoring alert"
    message = incident.summary
    details: dict[str, Any] = {
        "incident_id": incident.incident_id,
        "state": incident.state,
        "policy_name": incident.policy_name,
        "condition_name": incident.condition_name,
        "event": event,
        "metric_type": incident.metric.type if incident.metric else None,
        "started_at": incident.started_at,
        "ended_at": incident.ended_at,
    }

    alert = alert_service.create_or_update_alert(
        db=db,
        org_id=org_uuid,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        integration_key=incident.policy_name,
        error_class=event or "gcp_alert",
        details=details,
    )

    if incident.state and incident.state.lower() == "closed":
        alert.status = AlertStatus.RESOLVED.value
        alert.resolved_at = _parse_ts(incident.ended_at) or datetime.now(timezone.utc)
        db.commit()

    logger.info(
        "gcp_alert_ingested",
        extra=build_log_context(org_id=org_id),
    )
    return {"status": "ok", "alert_id": str(alert.id)}
