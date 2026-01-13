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
from app.db.enums import (
    AlertType,
    AlertSeverity,
    IntegrationType,
    ConfigStatus,
    JobType,
)
from app.services import (
    alert_service,
    job_service,
    meta_page_service,
    ops_service,
    org_service,
    task_service,
)


router = APIRouter(prefix="/internal/scheduled", tags=["internal"])


def verify_internal_secret(x_internal_secret: str = Header(...)):
    """Verify the internal secret header."""
    expected = (
        settings.INTERNAL_SECRET if hasattr(settings, "INTERNAL_SECRET") else None
    )
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
        mappings = meta_page_service.list_active_mappings(db)

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
    from app.services import job_service

    orgs_processed = 0

    with SessionLocal() as db:
        # Get all organizations
        orgs = org_service.list_orgs(db)

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


class WorkflowApprovalExpiryResponse(BaseModel):
    orgs_processed: int
    jobs_created: int


@router.post(
    "/workflow-approval-expiry", response_model=WorkflowApprovalExpiryResponse
)
def workflow_approval_expiry(x_internal_secret: str = Header(...)):
    """
    Schedule workflow approval expiry sweeps for all organizations.

    Called by external cron (every 5 minutes recommended).
    """
    verify_internal_secret(x_internal_secret)

    from app.services import job_service

    orgs_processed = 0
    jobs_created = 0

    with SessionLocal() as db:
        orgs = org_service.list_orgs(db)

        for org in orgs:
            job_service.schedule_job(
                db=db,
                job_type=JobType.WORKFLOW_APPROVAL_EXPIRY,
                org_id=org.id,
                payload={"org_id": str(org.id)},
            )
            orgs_processed += 1
            jobs_created += 1

        db.commit()

    return WorkflowApprovalExpiryResponse(
        orgs_processed=orgs_processed,
        jobs_created=jobs_created,
    )


class DataPurgeScheduleResponse(BaseModel):
    orgs_processed: int
    jobs_created: int


@router.post("/data-purge", response_model=DataPurgeScheduleResponse)
def data_purge_schedule(x_internal_secret: str = Header(...)):
    """Schedule data purge jobs for all organizations."""
    verify_internal_secret(x_internal_secret)

    from app.services import job_service

    orgs_processed = 0
    jobs_created = 0

    with SessionLocal() as db:
        orgs = org_service.list_orgs(db)
        for org in orgs:
            job_service.schedule_job(
                db=db,
                job_type=JobType.DATA_PURGE,
                org_id=org.id,
                payload={"org_id": str(org.id)},
            )
            orgs_processed += 1
            jobs_created += 1
        db.commit()

    return DataPurgeScheduleResponse(
        orgs_processed=orgs_processed,
        jobs_created=jobs_created,
    )


class TaskNotificationsResponse(BaseModel):
    tasks_due_soon: int
    tasks_overdue: int
    notifications_created: int


@router.post("/task-notifications", response_model=TaskNotificationsResponse)
def task_notifications_sweep(x_internal_secret: str = Header(...)):
    """
    Daily sweep for task due/overdue notifications.

    Called by external cron (daily recommended).
    Creates one-time notifications for:
    - Tasks due tomorrow (TASK_DUE_SOON)
    - Overdue tasks (TASK_OVERDUE)

    Uses dedupe keys to ensure one-time notifications per task.
    """
    verify_internal_secret(x_internal_secret)

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.services import notification_service

    tasks_due_soon = 0
    tasks_overdue = 0
    notifications_created = 0

    with SessionLocal() as db:
        orgs = org_service.list_orgs(db)
        for org in orgs:
            tz_name = org.timezone or "UTC"
            try:
                org_tz = ZoneInfo(tz_name)
            except Exception:
                org_tz = ZoneInfo("UTC")

            today = datetime.now(org_tz).date()
            tomorrow = today + timedelta(days=1)

            # Find tasks due tomorrow (not completed)
            due_soon_tasks = task_service.list_user_tasks_due_on(
                db=db,
                org_id=org.id,
                due_date=tomorrow,
            )

            for task in due_soon_tasks:
                tasks_due_soon += 1
                notification_service.notify_task_due_soon(
                    db=db,
                    task_id=task.id,
                    task_title=task.title,
                    org_id=task.organization_id,
                    assignee_id=task.owner_id,
                    due_date=task.due_date.strftime("%Y-%m-%d"),
                    case_number=task.case.case_number if task.case else None,
                )
                notifications_created += 1

            # Find overdue tasks (not completed, due before today)
            overdue_tasks = task_service.list_user_tasks_overdue(
                db=db,
                org_id=org.id,
                today=today,
            )

            for task in overdue_tasks:
                tasks_overdue += 1
                notification_service.notify_task_overdue(
                    db=db,
                    task_id=task.id,
                    task_title=task.title,
                    org_id=task.organization_id,
                    assignee_id=task.owner_id,
                    due_date=task.due_date.strftime("%Y-%m-%d"),
                    case_number=task.case.case_number if task.case else None,
                )
                notifications_created += 1

    return TaskNotificationsResponse(
        tasks_due_soon=tasks_due_soon,
        tasks_overdue=tasks_overdue,
        notifications_created=notifications_created,
    )


# =============================================================================
# Meta Sync Scheduled Jobs
# =============================================================================


class MetaHierarchySyncResponse(BaseModel):
    ad_accounts_processed: int
    jobs_created: int


@router.post("/meta-hierarchy-sync", response_model=MetaHierarchySyncResponse)
def meta_hierarchy_sync(x_internal_secret: str = Header(...)):
    """
    Schedule Meta hierarchy sync jobs for all active ad accounts.

    Called by external cron (every 6-12 hours recommended).
    Syncs campaign/adset/ad hierarchy using delta sync (updated_time filter).
    """
    verify_internal_secret(x_internal_secret)

    from app.db.models import MetaAdAccount

    ad_accounts_processed = 0
    jobs_created = 0

    with SessionLocal() as db:
        # Get all active ad accounts across all orgs
        ad_accounts = (
            db.query(MetaAdAccount)
            .filter(MetaAdAccount.is_active.is_(True))
            .all()
        )

        for ad_account in ad_accounts:
            job_service.schedule_job(
                db=db,
                job_type=JobType.META_HIERARCHY_SYNC,
                org_id=ad_account.organization_id,
                payload={
                    "ad_account_id": str(ad_account.id),
                    "full_sync": False,  # Delta sync by default
                },
            )
            ad_accounts_processed += 1
            jobs_created += 1

        db.commit()

    return MetaHierarchySyncResponse(
        ad_accounts_processed=ad_accounts_processed,
        jobs_created=jobs_created,
    )


class MetaSpendSyncResponse(BaseModel):
    ad_accounts_processed: int
    jobs_created: int


@router.post("/meta-spend-sync", response_model=MetaSpendSyncResponse)
def meta_spend_sync(
    x_internal_secret: str = Header(...),
    sync_type: str = "daily",
):
    """
    Schedule Meta spend sync jobs for all active ad accounts.

    Called by external cron (daily recommended).

    Args:
        sync_type: 'daily' (yesterday + 7-day rolling), 'weekly' (90-day backfill),
                   'initial' (180-day backfill for new accounts)
    """
    verify_internal_secret(x_internal_secret)

    from app.db.models import MetaAdAccount

    ad_accounts_processed = 0
    jobs_created = 0

    with SessionLocal() as db:
        ad_accounts = (
            db.query(MetaAdAccount)
            .filter(MetaAdAccount.is_active.is_(True))
            .all()
        )

        for ad_account in ad_accounts:
            job_service.schedule_job(
                db=db,
                job_type=JobType.META_SPEND_SYNC,
                org_id=ad_account.organization_id,
                payload={
                    "ad_account_id": str(ad_account.id),
                    "sync_type": sync_type,
                },
            )
            ad_accounts_processed += 1
            jobs_created += 1

        db.commit()

    return MetaSpendSyncResponse(
        ad_accounts_processed=ad_accounts_processed,
        jobs_created=jobs_created,
    )


class MetaFormsSyncResponse(BaseModel):
    pages_processed: int
    jobs_created: int


@router.post("/meta-forms-sync", response_model=MetaFormsSyncResponse)
def meta_forms_sync(x_internal_secret: str = Header(...)):
    """
    Schedule Meta forms sync jobs for all active page mappings.

    Called by external cron (nightly/weekly recommended).
    Syncs form metadata with versioning (uses PAGE tokens, not ad account tokens).
    """
    verify_internal_secret(x_internal_secret)

    pages_processed = 0
    jobs_created = 0

    with SessionLocal() as db:
        # Get all active page mappings (forms sync uses page tokens)
        mappings = meta_page_service.list_active_mappings(db)

        # Group by org to create one job per org
        orgs_with_pages: dict = {}
        for mapping in mappings:
            org_id = mapping.organization_id
            if org_id not in orgs_with_pages:
                orgs_with_pages[org_id] = []
            orgs_with_pages[org_id].append(mapping.page_id)
            pages_processed += 1

        # Schedule one job per org (covers all pages in that org)
        for org_id, page_ids in orgs_with_pages.items():
            job_service.schedule_job(
                db=db,
                job_type=JobType.META_FORM_SYNC,
                org_id=org_id,
                payload={
                    "page_ids": page_ids,
                },
            )
            jobs_created += 1

        db.commit()

    return MetaFormsSyncResponse(
        pages_processed=pages_processed,
        jobs_created=jobs_created,
    )
