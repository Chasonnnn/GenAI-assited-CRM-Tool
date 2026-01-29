"""Campaign service for bulk email management."""

import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Campaign,
    CampaignRun,
    CampaignRecipient,
    EmailSuppression,
    EmailTemplate,
    Surrogate,
    IntendedParent,
    Job,
    PipelineStage,
)
from app.db.enums import CampaignStatus, CampaignRecipientStatus, JobType, JobStatus, EmailStatus
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignListItem,
    CampaignRunResponse,
    CampaignPreviewResponse,
    RecipientPreview,
    FilterCriteria,
)


CAMPAIGN_SEND_BATCH_SIZE = int(os.getenv("CAMPAIGN_SEND_BATCH_SIZE", "200"))


# =============================================================================
# Campaign CRUD
# =============================================================================


def list_campaigns(
    db: Session,
    org_id: UUID,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CampaignListItem], int]:
    """List campaigns for an organization with optimized run stats query."""
    # Base query for count
    base_query = db.query(Campaign).filter(Campaign.organization_id == org_id)

    if status:
        base_query = base_query.filter(Campaign.status == status)

    total = base_query.count()

    # Subquery: Get latest run per campaign using window function
    # This avoids N+1 queries by fetching all latest runs in one query
    run_subq = (
        db.query(
            CampaignRun.campaign_id,
            CampaignRun.total_count,
            CampaignRun.sent_count,
            CampaignRun.failed_count,
            CampaignRun.opened_count,
            CampaignRun.clicked_count,
            func.row_number()
            .over(
                partition_by=CampaignRun.campaign_id,
                order_by=CampaignRun.started_at.desc(),
            )
            .label("rn"),
        )
        .filter(CampaignRun.organization_id == org_id)
        .subquery()
    )

    # Main query with LEFT JOIN to latest run stats
    query = (
        db.query(
            Campaign,
            run_subq.c.total_count,
            run_subq.c.sent_count,
            run_subq.c.failed_count,
            run_subq.c.opened_count,
            run_subq.c.clicked_count,
        )
        .outerjoin(
            run_subq,
            (Campaign.id == run_subq.c.campaign_id) & (run_subq.c.rn == 1),
        )
        .filter(Campaign.organization_id == org_id)
        .options(joinedload(Campaign.email_template))
    )

    if status:
        query = query.filter(Campaign.status == status)

    rows = query.order_by(Campaign.created_at.desc()).offset(offset).limit(limit).all()

    # Build result from joined data
    result = []
    for row in rows:
        c = row[0]  # Campaign object
        result.append(
            CampaignListItem(
                id=c.id,
                name=c.name,
                email_template_name=c.email_template.name if c.email_template else None,
                recipient_type=c.recipient_type,
                status=c.status,
                scheduled_at=c.scheduled_at,
                total_recipients=row.total_count or 0,
                sent_count=row.sent_count or 0,
                failed_count=row.failed_count or 0,
                opened_count=row.opened_count or 0,
                clicked_count=row.clicked_count or 0,
                created_at=c.created_at,
            )
        )

    return result, total


def get_campaign(db: Session, org_id: UUID, campaign_id: UUID) -> Campaign | None:
    """Get a campaign by ID."""
    return (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.organization_id == org_id)
        .options(joinedload(Campaign.email_template), joinedload(Campaign.created_by))
        .first()
    )


def create_campaign(db: Session, org_id: UUID, user_id: UUID, data: CampaignCreate) -> Campaign:
    """Create a new campaign."""
    # Verify template exists
    template = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == data.email_template_id,
            EmailTemplate.organization_id == org_id,
        )
        .first()
    )

    if not template:
        raise ValueError("Email template not found")

    campaign = Campaign(
        organization_id=org_id,
        name=data.name,
        description=data.description,
        email_template_id=data.email_template_id,
        recipient_type=data.recipient_type,
        filter_criteria=data.filter_criteria.model_dump(mode="json")
        if data.filter_criteria
        else {},
        scheduled_at=data.scheduled_at,
        status=CampaignStatus.DRAFT.value,
        created_by_user_id=user_id,
    )
    db.add(campaign)
    db.flush()

    return campaign


def update_campaign(
    db: Session, org_id: UUID, campaign_id: UUID, data: CampaignUpdate
) -> Campaign | None:
    """Update a campaign (only drafts can be updated)."""
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == org_id,
            Campaign.status == CampaignStatus.DRAFT.value,
        )
        .first()
    )

    if not campaign:
        return None

    if data.name is not None:
        campaign.name = data.name
    if data.description is not None:
        campaign.description = data.description
    if data.email_template_id is not None:
        # SECURITY: Validate template belongs to org before updating
        template = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.id == data.email_template_id,
                EmailTemplate.organization_id == org_id,
            )
            .first()
        )
        if not template:
            raise ValueError("Email template not found")
        campaign.email_template_id = data.email_template_id
    if data.recipient_type is not None:
        campaign.recipient_type = data.recipient_type
    if data.filter_criteria is not None:
        campaign.filter_criteria = data.filter_criteria.model_dump(mode="json")
    if data.scheduled_at is not None:
        campaign.scheduled_at = data.scheduled_at

    db.flush()
    return campaign


def delete_campaign(db: Session, org_id: UUID, campaign_id: UUID) -> bool:
    """Delete a campaign (only drafts can be deleted)."""
    result = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == org_id,
            Campaign.status == CampaignStatus.DRAFT.value,
        )
        .delete()
    )

    return result > 0


# =============================================================================
# Recipient Filtering
# =============================================================================


def _build_recipient_query(db: Session, org_id: UUID, recipient_type: str, filter_criteria: dict):
    """Build SQLAlchemy query for recipients based on filter criteria."""
    criteria = FilterCriteria(**filter_criteria) if filter_criteria else FilterCriteria()

    if recipient_type == "case":
        query = db.query(Surrogate).filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            Surrogate.email.isnot(None),
            Surrogate.email != "",
        )

        if criteria.stage_ids:
            query = query.filter(Surrogate.stage_id.in_(criteria.stage_ids))

        if criteria.stage_slugs:
            # IMPORTANT: Scope stages to org's pipelines to prevent cross-tenant leakage
            from app.db.models import Pipeline

            stage_ids = (
                db.query(PipelineStage.id)
                .join(Pipeline, PipelineStage.pipeline_id == Pipeline.id)
                .filter(
                    Pipeline.organization_id == org_id,
                    PipelineStage.slug.in_(criteria.stage_slugs),
                )
                .all()
            )
            query = query.filter(Surrogate.stage_id.in_([s.id for s in stage_ids]))

        if criteria.states:
            query = query.filter(Surrogate.state.in_(criteria.states))

        if criteria.created_after:
            query = query.filter(Surrogate.created_at >= criteria.created_after)

        if criteria.created_before:
            query = query.filter(Surrogate.created_at <= criteria.created_before)

        if criteria.source:
            query = query.filter(Surrogate.source == criteria.source)

        if criteria.is_priority is not None:
            query = query.filter(Surrogate.is_priority == criteria.is_priority)

        return query

    elif recipient_type == "intended_parent":
        query = db.query(IntendedParent).filter(
            IntendedParent.organization_id == org_id,
            IntendedParent.email.isnot(None),
            IntendedParent.email != "",
            IntendedParent.is_archived.is_(False),  # Exclude archived IPs
        )

        if criteria.stage_slugs:
            query = query.filter(IntendedParent.status.in_(criteria.stage_slugs))

        if criteria.created_after:
            query = query.filter(IntendedParent.created_at >= criteria.created_after)

        if criteria.created_before:
            query = query.filter(IntendedParent.created_at <= criteria.created_before)

        return query

    raise ValueError(f"Unknown recipient type: {recipient_type}")


def _load_suppressed_emails(db: Session, org_id: UUID) -> set[str]:
    rows = db.query(EmailSuppression.email).filter(EmailSuppression.organization_id == org_id).all()
    return {row.email.lower() for row in rows if row.email}


def _load_existing_recipients(
    db: Session,
    run_id: UUID,
    entity_type: str,
    entity_ids: list[UUID],
) -> dict[UUID, CampaignRecipient]:
    if not entity_ids:
        return {}
    recipients = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.run_id == run_id,
            CampaignRecipient.entity_type == entity_type,
            CampaignRecipient.entity_id.in_(entity_ids),
        )
        .all()
    )
    return {recipient.entity_id: recipient for recipient in recipients}


def preview_recipients(
    db: Session,
    org_id: UUID,
    recipient_type: str,
    filter_criteria: dict,
    limit: int = 50,
) -> CampaignPreviewResponse:
    """Preview recipients matching the filter criteria."""
    query = _build_recipient_query(db, org_id, recipient_type, filter_criteria)

    total_count = query.count()
    entities = query.limit(limit).all()

    # Get suppressed emails for this org (handle SA 2.0 Row objects)
    suppression_rows = (
        db.query(EmailSuppression.email).filter(EmailSuppression.organization_id == org_id).all()
    )
    suppressed = {row[0].lower() for row in suppression_rows if row[0]}

    recipients = []
    for entity in entities:
        email = entity.email.lower() if entity.email else ""
        if email in suppressed:
            continue  # Skip suppressed

        if recipient_type == "case":
            stage = db.query(PipelineStage).filter(PipelineStage.id == entity.stage_id).first()
            recipients.append(
                RecipientPreview(
                    entity_type="case",
                    entity_id=entity.id,
                    email=entity.email,
                    name=entity.full_name,
                    stage=stage.label if stage else None,
                )
            )
        else:
            recipients.append(
                RecipientPreview(
                    entity_type="intended_parent",
                    entity_id=entity.id,
                    email=entity.email,
                    name=entity.full_name,
                    stage=None,
                )
            )

    return CampaignPreviewResponse(total_count=total_count, sample_recipients=recipients[:limit])


# =============================================================================
# Sending
# =============================================================================


def enqueue_campaign_send(
    db: Session, org_id: UUID, campaign_id: UUID, user_id: UUID, send_now: bool = True
) -> tuple[str, UUID | None, datetime | None]:
    """
    Enqueue a campaign for sending.

    Returns: (message, run_id or None, scheduled_at or None)
    """
    from app.services import email_provider_service

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

    if campaign.status not in [
        CampaignStatus.DRAFT.value,
        CampaignStatus.SCHEDULED.value,
    ]:
        raise ValueError(f"Cannot send campaign in '{campaign.status}' status")

    # Validate and lock email provider at run creation time
    try:
        provider_type, _ = email_provider_service.resolve_campaign_provider(db, org_id)
    except email_provider_service.ConfigurationError as e:
        raise ValueError(str(e))

    if send_now:
        # Create run immediately with locked provider
        run = CampaignRun(
            organization_id=org_id,
            campaign_id=campaign.id,
            status="running",
            email_provider=provider_type,  # Lock provider at creation
            total_count=0,
            sent_count=0,
            failed_count=0,
            skipped_count=0,
        )
        db.add(run)
        db.flush()

        # Update campaign status
        campaign.status = CampaignStatus.SCHEDULED.value

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

    # Schedule for later - still create the run and job, but with run_at
    run = CampaignRun(
        organization_id=org_id,
        campaign_id=campaign.id,
        status="running",
        email_provider=provider_type,  # Lock provider at creation
        total_count=0,
        sent_count=0,
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

    failed_count = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.run_id == run_id,
            CampaignRecipient.status == CampaignRecipientStatus.FAILED.value,
        )
        .count()
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
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == org_id,
            Campaign.status == CampaignStatus.SCHEDULED.value,
        )
        .first()
    )

    if not campaign:
        return False

    campaign.status = CampaignStatus.CANCELLED.value
    return True


# =============================================================================
# Runs
# =============================================================================


def list_campaign_runs(
    db: Session, org_id: UUID, campaign_id: UUID, limit: int = 20
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

    return [CampaignRunResponse.model_validate(r) for r in runs]


def get_campaign_run(db: Session, org_id: UUID, run_id: UUID) -> CampaignRun | None:
    """Get a campaign run with recipients."""
    return (
        db.query(CampaignRun)
        .filter(CampaignRun.id == run_id, CampaignRun.organization_id == org_id)
        .options(joinedload(CampaignRun.recipients))
        .first()
    )


def list_run_recipients(
    db: Session,
    run_id: UUID,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[CampaignRecipient]:
    """List recipients for a campaign run."""
    query = db.query(CampaignRecipient).filter(CampaignRecipient.run_id == run_id)

    if status:
        query = query.filter(CampaignRecipient.status == status)

    return query.order_by(CampaignRecipient.created_at.desc()).offset(offset).limit(limit).all()


def get_latest_run_for_campaign(
    db: Session,
    campaign_id: UUID,
) -> CampaignRun | None:
    """Fetch the latest run for a campaign."""
    return (
        db.query(CampaignRun)
        .filter(CampaignRun.campaign_id == campaign_id)
        .order_by(CampaignRun.started_at.desc())
        .first()
    )


# =============================================================================
# Suppression
# =============================================================================


def is_email_suppressed(db: Session, org_id: UUID, email: str) -> bool:
    """Check if an email is in the suppression list."""
    return (
        db.query(EmailSuppression)
        .filter(
            EmailSuppression.organization_id == org_id,
            EmailSuppression.email == email.lower(),
        )
        .first()
        is not None
    )


def add_to_suppression(
    db: Session,
    org_id: UUID,
    email: str,
    reason: str,
    source_type: str | None = None,
    source_id: UUID | None = None,
) -> EmailSuppression:
    """Add an email to the suppression list (idempotent)."""
    existing = (
        db.query(EmailSuppression)
        .filter(
            EmailSuppression.organization_id == org_id,
            EmailSuppression.email == email.lower(),
        )
        .first()
    )

    if existing:
        return existing

    suppression = EmailSuppression(
        organization_id=org_id,
        email=email.lower(),
        reason=reason,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(suppression)
    db.flush()

    return suppression


def list_suppressions(
    db: Session, org_id: UUID, limit: int = 100, offset: int = 0
) -> tuple[list[EmailSuppression], int]:
    """List suppressed emails for an organization."""
    query = db.query(EmailSuppression).filter(EmailSuppression.organization_id == org_id)

    total = query.count()
    items = query.order_by(EmailSuppression.created_at.desc()).offset(offset).limit(limit).all()

    return items, total


def remove_from_suppression(db: Session, org_id: UUID, email: str) -> bool:
    """Remove an email from the suppression list."""
    result = (
        db.query(EmailSuppression)
        .filter(
            EmailSuppression.organization_id == org_id,
            EmailSuppression.email == email.lower(),
        )
        .delete()
    )

    return result > 0


# =============================================================================
# Campaign Execution
# =============================================================================


def execute_campaign_run(
    db: Session,
    org_id: UUID,
    campaign_id: UUID,
    run_id: UUID,
) -> dict:
    """
    Execute a campaign run - send emails to all recipients.

    This is called by the worker for async processing.
    Recipients are filtered, emails are sent individually, and status is tracked.

    Returns:
        dict with sent_count, failed_count, skipped_count
    """
    from app.services import email_service

    # Get campaign
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == org_id,
        )
        .first()
    )

    if not campaign:
        raise Exception(f"Campaign {campaign_id} not found")

    # Get run
    run = (
        db.query(CampaignRun)
        .filter(
            CampaignRun.id == run_id,
            CampaignRun.campaign_id == campaign_id,
        )
        .first()
    )

    if not run:
        raise Exception(f"Campaign run {run_id} not found")

    # Get template
    template = (
        db.query(EmailTemplate).filter(EmailTemplate.id == campaign.email_template_id).first()
    )

    if not template:
        raise Exception(f"Email template {campaign.email_template_id} not found")

    if run.status == "completed":
        return {
            "sent_count": run.sent_count,
            "failed_count": run.failed_count,
            "skipped_count": run.skipped_count,
            "total_count": run.total_count,
        }

    # Mark campaign as sending
    campaign.status = CampaignStatus.SENDING.value
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    db.commit()

    recipient_query = _build_recipient_query(
        db, org_id, campaign.recipient_type, campaign.filter_criteria or {}
    )
    if campaign.recipient_type == "case":
        email_col = Surrogate.email
        id_col = Surrogate.id
    else:
        email_col = IntendedParent.email
        id_col = IntendedParent.id

    recipient_query = recipient_query.order_by(func.lower(email_col), id_col)
    run.total_count = recipient_query.count()
    db.commit()

    seen_emails: dict[str, str | None] = {}
    suppressed_emails = _load_suppressed_emails(db, org_id)

    def _mark_skipped(existing_recipient, reason, email, name, entity_id):
        if not existing_recipient:
            existing_recipient = CampaignRecipient(
                run_id=run_id,
                entity_type=campaign.recipient_type,
                entity_id=entity_id,
                recipient_email=email,
                recipient_name=name,
                status=CampaignRecipientStatus.SKIPPED.value,
                skip_reason=reason,
            )
            db.add(existing_recipient)
            return
        if existing_recipient.status not in (
            CampaignRecipientStatus.SENT.value,
            CampaignRecipientStatus.SKIPPED.value,
        ):
            existing_recipient.status = CampaignRecipientStatus.SKIPPED.value
            existing_recipient.skip_reason = reason

    batch_size = max(1, CAMPAIGN_SEND_BATCH_SIZE)
    recipients_buffer = []
    recipient_iter = recipient_query.execution_options(stream_results=True).yield_per(batch_size)

    def _process_batch(batch):
        entity_ids = [recipient.id for recipient in batch]
        existing_by_entity = _load_existing_recipients(
            db,
            run_id,
            campaign.recipient_type,
            entity_ids,
        )

        for recipient in batch:
            # Get email and name
            if campaign.recipient_type == "case":
                email = recipient.email
                name = recipient.full_name or recipient.first_name
                entity_id = recipient.id
            else:  # intended_parent
                email = recipient.email
                name = recipient.full_name or recipient.first_name
                entity_id = recipient.id

            if not email:
                continue

            email_norm = email.strip().lower()
            if not email_norm:
                continue

            existing = existing_by_entity.get(entity_id)

            if email_norm in seen_emails:
                skip_reason = seen_emails[email_norm] or "duplicate_email"
                _mark_skipped(existing, skip_reason, email, name, entity_id)
                continue

            # Check suppression
            if email_norm in suppressed_emails:
                seen_emails[email_norm] = "suppressed"
                _mark_skipped(existing, "suppressed", email, name, entity_id)
                continue

            seen_emails[email_norm] = None

            # Build email from template with shared variable builder
            if campaign.recipient_type == "case":
                variables = email_service.build_surrogate_template_variables(db, recipient)
            else:
                variables = email_service.build_intended_parent_template_variables(db, recipient)

            subject, body = email_service.render_template(
                template.subject, template.body, variables
            )

            # Create recipient record
            cr = existing
            if not cr:
                from app.services import tracking_service

                cr = CampaignRecipient(
                    run_id=run_id,
                    entity_type=campaign.recipient_type,
                    entity_id=entity_id,
                    recipient_email=email,
                    recipient_name=name,
                    status=CampaignRecipientStatus.PENDING.value,
                    tracking_token=tracking_service.generate_tracking_token(),
                )
                db.add(cr)
            elif cr.status in (
                CampaignRecipientStatus.PENDING.value,
                CampaignRecipientStatus.SENT.value,
                CampaignRecipientStatus.DELIVERED.value,
                CampaignRecipientStatus.FAILED.value,
                CampaignRecipientStatus.SKIPPED.value,
            ):
                continue

            # Ensure tracking token exists (for retried sends)
            if not cr.tracking_token:
                from app.services import tracking_service

                cr.tracking_token = tracking_service.generate_tracking_token()

            # Inject tracking pixel and wrap links
            # Skip internal tracking for Resend (uses webhooks instead)
            if run.email_provider == "resend":
                tracked_body = body  # No internal tracking for Resend
            else:
                from app.services import tracking_service

                tracked_body = tracking_service.prepare_email_for_tracking(body, cr.tracking_token)

            try:
                # Queue email (actual send happens in background job)
                email_log, _job = email_service.send_email(
                    db=db,
                    org_id=org_id,
                    template_id=template.id,
                    recipient_email=email,
                    subject=subject,
                    body=tracked_body,
                    commit=False,
                )
                cr.status = CampaignRecipientStatus.PENDING.value
                cr.external_message_id = str(email_log.id)
            except Exception as e:
                cr.status = CampaignRecipientStatus.FAILED.value
                cr.error = str(e)[:500]

        db.commit()

    for recipient in recipient_iter:
        recipients_buffer.append(recipient)
        if len(recipients_buffer) >= batch_size:
            _process_batch(recipients_buffer)
            recipients_buffer = []

    if recipients_buffer:
        _process_batch(recipients_buffer)

    # Update run and campaign status
    status_rows = (
        db.query(CampaignRecipient.status, func.count(CampaignRecipient.id))
        .filter(CampaignRecipient.run_id == run_id)
        .group_by(CampaignRecipient.status)
        .all()
    )
    status_counts = {status: count for status, count in status_rows}

    pending_count = status_counts.get(CampaignRecipientStatus.PENDING.value, 0)
    run.sent_count = status_counts.get(CampaignRecipientStatus.SENT.value, 0)
    run.failed_count = status_counts.get(CampaignRecipientStatus.FAILED.value, 0)
    run.skipped_count = status_counts.get(CampaignRecipientStatus.SKIPPED.value, 0)
    run.completed_at = datetime.now(timezone.utc) if pending_count == 0 else None
    run.status = (
        "completed"
        if pending_count == 0 and run.failed_count == 0
        else ("failed" if pending_count == 0 else "running")
    )

    campaign.sent_count = run.sent_count
    campaign.failed_count = run.failed_count
    campaign.skipped_count = run.skipped_count
    campaign.total_recipients = run.total_count
    if pending_count == 0:
        campaign.status = (
            CampaignStatus.COMPLETED.value if run.failed_count == 0 else CampaignStatus.FAILED.value
        )
    else:
        campaign.status = CampaignStatus.SENDING.value

    db.commit()

    return {
        "sent_count": run.sent_count,
        "failed_count": run.failed_count,
        "skipped_count": run.skipped_count,
        "total_count": run.total_count,
    }


def retry_failed_campaign_run(
    db: Session,
    org_id: UUID,
    campaign_id: UUID,
    run_id: UUID,
) -> dict:
    """Retry failed recipients for an existing campaign run."""
    from app.services import email_service

    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == org_id,
        )
        .first()
    )
    if not campaign:
        raise Exception(f"Campaign {campaign_id} not found")

    run = (
        db.query(CampaignRun)
        .filter(
            CampaignRun.id == run_id,
            CampaignRun.campaign_id == campaign_id,
        )
        .first()
    )
    if not run:
        raise Exception(f"Campaign run {run_id} not found")

    template = (
        db.query(EmailTemplate).filter(EmailTemplate.id == campaign.email_template_id).first()
    )
    if not template:
        raise Exception(f"Email template {campaign.email_template_id} not found")

    failed_recipients = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.run_id == run_id,
            CampaignRecipient.status == CampaignRecipientStatus.FAILED.value,
        )
        .order_by(func.lower(CampaignRecipient.recipient_email), CampaignRecipient.id)
        .all()
    )
    if not failed_recipients:
        return {
            "sent_count": run.sent_count,
            "failed_count": run.failed_count,
            "skipped_count": run.skipped_count,
            "total_count": run.total_count,
            "retried_count": 0,
        }

    campaign.status = CampaignStatus.SENDING.value
    run.status = "running"
    db.commit()

    suppressed_emails = _load_suppressed_emails(db, org_id)
    seen_emails: dict[str, str | None] = {}
    retried_count = 0
    skipped_count = 0

    for recipient in failed_recipients:
        if campaign.recipient_type == "case":
            entity = (
                db.query(Surrogate)
                .filter(
                    Surrogate.id == recipient.entity_id,
                    Surrogate.organization_id == org_id,
                    Surrogate.is_archived.is_(False),
                )
                .first()
            )
        else:
            entity = (
                db.query(IntendedParent)
                .filter(
                    IntendedParent.id == recipient.entity_id,
                    IntendedParent.organization_id == org_id,
                    IntendedParent.is_archived.is_(False),
                )
                .first()
            )

        if not entity or not getattr(entity, "email", None):
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = "missing_recipient"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        email = entity.email
        email_norm = email.strip().lower() if email else ""
        if not email_norm:
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = "missing_recipient"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        if email_norm in seen_emails:
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = seen_emails[email_norm] or "duplicate_email"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        if email_norm in suppressed_emails:
            seen_emails[email_norm] = "suppressed"
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = "suppressed"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        seen_emails[email_norm] = None

        recipient.recipient_email = email
        recipient.recipient_name = getattr(entity, "full_name", None) or ""

        if campaign.recipient_type == "case":
            variables = email_service.build_surrogate_template_variables(db, entity)
        else:
            variables = email_service.build_intended_parent_template_variables(db, entity)

        subject, body = email_service.render_template(template.subject, template.body, variables)

        if run.email_provider == "resend":
            tracked_body = body
        else:
            from app.services import tracking_service

            if not recipient.tracking_token:
                recipient.tracking_token = tracking_service.generate_tracking_token()
            tracked_body = tracking_service.prepare_email_for_tracking(
                body, recipient.tracking_token
            )

        try:
            email_log, _job = email_service.send_email(
                db=db,
                org_id=org_id,
                template_id=template.id,
                recipient_email=email,
                subject=subject,
                body=tracked_body,
                commit=False,
            )
        except Exception as exc:
            recipient.status = CampaignRecipientStatus.FAILED.value
            recipient.error = str(exc)[:500]
            recipient.skip_reason = None
            recipient.external_message_id = None
            continue

        if email_log.status == EmailStatus.SKIPPED.value:
            recipient.status = CampaignRecipientStatus.SKIPPED.value
            recipient.skip_reason = "suppressed"
            recipient.error = None
            recipient.external_message_id = None
            skipped_count += 1
            continue

        recipient.status = CampaignRecipientStatus.PENDING.value
        recipient.error = None
        recipient.skip_reason = None
        recipient.external_message_id = str(email_log.id)
        retried_count += 1

    db.commit()

    status_rows = (
        db.query(CampaignRecipient.status, func.count(CampaignRecipient.id))
        .filter(CampaignRecipient.run_id == run_id)
        .group_by(CampaignRecipient.status)
        .all()
    )
    status_counts = {status: count for status, count in status_rows}

    pending_count = status_counts.get(CampaignRecipientStatus.PENDING.value, 0)
    run.sent_count = status_counts.get(CampaignRecipientStatus.SENT.value, 0)
    run.failed_count = status_counts.get(CampaignRecipientStatus.FAILED.value, 0)
    run.skipped_count = status_counts.get(CampaignRecipientStatus.SKIPPED.value, 0)
    run.completed_at = datetime.now(timezone.utc) if pending_count == 0 else None
    run.status = (
        "completed"
        if pending_count == 0 and run.failed_count == 0
        else ("failed" if pending_count == 0 else "running")
    )

    campaign.sent_count = run.sent_count
    campaign.failed_count = run.failed_count
    campaign.skipped_count = run.skipped_count
    campaign.total_recipients = run.total_count
    campaign.status = (
        CampaignStatus.COMPLETED.value
        if pending_count == 0 and run.failed_count == 0
        else (CampaignStatus.FAILED.value if pending_count == 0 else CampaignStatus.SENDING.value)
    )

    db.commit()

    return {
        "sent_count": run.sent_count,
        "failed_count": run.failed_count,
        "skipped_count": run.skipped_count,
        "total_count": run.total_count,
        "retried_count": retried_count,
    }
