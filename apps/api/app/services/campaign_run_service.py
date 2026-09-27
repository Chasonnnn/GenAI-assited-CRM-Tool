"""Campaign scheduling, cancellation, retries, and run reads."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.enums import CampaignRecipientStatus, CampaignStatus, EmailStatus, JobStatus, JobType
from app.db.models import (
    Campaign,
    CampaignRecipient,
    CampaignRun,
    EmailTemplate,
    Job,
    MessageDelivery,
)
from app.schemas.campaign import (
    CampaignRunResponse,
)
from app.services import (
    campaign_access,
    campaign_audience,
    campaign_content,
    campaign_delivery_service,
)

EMPTY_RUN_STATISTICS = {
    key: 0
    for key in (
        "total_count",
        "sent_count",
        "delivered_count",
        "failed_count",
        "skipped_count",
        "opened_count",
        "clicked_count",
    )
}


def ensure_future_datetime(value: datetime | None, field_name: str) -> None:
    """Ensure a datetime is in the future (UTC)."""
    if not value:
        return
    now = datetime.now(UTC)
    candidate = value if value.tzinfo else value.replace(tzinfo=UTC)
    if candidate <= now:
        raise ValueError(f"{field_name} must be in the future")


def enqueue_campaign_send(
    db: Session, org_id: UUID, campaign_id: UUID, user_id: UUID, send_now: bool = True
) -> tuple[str, UUID | None, datetime | None]:
    """
    Enqueue a campaign for sending.

    Returns: (message, run_id or None, scheduled_at or None)
    """
    from app.services import email_provider_service, permission_policy_service

    permission_policy_service.lock_configuration(db, org_id)
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == org_id,
        )
        .with_for_update()
        .first()
    )

    if not campaign:
        raise ValueError("Campaign not found")
    campaign_access.validate_template_scope(db, campaign)
    authority_snapshot = campaign_access.authorize_send(db, campaign, user_id)
    campaign_access.audit(db, campaign, user_id, "send")

    campaign_audience.ensure_supported_campaign_channel(campaign.channel, campaign.recipient_type)

    if campaign.status not in [
        CampaignStatus.DRAFT.value,
        CampaignStatus.SCHEDULED.value,
    ]:
        raise ValueError(f"Cannot send campaign in '{campaign.status}' status")

    provider_type: str | None = None
    template_snapshot: dict | None = None
    message_template_version_id: UUID | None = None
    if campaign.channel == "email":
        try:
            provider_type, provider_config = email_provider_service.resolve_campaign_provider(
                db, org_id
            )
        except email_provider_service.ConfigurationError as e:
            raise ValueError(str(e))

        template = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.id == campaign.email_template_id,
                EmailTemplate.organization_id == org_id,
            )
            .with_for_update()
            .first()
        )
        if template is None:
            raise ValueError("Email template not found")
        template_snapshot = campaign_content.snapshot_campaign_template(template, provider_config)
    else:
        if campaign.include_unsubscribed:
            raise ValueError("include_unsubscribed is not available for messaging campaigns")
        message_template = campaign_content.load_published_message_template(
            db,
            org_id=org_id,
            template_version_id=campaign.message_template_version_id,
            lock=True,
        )
        message_template_version_id = message_template.id

    if send_now:
        # Create run immediately with locked provider
        run = CampaignRun(
            organization_id=org_id,
            campaign_id=campaign.id,
            authority_snapshot=authority_snapshot,
            status="running",
            email_provider=provider_type,  # Lock provider at creation
            email_template_snapshot=template_snapshot,
            message_template_version_id=message_template_version_id,
            total_count=0,
            sent_count=0,
            delivered_count=0,
            failed_count=0,
            skipped_count=0,
        )
        db.add(run)
        db.flush()

        # Update campaign status
        campaign.status = CampaignStatus.SENDING.value
        campaign.scheduled_at = None

        # Create job for async processing
        job = Job(
            organization_id=org_id,
            job_type=JobType.CAMPAIGN_SEND.value,
            status=JobStatus.PENDING.value,
            payload={
                "campaign_id": str(campaign.id),
                "run_id": str(run.id),
                "user_id": str(user_id),
            },
            idempotency_key=f"campaign:{campaign.id}:run:{run.id}",
        )
        db.add(job)
        db.flush()

        return "Campaign queued for sending", run.id, None

    if not campaign.scheduled_at:
        raise ValueError("scheduled_at is required when send_now is false")
    ensure_future_datetime(campaign.scheduled_at, "scheduled_at")

    # Schedule for later - still create the run and job, but with run_at
    run = CampaignRun(
        organization_id=org_id,
        campaign_id=campaign.id,
        authority_snapshot=authority_snapshot,
        status="running",
        email_provider=provider_type,  # Lock provider at creation
        email_template_snapshot=template_snapshot,
        message_template_version_id=message_template_version_id,
        total_count=0,
        sent_count=0,
        delivered_count=0,
        failed_count=0,
        skipped_count=0,
    )
    db.add(run)
    db.flush()

    campaign.status = CampaignStatus.SCHEDULED.value

    # Create job scheduled for future execution
    job = Job(
        organization_id=org_id,
        job_type=JobType.CAMPAIGN_SEND.value,
        status=JobStatus.PENDING.value,
        payload={
            "campaign_id": str(campaign.id),
            "run_id": str(run.id),
            "user_id": str(user_id),
        },
        idempotency_key=f"campaign:{campaign.id}:run:{run.id}",
        run_at=campaign.scheduled_at,  # Run at scheduled time
    )
    db.add(job)
    db.flush()

    return "Campaign scheduled", run.id, campaign.scheduled_at


def enqueue_campaign_retry_failed(
    db: Session,
    org_id: UUID,
    campaign_id: UUID,
    run_id: UUID,
    user_id: UUID,
) -> tuple[str, UUID, UUID | None, int]:
    """Enqueue a retry for failed recipients in a run."""
    from app.services import permission_policy_service

    permission_policy_service.lock_configuration(db, org_id)
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == org_id,
        )
        .first()
    )
    if not campaign:
        raise ValueError("Campaign not found")
    if campaign.status == CampaignStatus.CANCELLED.value:
        raise ValueError("Cannot retry a cancelled campaign")
    if campaign.channel == "messaging":
        raise ValueError("Messaging delivery retries are managed by the durable messaging outbox")
    campaign_access.validate_template_scope(db, campaign)
    authority_snapshot = campaign_access.authorize_send(db, campaign, user_id)
    campaign_access.audit(db, campaign, user_id, "send")

    run = (
        db.query(CampaignRun)
        .filter(
            CampaignRun.organization_id == org_id,
            CampaignRun.id == run_id,
            CampaignRun.campaign_id == campaign_id,
        )
        .first()
    )
    if not run:
        raise ValueError("Run not found")

    if campaign_access.enabled(db, org_id):
        run.authority_snapshot = authority_snapshot

    failed_count = (
        db.scalar(
            select(func.count(CampaignRecipient.id)).where(
                CampaignRecipient.run_id == run_id,
                CampaignRecipient.entity_type == campaign.recipient_type,
                CampaignRecipient.status == CampaignRecipientStatus.FAILED.value,
            )
        )
        or 0
    )
    if failed_count == 0:
        raise ValueError("No failed recipients to retry")

    existing = (
        db.query(Job)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == JobType.CAMPAIGN_SEND.value,
            Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]),
            Job.payload["run_id"].astext == str(run_id),
            Job.payload["retry_failed_only"].astext == "true",
        )
        .first()
    )
    if existing:
        return "Retry already queued", run_id, existing.id, failed_count

    job = Job(
        organization_id=org_id,
        job_type=JobType.CAMPAIGN_SEND.value,
        status=JobStatus.PENDING.value,
        payload={
            "campaign_id": str(campaign_id),
            "run_id": str(run_id),
            "user_id": str(user_id),
            "retry_failed_only": True,
        },
        idempotency_key=None,
    )
    db.add(job)
    db.flush()

    run.status = "running"
    campaign.status = CampaignStatus.SENDING.value

    return "Retry queued", run_id, job.id, failed_count


def cancel_campaign(db: Session, org_id: UUID, campaign_id: UUID) -> bool:
    """Cancel a scheduled campaign."""
    from app.services import permission_policy_service

    permission_policy_service.lock_configuration(db, org_id)
    from app.db.enums import EmailDeliveryStatus
    from app.db.models import EmailDelivery, EmailLog

    latest_run_id = (
        db.query(CampaignRun.id)
        .filter(
            CampaignRun.organization_id == org_id,
            CampaignRun.campaign_id == campaign_id,
        )
        .order_by(CampaignRun.started_at.desc())
        .first()
    )
    latest_run = None
    if latest_run_id is not None:
        locked = campaign_delivery_service.lock_campaign_run_and_campaign(
            db,
            organization_id=org_id,
            run_id=latest_run_id[0],
        )
        if locked is None:
            return False
        latest_run, campaign = locked
    else:
        campaign = (
            db.query(Campaign)
            .filter(
                Campaign.id == campaign_id,
                Campaign.organization_id == org_id,
            )
            .with_for_update(of=Campaign)
            .populate_existing()
            .one_or_none()
        )

    if campaign is None or campaign.status not in {
        CampaignStatus.SCHEDULED.value,
        CampaignStatus.SENDING.value,
    }:
        return False

    campaign.status = CampaignStatus.CANCELLED.value
    campaign.scheduled_at = None

    now = datetime.now(UTC)
    if latest_run and latest_run.status != "completed":
        latest_run.status = "failed"
        latest_run.error_message = "cancelled"
        latest_run.completed_at = now

        if campaign.channel == "messaging":
            cancellable_messages = (
                db.query(MessageDelivery, CampaignRecipient)
                .join(
                    CampaignRecipient,
                    CampaignRecipient.message_delivery_id == MessageDelivery.id,
                )
                .filter(
                    MessageDelivery.organization_id == org_id,
                    CampaignRecipient.run_id == latest_run.id,
                    MessageDelivery.status.in_(("pending", "retry_scheduled")),
                )
                .with_for_update(of=MessageDelivery)
                .all()
            )
            for delivery, recipient in cancellable_messages:
                delivery.status = "cancelled"
                delivery.completed_at = now
                delivery.last_error_type = "campaign_cancelled"
                delivery.last_error = "cancelled"
                recipient.status = CampaignRecipientStatus.SKIPPED.value
                recipient.error = None
                recipient.skip_reason = "cancelled"
        else:
            cancellable_deliveries = (
                db.query(EmailDelivery, EmailLog, CampaignRecipient)
                .join(
                    EmailLog,
                    EmailLog.id == EmailDelivery.email_log_id,
                )
                .join(
                    CampaignRecipient,
                    or_(
                        CampaignRecipient.email_log_id == EmailLog.id,
                        and_(
                            EmailLog.source_type == "campaign_recipient",
                            EmailLog.source_id == CampaignRecipient.id,
                        ),
                    ),
                )
                .filter(
                    EmailDelivery.organization_id == org_id,
                    EmailLog.organization_id == org_id,
                    CampaignRecipient.run_id == latest_run.id,
                    EmailDelivery.status.in_(
                        [
                            EmailDeliveryStatus.PENDING.value,
                            EmailDeliveryStatus.RETRY_SCHEDULED.value,
                        ]
                    ),
                )
                .with_for_update(of=EmailDelivery)
                .all()
            )
            for delivery, email_log, recipient in cancellable_deliveries:
                delivery.status = EmailDeliveryStatus.CANCELLED.value
                delivery.completed_at = now
                delivery.last_error_type = "campaign_cancelled"
                delivery.last_error = "cancelled"
                email_log.status = EmailStatus.SKIPPED.value
                email_log.error = "cancelled"
                recipient.status = CampaignRecipientStatus.SKIPPED.value
                recipient.error = None
                recipient.skip_reason = "cancelled"

    pending_jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == JobType.CAMPAIGN_SEND.value,
            Job.status == JobStatus.PENDING.value,
            Job.payload["campaign_id"].astext == str(campaign_id),
        )
        .all()
    )
    for job in pending_jobs:
        job.status = JobStatus.FAILED.value
        job.last_error = "cancelled"
        job.completed_at = now

    if latest_run is not None:
        campaign_delivery_service.recompute_campaign_run_aggregates(
            db,
            organization_id=org_id,
            run_id=latest_run.id,
            commit=False,
        )

    return True


def viewer_run_statistics(db, org_id, run_ids, viewer_session) -> dict:
    if not run_ids:
        return {}
    recipient = CampaignRecipient
    query = (
        db.query(
            recipient.run_id,
            func.count(recipient.id).label("total_count"),
            func.count(recipient.id)
            .filter(recipient.status.in_(("sent", "delivered")))
            .label("sent_count"),
            func.count(recipient.id)
            .filter(recipient.status == "delivered")
            .label("delivered_count"),
            func.count(recipient.id).filter(recipient.status == "failed").label("failed_count"),
            func.count(recipient.id).filter(recipient.status == "skipped").label("skipped_count"),
            func.count(recipient.id).filter(recipient.opened_at.is_not(None)).label("opened_count"),
            func.count(recipient.id)
            .filter(recipient.clicked_at.is_not(None))
            .label("clicked_count"),
        )
        .join(CampaignRun, CampaignRun.id == recipient.run_id)
        .join(Campaign, Campaign.id == CampaignRun.campaign_id)
        .filter(
            CampaignRun.organization_id == org_id,
            Campaign.organization_id == org_id,
            recipient.run_id.in_(run_ids),
            recipient.entity_type == Campaign.recipient_type,
            campaign_access.visible_filter(db, viewer_session),
            campaign_access.viewer_recipient_filter(db, viewer_session, org_id),
        )
        .group_by(recipient.run_id)
    )
    return {
        row.run_id: {key: row._mapping[key] for key in EMPTY_RUN_STATISTICS} for row in query.all()
    }


def campaign_run_response(db, run, viewer_session=None) -> CampaignRunResponse:
    response = CampaignRunResponse.model_validate(run)
    if viewer_session is not None and campaign_access.enabled(db, run.organization_id):
        counts = viewer_run_statistics(db, run.organization_id, [run.id], viewer_session)
        response = response.model_copy(update=counts.get(run.id, EMPTY_RUN_STATISTICS))
    return response


def list_campaign_runs(
    db: Session, org_id: UUID, campaign_id: UUID, limit: int = 20, *, viewer_session=None
) -> list[CampaignRunResponse]:
    """List runs for a campaign."""
    runs = (
        db.query(CampaignRun)
        .filter(
            CampaignRun.organization_id == org_id,
            CampaignRun.campaign_id == campaign_id,
        )
        .order_by(CampaignRun.started_at.desc())
        .limit(limit)
        .all()
    )

    stats = (
        viewer_run_statistics(db, org_id, [run.id for run in runs], viewer_session)
        if viewer_session is not None and campaign_access.enabled(db, org_id)
        else None
    )
    return [
        CampaignRunResponse.model_validate(run).model_copy(
            update=stats.get(run.id, EMPTY_RUN_STATISTICS)
        )
        if stats is not None
        else CampaignRunResponse.model_validate(run)
        for run in runs
    ]


def get_campaign_run(db: Session, org_id: UUID, run_id: UUID) -> CampaignRun | None:
    """Get a campaign run with recipients."""
    return (
        db.query(CampaignRun)
        .filter(CampaignRun.id == run_id, CampaignRun.organization_id == org_id)
        .first()
    )


def list_run_recipients(
    db: Session,
    run_id: UUID,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    *,
    org_id: UUID | None = None,
    viewer_session=None,
) -> list[CampaignRecipient]:
    """List recipients for a campaign run."""
    query = db.query(CampaignRecipient).filter(CampaignRecipient.run_id == run_id)

    if viewer_session is not None:
        query = (
            query.join(CampaignRun, CampaignRun.id == CampaignRecipient.run_id)
            .join(Campaign, Campaign.id == CampaignRun.campaign_id)
            .filter(
                CampaignRun.organization_id == org_id,
                Campaign.organization_id == org_id,
                CampaignRecipient.entity_type == Campaign.recipient_type,
            )
        )
        if campaign_access.enabled(db, org_id):
            query = query.filter(
                campaign_access.visible_filter(db, viewer_session),
                campaign_access.viewer_recipient_filter(db, viewer_session, org_id),
            )

    if status:
        query = query.filter(CampaignRecipient.status == status)

    return query.order_by(CampaignRecipient.created_at.desc()).offset(offset).limit(limit).all()


def get_latest_run_for_campaign(
    db: Session,
    campaign_id: UUID,
    *,
    org_id: UUID | None = None,
) -> CampaignRun | None:
    """Fetch the latest run for a campaign."""
    query = db.query(CampaignRun).filter(CampaignRun.campaign_id == campaign_id)
    if org_id is not None:
        query = query.filter(CampaignRun.organization_id == org_id)
    return query.order_by(CampaignRun.started_at.desc()).first()
