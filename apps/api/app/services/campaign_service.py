"""Campaign service for bulk email management."""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Sequence

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Campaign, CampaignRun, CampaignRecipient, EmailSuppression,
    EmailTemplate, Case, IntendedParent, Job, PipelineStage
)
from app.db.enums import CampaignStatus, CampaignRecipientStatus, JobType, JobStatus
from app.schemas.campaign import (
    CampaignCreate, CampaignUpdate, CampaignResponse, CampaignListItem,
    CampaignRunResponse, CampaignPreviewResponse, RecipientPreview,
    FilterCriteria
)


# =============================================================================
# Campaign CRUD
# =============================================================================

def list_campaigns(
    db: Session,
    org_id: UUID,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0
) -> tuple[list[CampaignListItem], int]:
    """List campaigns for an organization."""
    query = db.query(Campaign).filter(
        Campaign.organization_id == org_id
    ).options(joinedload(Campaign.email_template))
    
    if status:
        query = query.filter(Campaign.status == status)
    
    total = query.count()
    
    campaigns = query.order_by(Campaign.created_at.desc()).offset(offset).limit(limit).all()
    
    # Get latest run stats for each campaign
    result = []
    for c in campaigns:
        latest_run = db.query(CampaignRun).filter(
            CampaignRun.campaign_id == c.id
        ).order_by(CampaignRun.started_at.desc()).first()
        
        result.append(CampaignListItem(
            id=c.id,
            name=c.name,
            email_template_name=c.email_template.name if c.email_template else None,
            recipient_type=c.recipient_type,
            status=c.status,
            scheduled_at=c.scheduled_at,
            total_recipients=latest_run.total_count if latest_run else 0,
            sent_count=latest_run.sent_count if latest_run else 0,
            failed_count=latest_run.failed_count if latest_run else 0,
            created_at=c.created_at,
        ))
    
    return result, total


def get_campaign(db: Session, org_id: UUID, campaign_id: UUID) -> Campaign | None:
    """Get a campaign by ID."""
    return db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == org_id
    ).options(
        joinedload(Campaign.email_template),
        joinedload(Campaign.created_by)
    ).first()


def create_campaign(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    data: CampaignCreate
) -> Campaign:
    """Create a new campaign."""
    # Verify template exists
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == data.email_template_id,
        EmailTemplate.organization_id == org_id
    ).first()
    
    if not template:
        raise ValueError("Email template not found")
    
    campaign = Campaign(
        organization_id=org_id,
        name=data.name,
        description=data.description,
        email_template_id=data.email_template_id,
        recipient_type=data.recipient_type,
        filter_criteria=data.filter_criteria.model_dump() if data.filter_criteria else {},
        scheduled_at=data.scheduled_at,
        status=CampaignStatus.DRAFT.value,
        created_by_user_id=user_id,
    )
    db.add(campaign)
    db.flush()
    
    return campaign


def update_campaign(
    db: Session,
    org_id: UUID,
    campaign_id: UUID,
    data: CampaignUpdate
) -> Campaign | None:
    """Update a campaign (only drafts can be updated)."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == org_id,
        Campaign.status == CampaignStatus.DRAFT.value
    ).first()
    
    if not campaign:
        return None
    
    if data.name is not None:
        campaign.name = data.name
    if data.description is not None:
        campaign.description = data.description
    if data.email_template_id is not None:
        # SECURITY: Validate template belongs to org before updating
        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == data.email_template_id,
            EmailTemplate.organization_id == org_id
        ).first()
        if not template:
            raise ValueError("Email template not found")
        campaign.email_template_id = data.email_template_id
    if data.recipient_type is not None:
        campaign.recipient_type = data.recipient_type
    if data.filter_criteria is not None:
        campaign.filter_criteria = data.filter_criteria.model_dump()
    if data.scheduled_at is not None:
        campaign.scheduled_at = data.scheduled_at
    
    db.flush()
    return campaign


def delete_campaign(db: Session, org_id: UUID, campaign_id: UUID) -> bool:
    """Delete a campaign (only drafts can be deleted)."""
    result = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == org_id,
        Campaign.status == CampaignStatus.DRAFT.value
    ).delete()
    
    return result > 0


# =============================================================================
# Recipient Filtering
# =============================================================================

def _build_recipient_query(
    db: Session,
    org_id: UUID,
    recipient_type: str,
    filter_criteria: dict
):
    """Build SQLAlchemy query for recipients based on filter criteria."""
    criteria = FilterCriteria(**filter_criteria) if filter_criteria else FilterCriteria()
    
    if recipient_type == "case":
        query = db.query(Case).filter(
            Case.organization_id == org_id,
            Case.is_archived == False,
            Case.email != None,
            Case.email != "",
        )
        
        if criteria.stage_ids:
            query = query.filter(Case.stage_id.in_([UUID(s) for s in criteria.stage_ids]))
        
        if criteria.stage_slugs:
            # IMPORTANT: Scope stages to org's pipelines to prevent cross-tenant leakage
            from app.db.models import Pipeline
            stage_ids = db.query(PipelineStage.id).join(
                Pipeline, PipelineStage.pipeline_id == Pipeline.id
            ).filter(
                Pipeline.organization_id == org_id,
                PipelineStage.slug.in_(criteria.stage_slugs)
            ).all()
            query = query.filter(Case.stage_id.in_([s.id for s in stage_ids]))
        
        if criteria.states:
            query = query.filter(Case.state.in_(criteria.states))
        
        if criteria.created_after:
            query = query.filter(Case.created_at >= criteria.created_after)
        
        if criteria.created_before:
            query = query.filter(Case.created_at <= criteria.created_before)
        
        if criteria.source:
            query = query.filter(Case.source == criteria.source)
        
        if criteria.is_priority is not None:
            query = query.filter(Case.is_priority == criteria.is_priority)
        
        return query
    
    elif recipient_type == "intended_parent":
        query = db.query(IntendedParent).filter(
            IntendedParent.organization_id == org_id,
            IntendedParent.email != None,
            IntendedParent.email != "",
            IntendedParent.is_archived == False,  # Exclude archived IPs
        )
        
        if criteria.created_after:
            query = query.filter(IntendedParent.created_at >= criteria.created_after)
        
        if criteria.created_before:
            query = query.filter(IntendedParent.created_at <= criteria.created_before)
        
        return query
    
    raise ValueError(f"Unknown recipient type: {recipient_type}")


def preview_recipients(
    db: Session,
    org_id: UUID,
    recipient_type: str,
    filter_criteria: dict,
    limit: int = 50
) -> CampaignPreviewResponse:
    """Preview recipients matching the filter criteria."""
    query = _build_recipient_query(db, org_id, recipient_type, filter_criteria)
    
    total_count = query.count()
    entities = query.limit(limit).all()
    
    # Get suppressed emails for this org (handle SA 2.0 Row objects)
    suppression_rows = db.query(EmailSuppression.email).filter(
        EmailSuppression.organization_id == org_id
    ).all()
    suppressed = {row[0].lower() for row in suppression_rows if row[0]}
    
    recipients = []
    for entity in entities:
        email = entity.email.lower() if entity.email else ""
        if email in suppressed:
            continue  # Skip suppressed
        
        if recipient_type == "case":
            stage = db.query(PipelineStage).filter(PipelineStage.id == entity.stage_id).first()
            recipients.append(RecipientPreview(
                entity_type="case",
                entity_id=entity.id,
                email=entity.email,
                name=entity.full_name,
                stage=stage.label if stage else None,
            ))
        else:
            recipients.append(RecipientPreview(
                entity_type="intended_parent",
                entity_id=entity.id,
                email=entity.email,
                name=entity.full_name,
                stage=None,
            ))
    
    return CampaignPreviewResponse(
        total_count=total_count,
        sample_recipients=recipients[:limit]
    )


# =============================================================================
# Sending
# =============================================================================

def enqueue_campaign_send(
    db: Session,
    org_id: UUID,
    campaign_id: UUID,
    user_id: UUID,
    send_now: bool = True
) -> tuple[str, UUID | None, datetime | None]:
    """
    Enqueue a campaign for sending.
    
    Returns: (message, run_id or None, scheduled_at or None)
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == org_id,
    ).with_for_update().first()
    
    if not campaign:
        raise ValueError("Campaign not found")
    
    if campaign.status not in [CampaignStatus.DRAFT.value, CampaignStatus.SCHEDULED.value]:
        raise ValueError(f"Cannot send campaign in '{campaign.status}' status")
    
    if send_now or not campaign.scheduled_at:
        # Create run immediately
        run = CampaignRun(
            organization_id=org_id,
            campaign_id=campaign.id,
            status="pending",
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
    else:
        # Schedule for later - still create the run and job, but with run_at
        run = CampaignRun(
            organization_id=org_id,
            campaign_id=campaign.id,
            status="pending",
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


def cancel_campaign(db: Session, org_id: UUID, campaign_id: UUID) -> bool:
    """Cancel a scheduled campaign."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == org_id,
        Campaign.status == CampaignStatus.SCHEDULED.value
    ).first()
    
    if not campaign:
        return False
    
    campaign.status = CampaignStatus.CANCELLED.value
    return True


# =============================================================================
# Runs
# =============================================================================

def list_campaign_runs(
    db: Session,
    org_id: UUID,
    campaign_id: UUID,
    limit: int = 20
) -> list[CampaignRunResponse]:
    """List runs for a campaign."""
    runs = db.query(CampaignRun).filter(
        CampaignRun.organization_id == org_id,
        CampaignRun.campaign_id == campaign_id
    ).order_by(CampaignRun.started_at.desc()).limit(limit).all()
    
    return [CampaignRunResponse.model_validate(r) for r in runs]


def get_campaign_run(
    db: Session,
    org_id: UUID,
    run_id: UUID
) -> CampaignRun | None:
    """Get a campaign run with recipients."""
    return db.query(CampaignRun).filter(
        CampaignRun.id == run_id,
        CampaignRun.organization_id == org_id
    ).options(joinedload(CampaignRun.recipients)).first()


# =============================================================================
# Suppression
# =============================================================================

def is_email_suppressed(db: Session, org_id: UUID, email: str) -> bool:
    """Check if an email is in the suppression list."""
    return db.query(EmailSuppression).filter(
        EmailSuppression.organization_id == org_id,
        EmailSuppression.email == email.lower()
    ).first() is not None


def add_to_suppression(
    db: Session,
    org_id: UUID,
    email: str,
    reason: str,
    source_type: str | None = None,
    source_id: UUID | None = None
) -> EmailSuppression:
    """Add an email to the suppression list (idempotent)."""
    existing = db.query(EmailSuppression).filter(
        EmailSuppression.organization_id == org_id,
        EmailSuppression.email == email.lower()
    ).first()
    
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
    db: Session,
    org_id: UUID,
    limit: int = 100,
    offset: int = 0
) -> tuple[list[EmailSuppression], int]:
    """List suppressed emails for an organization."""
    query = db.query(EmailSuppression).filter(
        EmailSuppression.organization_id == org_id
    )
    
    total = query.count()
    items = query.order_by(EmailSuppression.created_at.desc()).offset(offset).limit(limit).all()
    
    return items, total


def remove_from_suppression(db: Session, org_id: UUID, email: str) -> bool:
    """Remove an email from the suppression list."""
    result = db.query(EmailSuppression).filter(
        EmailSuppression.organization_id == org_id,
        EmailSuppression.email == email.lower()
    ).delete()
    
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
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == org_id,
    ).first()
    
    if not campaign:
        raise Exception(f"Campaign {campaign_id} not found")
    
    # Get run
    run = db.query(CampaignRun).filter(
        CampaignRun.id == run_id,
        CampaignRun.campaign_id == campaign_id,
    ).first()
    
    if not run:
        raise Exception(f"Campaign run {run_id} not found")
    
    # Get template
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == campaign.email_template_id
    ).first()
    
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
    
    # Get recipients
    recipients = _build_recipient_query(
        db, org_id,
        campaign.recipient_type,
        campaign.filter_criteria or {}
    ).all()
    
    recipients.sort(key=lambda r: ((r.email or "").lower(), str(r.id)))
    
    run.total_count = len(recipients)
    db.commit()

    seen_emails: dict[str, str | None] = {}

    for recipient in recipients:
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
        
        existing = db.query(CampaignRecipient).filter(
            CampaignRecipient.run_id == run_id,
            CampaignRecipient.entity_type == campaign.recipient_type,
            CampaignRecipient.entity_id == entity_id,
        ).first()
        
        if email_norm in seen_emails:
            skip_reason = seen_emails[email_norm] or "duplicate_email"
            if not existing:
                existing = CampaignRecipient(
                    organization_id=org_id,
                    run_id=run_id,
                    entity_type=campaign.recipient_type,
                    entity_id=entity_id,
                    recipient_email=email,
                    recipient_name=name,
                )
                db.add(existing)
                db.flush()
            if existing.status not in (
                CampaignRecipientStatus.SENT.value,
                CampaignRecipientStatus.SKIPPED.value,
            ):
                existing.status = CampaignRecipientStatus.SKIPPED.value
                existing.skip_reason = skip_reason
                db.commit()
            continue
        
        # Check suppression
        if is_email_suppressed(db, org_id, email_norm):
            seen_emails[email_norm] = "suppressed"
            if not existing:
                existing = CampaignRecipient(
                    organization_id=org_id,
                    run_id=run_id,
                    entity_type=campaign.recipient_type,
                    entity_id=entity_id,
                    recipient_email=email,
                    recipient_name=name,
                )
                db.add(existing)
                db.flush()
            if existing.status not in (
                CampaignRecipientStatus.SENT.value,
                CampaignRecipientStatus.SKIPPED.value,
            ):
                existing.status = CampaignRecipientStatus.SKIPPED.value
                existing.skip_reason = "suppressed"
                db.commit()
            continue

        seen_emails[email_norm] = None
        
        # Build email from template with variable substitution
        subject = template.subject
        body = template.body
        
        # Basic variable replacement
        variables = {
            "first_name": name.split()[0] if name else "",
            "full_name": name or "",
            "email": email,
        }
        
        for key, value in variables.items():
            placeholder = "{{" + key + "}}"
            subject = subject.replace(placeholder, str(value) if value else "")
            body = body.replace(placeholder, str(value) if value else "")
        
        # Create recipient record
        cr = existing
        if not cr:
            cr = CampaignRecipient(
                organization_id=org_id,
                run_id=run_id,
                entity_type=campaign.recipient_type,
                entity_id=entity_id,
                recipient_email=email,
                recipient_name=name,
                status=CampaignRecipientStatus.PENDING.value,
            )
            db.add(cr)
            db.flush()
        elif cr.status in (
            CampaignRecipientStatus.SENT.value,
            CampaignRecipientStatus.SKIPPED.value,
        ):
            continue
        
        try:
            # Queue email (actual send happens in background job)
            email_log, _job = email_service.send_email(
                db=db,
                org_id=org_id,
                template_id=template.id,
                recipient_email=email,
                subject=subject,
                body=body,
            )
            cr.status = CampaignRecipientStatus.PENDING.value
            cr.external_message_id = str(email_log.id)
        except Exception as e:
            cr.status = CampaignRecipientStatus.FAILED.value
            cr.error = str(e)[:500]
        
        db.commit()
    
    # Update run and campaign status
    status_rows = db.query(
        CampaignRecipient.status,
        func.count(CampaignRecipient.id)
    ).filter(
        CampaignRecipient.run_id == run_id
    ).group_by(
        CampaignRecipient.status
    ).all()
    status_counts = {status: count for status, count in status_rows}
    
    pending_count = status_counts.get(CampaignRecipientStatus.PENDING.value, 0)
    run.sent_count = status_counts.get(CampaignRecipientStatus.SENT.value, 0)
    run.failed_count = status_counts.get(CampaignRecipientStatus.FAILED.value, 0)
    run.skipped_count = status_counts.get(CampaignRecipientStatus.SKIPPED.value, 0)
    run.completed_at = datetime.now(timezone.utc) if pending_count == 0 else None
    run.status = "completed" if pending_count == 0 and run.failed_count == 0 else (
        "failed" if pending_count == 0 else "running"
    )
    
    campaign.sent_count = run.sent_count
    campaign.failed_count = run.failed_count
    campaign.skipped_count = run.skipped_count
    campaign.total_recipients = run.total_count
    if pending_count == 0:
        campaign.status = CampaignStatus.COMPLETED.value if run.failed_count == 0 else CampaignStatus.FAILED.value
    else:
        campaign.status = CampaignStatus.SENDING.value
    
    db.commit()
    
    return {
        "sent_count": run.sent_count,
        "failed_count": run.failed_count,
        "skipped_count": run.skipped_count,
        "total_count": run.total_count,
    }
