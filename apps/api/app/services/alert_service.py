"""
System alerts service.

Manages deduplicated, actionable alerts with fingerprinting.
"""
import hashlib
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import SystemAlert
from app.db.enums import AlertType, AlertSeverity, AlertStatus


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
    """
    dedupe_key = fingerprint(alert_type, integration_key, error_class, http_status)
    now = datetime.now(timezone.utc)
    
    # Try to find existing alert
    existing = db.query(SystemAlert).filter(
        SystemAlert.organization_id == org_id,
        SystemAlert.dedupe_key == dedupe_key,
    ).first()
    
    if existing:
        # Update existing alert
        existing.last_seen_at = now
        existing.occurrence_count += 1
        existing.message = message
        if details:
            existing.details = details
        
        # Reopen if resolved/snoozed and recurring
        if existing.status in (AlertStatus.RESOLVED.value, AlertStatus.SNOOZED.value):
            # Check if snooze expired
            if existing.snoozed_until and now > existing.snoozed_until:
                existing.status = AlertStatus.OPEN.value
                existing.snoozed_until = None
            elif existing.status == AlertStatus.RESOLVED.value:
                existing.status = AlertStatus.OPEN.value
        
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new alert
    alert = SystemAlert(
        organization_id=org_id,
        dedupe_key=dedupe_key,
        integration_key=integration_key,
        alert_type=alert_type.value,
        severity=severity.value,
        status=AlertStatus.OPEN.value,
        title=title[:255],
        message=message,
        details=details,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def list_alerts(
    db: Session,
    org_id: UUID,
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SystemAlert]:
    """List alerts with optional filtering."""
    query = db.query(SystemAlert).filter(
        SystemAlert.organization_id == org_id
    )
    
    if status:
        query = query.filter(SystemAlert.status == status.value)
    if severity:
        query = query.filter(SystemAlert.severity == severity.value)
    
    return query.order_by(
        SystemAlert.last_seen_at.desc()
    ).offset(offset).limit(limit).all()


def count_alerts(
    db: Session,
    org_id: UUID,
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
) -> int:
    """Count alerts with optional status and severity filter."""
    query = db.query(SystemAlert).filter(
        SystemAlert.organization_id == org_id
    )
    if status:
        query = query.filter(SystemAlert.status == status.value)
    if severity:
        query = query.filter(SystemAlert.severity == severity.value)
    return query.count()


def get_alert_for_org(db: Session, org_id: UUID, alert_id: UUID) -> SystemAlert | None:
    """Get a single alert scoped to org."""
    return db.query(SystemAlert).filter(
        SystemAlert.id == alert_id,
        SystemAlert.organization_id == org_id,
    ).first()


def resolve_alert(
    db: Session,
    alert_id: UUID,
    user_id: UUID,
) -> SystemAlert | None:
    """Resolve an alert."""
    alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
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
    alert_id: UUID,
) -> SystemAlert | None:
    """Acknowledge an alert (stops immediate notifications but keeps open)."""
    alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
    if not alert:
        return None
    
    alert.status = AlertStatus.ACKNOWLEDGED.value
    db.commit()
    db.refresh(alert)
    return alert


def snooze_alert(
    db: Session,
    alert_id: UUID,
    hours: int = 24,
) -> SystemAlert | None:
    """Snooze an alert for a specified duration."""
    alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
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
        {"org_id": org_id}
    )
    
    summary = {"warn": 0, "error": 0, "critical": 0}
    for row in result:
        summary[row[0]] = row[1]
    
    return summary
