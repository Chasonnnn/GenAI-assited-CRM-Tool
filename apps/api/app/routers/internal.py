"""
Internal endpoints for scheduled/cron operations.

Protected by X-Internal-Secret header.
Call from external cron (Render/Railway/GH Actions).
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import MetaPageMapping
from app.db.enums import AlertType, AlertSeverity, IntegrationType, ConfigStatus
from app.services import alert_service, ops_service


router = APIRouter(prefix="/internal/scheduled", tags=["internal"])


def verify_internal_secret(x_internal_secret: str = Header(...)):
    """Verify the internal secret header."""
    expected = settings.INTERNAL_SECRET if hasattr(settings, 'INTERNAL_SECRET') else None
    if not expected:
        raise HTTPException(status_code=501, detail="INTERNAL_SECRET not configured")
    if x_internal_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid internal secret")


class TokenCheckResponse(BaseModel):
    pages_checked: int
    expiring_soon: int
    expired: int
    alerts_created: int


@router.post("/token-check", response_model=TokenCheckResponse)
def check_meta_tokens(x_internal_secret: str = Header(...)):
    """
    Daily sweep for expiring/expired Meta tokens.
    
    Creates/updates alerts for:
    - META_TOKEN_EXPIRING: Token expires in < 7 days
    - META_TOKEN_EXPIRED: Token already expired
    """
    verify_internal_secret(x_internal_secret)
    
    now = datetime.now(timezone.utc)
    expiry_threshold = now + timedelta(days=7)
    
    pages_checked = 0
    expiring_soon = 0
    expired = 0
    alerts_created = 0
    
    with SessionLocal() as db:
        # Get all active page mappings
        mappings = db.query(MetaPageMapping).filter(
            MetaPageMapping.is_active == True
        ).all()
        
        for mapping in mappings:
            pages_checked += 1
            
            if not mapping.token_expires_at:
                continue
            
            # Handle naive datetime (make it timezone-aware assuming UTC)
            token_expires = mapping.token_expires_at
            if token_expires.tzinfo is None:
                token_expires = token_expires.replace(tzinfo=timezone.utc)
            
            # Check if expired
            if token_expires < now:
                expired += 1
                
                # Update config status
                ops_service.update_config_status(
                    db=db,
                    org_id=mapping.organization_id,
                    integration_type=IntegrationType.META_LEADS,
                    config_status=ConfigStatus.EXPIRED_TOKEN,
                    integration_key=mapping.page_id,
                )
                
                # Create/update alert
                alert_service.create_or_update_alert(
                    db=db,
                    org_id=mapping.organization_id,
                    alert_type=AlertType.META_TOKEN_EXPIRED,
                    severity=AlertSeverity.CRITICAL,
                    title=f"Meta token expired for page {mapping.page_name or mapping.page_id}",
                    message=f"Token expired on {mapping.token_expires_at.strftime('%Y-%m-%d')}. Lead syncing is disabled.",
                    integration_key=mapping.page_id,
                )
                alerts_created += 1
                
            # Check if expiring soon
            elif token_expires < expiry_threshold:
                expiring_soon += 1
                
                days_until = (token_expires - now).days
                
                # Update config status (degraded but not fully broken)
                health = ops_service.get_or_create_health(
                    db=db,
                    org_id=mapping.organization_id,
                    integration_type=IntegrationType.META_LEADS,
                    integration_key=mapping.page_id,
                )
                # Don't override if already in error state
                if health.status != "error":
                    health.status = "degraded"
                    db.commit()
                
                # Create/update alert
                alert_service.create_or_update_alert(
                    db=db,
                    org_id=mapping.organization_id,
                    alert_type=AlertType.META_TOKEN_EXPIRING,
                    severity=AlertSeverity.WARN,
                    title=f"Meta token expiring in {days_until} days",
                    message=f"Token for page {mapping.page_name or mapping.page_id} expires on {mapping.token_expires_at.strftime('%Y-%m-%d')}. Refresh to avoid disruption.",
                    integration_key=mapping.page_id,
                )
                alerts_created += 1
    
    return TokenCheckResponse(
        pages_checked=pages_checked,
        expiring_soon=expiring_soon,
        expired=expired,
        alerts_created=alerts_created,
    )


class WorkflowSweepResponse(BaseModel):
    orgs_processed: int
    workflows_triggered: int


@router.post("/workflow-sweep", response_model=WorkflowSweepResponse)
def workflow_sweep(
    x_internal_secret: str = Header(...),
    sweep_type: str = "all",
):
    """
    Daily sweep for workflow automation triggers.
    
    Called by external cron (typically daily).
    Processes: scheduled, inactivity, task_due, task_overdue workflows.
    
    Args:
        sweep_type: 'all', 'scheduled', 'inactivity', 'task_due', 'task_overdue'
    """
    verify_internal_secret(x_internal_secret)
    
    from app.db.enums import JobType
    from app.db.models import Organization, Job
    from app.services import job_service
    
    orgs_processed = 0
    
    with SessionLocal() as db:
        # Get all active organizations
        orgs = db.query(Organization).filter(Organization.is_active == True).all()
        
        for org in orgs:
            # Schedule a sweep job for each org
            job_service.schedule_job(
                db=db,
                job_type=JobType.WORKFLOW_SWEEP,
                org_id=org.id,
                payload={
                    "org_id": str(org.id),
                    "sweep_type": sweep_type,
                },
            )
            orgs_processed += 1
        
        db.commit()
    
    return WorkflowSweepResponse(
        orgs_processed=orgs_processed,
        workflows_triggered=0,  # Actual count happens in worker
    )

