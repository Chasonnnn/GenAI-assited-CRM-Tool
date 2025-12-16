"""
Integration health and error tracking service.

Manages integration health status and hourly error rollups.
"""
import hashlib
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.models import IntegrationHealth, IntegrationErrorRollup
from app.db.enums import IntegrationType, IntegrationStatus, ConfigStatus


def get_hour_bucket(dt: datetime | None = None) -> datetime:
    """Get the start of the hour for a given datetime."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0)


def get_or_create_health(
    db: Session,
    org_id: UUID,
    integration_type: IntegrationType,
    integration_key: str | None = None,
) -> IntegrationHealth:
    """Get or create an IntegrationHealth record."""
    health = db.query(IntegrationHealth).filter(
        IntegrationHealth.organization_id == org_id,
        IntegrationHealth.integration_type == integration_type.value,
        IntegrationHealth.integration_key == integration_key,
    ).first()
    
    if not health:
        health = IntegrationHealth(
            organization_id=org_id,
            integration_type=integration_type.value,
            integration_key=integration_key,
            status=IntegrationStatus.HEALTHY.value,
            config_status=ConfigStatus.CONFIGURED.value,
        )
        db.add(health)
        db.commit()
        db.refresh(health)
    
    return health


def record_success(
    db: Session,
    org_id: UUID,
    integration_type: IntegrationType,
    integration_key: str | None = None,
) -> IntegrationHealth:
    """Record a successful integration operation."""
    health = get_or_create_health(db, org_id, integration_type, integration_key)
    
    health.last_success_at = datetime.now(timezone.utc)
    health.status = IntegrationStatus.HEALTHY.value
    health.last_error = None  # Clear last error on success
    db.commit()
    
    return health


def record_error(
    db: Session,
    org_id: UUID,
    integration_type: IntegrationType,
    error_message: str,
    integration_key: str | None = None,
) -> IntegrationHealth:
    """
    Record an integration error.
    
    Updates IntegrationHealth and increments the hourly error rollup.
    """
    now = datetime.now(timezone.utc)
    hour_bucket = get_hour_bucket(now)
    
    # Update health status
    health = get_or_create_health(db, org_id, integration_type, integration_key)
    health.last_error_at = now
    health.last_error = error_message[:1000]  # Truncate for safety
    health.status = IntegrationStatus.ERROR.value
    
    # Upsert error rollup (increment count)
    stmt = insert(IntegrationErrorRollup).values(
        organization_id=org_id,
        integration_type=integration_type.value,
        integration_key=integration_key,
        period_start=hour_bucket,
        error_count=1,
        last_error=error_message[:1000],
    ).on_conflict_do_update(
        constraint="uq_integration_error_rollup",
        set_={
            "error_count": IntegrationErrorRollup.error_count + 1,
            "last_error": error_message[:1000],
        }
    )
    db.execute(stmt)
    db.commit()
    
    return health


def get_error_count_24h(
    db: Session,
    org_id: UUID,
    integration_type: IntegrationType,
    integration_key: str | None = None,
) -> int:
    """Get error count for last 24 hours from rollups."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    
    result = db.execute(
        text("""
            SELECT COALESCE(SUM(error_count), 0) as total
            FROM integration_error_rollup
            WHERE organization_id = :org_id
              AND integration_type = :integration_type
              AND (integration_key = :integration_key OR (integration_key IS NULL AND :integration_key IS NULL))
              AND period_start > :cutoff
        """),
        {
            "org_id": org_id,
            "integration_type": integration_type.value,
            "integration_key": integration_key,
            "cutoff": cutoff,
        }
    )
    row = result.fetchone()
    return int(row[0]) if row else 0


def update_config_status(
    db: Session,
    org_id: UUID,
    integration_type: IntegrationType,
    config_status: ConfigStatus,
    integration_key: str | None = None,
) -> IntegrationHealth:
    """Update the configuration status of an integration."""
    health = get_or_create_health(db, org_id, integration_type, integration_key)
    health.config_status = config_status.value
    
    # If token expired/missing, mark as degraded
    if config_status in (ConfigStatus.EXPIRED_TOKEN, ConfigStatus.MISSING_TOKEN):
        health.status = IntegrationStatus.DEGRADED.value
    
    db.commit()
    return health


def list_integration_health(
    db: Session,
    org_id: UUID,
) -> list[dict]:
    """
    List all integrations and their health status.
    
    Returns enriched data including 24h error counts.
    """
    healths = db.query(IntegrationHealth).filter(
        IntegrationHealth.organization_id == org_id
    ).all()
    
    result = []
    for h in healths:
        error_count = get_error_count_24h(
            db, org_id, 
            IntegrationType(h.integration_type),
            h.integration_key
        )
        result.append({
            "id": str(h.id),
            "integration_type": h.integration_type,
            "integration_key": h.integration_key,
            "status": h.status,
            "config_status": h.config_status,
            "last_success_at": h.last_success_at.isoformat() if h.last_success_at else None,
            "last_error_at": h.last_error_at.isoformat() if h.last_error_at else None,
            "last_error": h.last_error,
            "error_count_24h": error_count,
        })
    
    return result
