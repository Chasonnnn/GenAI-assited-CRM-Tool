"""
System alerts service.

Manages deduplicated, actionable alerts with fingerprinting.
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import case, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import SystemAlert
from app.db.enums import AlertType, AlertSeverity, AlertStatus
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)


def fingerprint(
    alert_type: AlertType,
    integration_key: str | None,
    error_class: str | None,
    http_status: int | None = None,
) -> str:
    """
    Generate a stable, PII-safe fingerprint for alert deduplication.

    No timestamps or random IDs - ensures dedupe works correctly.
    """
    normalized = f"{alert_type.value}:{integration_key or 'default'}:{error_class or 'unknown'}:{http_status or 0}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def create_or_update_alert(
    db: Session,
    org_id: UUID,
    alert_type: AlertType,
    severity: AlertSeverity,
    title: str,
    message: str | None = None,
    integration_key: str | None = None,
    error_class: str | None = None,
    http_status: int | None = None,
    details: dict | None = None,
) -> SystemAlert:
    """
    Create a new alert or update an existing one if fingerprint matches.

    Updates: last_seen_at, occurrence_count, message, details
    Reopens resolved/snoozed alerts if they recur.

    Transaction-bound: caller controls commit/rollback.
    """
    dedupe_key = fingerprint(alert_type, integration_key, error_class, http_status)
    now = datetime.now(timezone.utc)

    reopen_condition = (
        (SystemAlert.status == AlertStatus.RESOLVED.value)
        | (
            (SystemAlert.status == AlertStatus.SNOOZED.value)
            & SystemAlert.snoozed_until.is_not(None)
            & (SystemAlert.snoozed_until < now)
        )
    )

    update_values: dict[str, object] = {
        "last_seen_at": now,
        "occurrence_count": SystemAlert.occurrence_count + 1,
        "message": message,
        "status": case(
            (reopen_condition, AlertStatus.OPEN.value),
            else_=SystemAlert.status,
        ),
        "snoozed_until": case(
            (reopen_condition, None),
            else_=SystemAlert.snoozed_until,
        ),
        "resolved_at": case(
            (reopen_condition, None),
            else_=SystemAlert.resolved_at,
        ),
        "resolved_by_user_id": case(
            (reopen_condition, None),
            else_=SystemAlert.resolved_by_user_id,
        ),
    }
    if details is not None:
        update_values["details"] = details

    stmt = (
        insert(SystemAlert)
        .values(
            organization_id=org_id,
            dedupe_key=dedupe_key,
            integration_key=integration_key,
            alert_type=alert_type.value,
            severity=severity.value,
            status=AlertStatus.OPEN.value,
            first_seen_at=now,
            last_seen_at=now,
            occurrence_count=1,
            title=title[:255],
            message=message,
            details=details,
        )
        .on_conflict_do_update(
            constraint="uq_system_alerts_dedupe",
            set_=update_values,
        )
        .returning(SystemAlert.id)
    )

    alert_id = db.execute(stmt).scalar_one()
    alert = db.get(SystemAlert, alert_id)
    if alert is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Failed to load upserted alert")
    return alert


def record_alert_isolated(
    *,
    org_id: UUID,
    alert_type: AlertType,
    severity: AlertSeverity,
    title: str,
    message: str | None = None,
    integration_key: str | None = None,
    error_class: str | None = None,
    http_status: int | None = None,
    details: dict | None = None,
) -> SystemAlert | None:
    """
    Persist a system alert in an isolated DB session.

    Use this from exception/failure paths where the parent transaction might roll back.
    """
    db = SessionLocal()
    try:
        alert = create_or_update_alert(
            db=db,
            org_id=org_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            integration_key=integration_key,
            error_class=error_class,
            http_status=http_status,
            details=details,
        )
        db.commit()
        return alert
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to persist system alert",
            extra={
                "org_id": str(org_id),
                "alert_type": alert_type.value,
                "integration_key": integration_key,
                "error_class": error_class,
                "http_status": http_status,
            },
        )
        return None
    finally:
        db.close()


def list_alerts(
    db: Session,
    org_id: UUID,
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SystemAlert]:
    """List alerts with optional filtering."""
    query = db.query(SystemAlert).filter(SystemAlert.organization_id == org_id)

    if status:
        query = query.filter(SystemAlert.status == status.value)
    if severity:
        query = query.filter(SystemAlert.severity == severity.value)

    return query.order_by(SystemAlert.last_seen_at.desc()).offset(offset).limit(limit).all()


def count_alerts(
    db: Session,
    org_id: UUID,
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
) -> int:
    """Count alerts with optional status and severity filter."""
    query = db.query(SystemAlert).filter(SystemAlert.organization_id == org_id)
    if status:
        query = query.filter(SystemAlert.status == status.value)
    if severity:
        query = query.filter(SystemAlert.severity == severity.value)
    return query.count()


def get_alert_for_org(db: Session, org_id: UUID, alert_id: UUID) -> SystemAlert | None:
    """Get a single alert scoped to org."""
    return (
        db.query(SystemAlert)
        .filter(
            SystemAlert.id == alert_id,
            SystemAlert.organization_id == org_id,
        )
        .first()
    )


def resolve_alert(
    db: Session,
    org_id: UUID,
    alert_id: UUID,
    user_id: UUID,
) -> SystemAlert | None:
    """Resolve an alert."""
    alert = (
        db.query(SystemAlert)
        .filter(
            SystemAlert.id == alert_id,
            SystemAlert.organization_id == org_id,
        )
        .first()
    )
    if not alert:
        return None

    alert.status = AlertStatus.RESOLVED.value
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by_user_id = user_id
    db.commit()
    db.refresh(alert)
    return alert


def acknowledge_alert(
    db: Session,
    org_id: UUID,
    alert_id: UUID,
) -> SystemAlert | None:
    """Acknowledge an alert (stops immediate notifications but keeps open)."""
    alert = (
        db.query(SystemAlert)
        .filter(
            SystemAlert.id == alert_id,
            SystemAlert.organization_id == org_id,
        )
        .first()
    )
    if not alert:
        return None

    alert.status = AlertStatus.ACKNOWLEDGED.value
    db.commit()
    db.refresh(alert)
    return alert


def snooze_alert(
    db: Session,
    org_id: UUID,
    alert_id: UUID,
    hours: int = 24,
) -> SystemAlert | None:
    """Snooze an alert for a specified duration."""
    alert = (
        db.query(SystemAlert)
        .filter(
            SystemAlert.id == alert_id,
            SystemAlert.organization_id == org_id,
        )
        .first()
    )
    if not alert:
        return None

    alert.status = AlertStatus.SNOOZED.value
    alert.snoozed_until = datetime.now(timezone.utc) + timedelta(hours=hours)
    db.commit()
    db.refresh(alert)
    return alert


def get_alert_summary(
    db: Session,
    org_id: UUID,
) -> dict:
    """Get a summary of alerts by severity for dashboard."""
    result = db.execute(
        text("""
            SELECT severity, COUNT(*) as count
            FROM system_alerts
            WHERE organization_id = :org_id
              AND status = 'open'
            GROUP BY severity
        """),
        {"org_id": org_id},
    )

    summary = {"warn": 0, "error": 0, "critical": 0}
    for row in result:
        summary[row[0]] = row[1]

    return summary
