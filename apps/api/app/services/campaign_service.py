"""Campaign definitions and organization publication."""

from copy import deepcopy
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.enums import CampaignStatus, JobStatus, JobType
from app.db.models import (
    Campaign,
    CampaignRun,
    EmailTemplate,
    Job,
)
from app.schemas.campaign import (
    CampaignCreate,
    CampaignListItem,
    CampaignUpdate,
)
from app.services import campaign_access, campaign_audience, campaign_content, campaign_run_service
from app.utils.pagination import paginate_query_by_offset


def list_campaigns(
    db: Session,
    org_id: UUID,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    exclude_recipient_types: set[str] | None = None,
    viewer_session=None,
) -> tuple[list[CampaignListItem], int]:
    """List campaigns for an organization with optimized run stats query."""
    if viewer_session is not None and viewer_session.org_id != org_id:
        return [], 0
    # Base query for count
    base_query = db.query(Campaign).filter(Campaign.organization_id == org_id)

    if viewer_session is not None:
        base_query = base_query.filter(campaign_access.visible_filter(db, viewer_session))
    if status:
        base_query = base_query.filter(Campaign.status == status)
    if exclude_recipient_types:
        base_query = base_query.filter(~Campaign.recipient_type.in_(exclude_recipient_types))

    # Subquery: Get latest run per campaign using window function
    # This avoids N+1 queries by fetching all latest runs in one query
    run_subq = (
        db.query(
            CampaignRun.campaign_id,
            CampaignRun.id.label("run_id"),
            CampaignRun.total_count,
            CampaignRun.sent_count,
            CampaignRun.delivered_count,
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
            run_subq.c.run_id,
            run_subq.c.total_count,
            run_subq.c.sent_count,
            run_subq.c.delivered_count,
            run_subq.c.failed_count,
            run_subq.c.opened_count,
            run_subq.c.clicked_count,
        )
        .outerjoin(
            run_subq,
            (Campaign.id == run_subq.c.campaign_id) & (run_subq.c.rn == 1),
        )
        .filter(Campaign.organization_id == org_id)
        .options(
            joinedload(Campaign.email_template),
            joinedload(Campaign.message_template),
        )
    )

    if viewer_session is not None:
        query = query.filter(campaign_access.visible_filter(db, viewer_session))
    if status:
        query = query.filter(Campaign.status == status)
    if exclude_recipient_types:
        query = query.filter(~Campaign.recipient_type.in_(exclude_recipient_types))

    rows, total = paginate_query_by_offset(
        query.order_by(Campaign.created_at.desc()),
        offset=offset,
        limit=limit,
        count_query=base_query,
    )

    # Build result from joined data
    permissions = (
        campaign_access.effective_permissions(db, viewer_session) if viewer_session else None
    )
    scoped_stats = (
        campaign_run_service.viewer_run_statistics(
            db, org_id, [row.run_id for row in rows if row.run_id], viewer_session
        )
        if viewer_session is not None and campaign_access.enabled(db, org_id)
        else None
    )
    result = []
    for row in rows:
        c = row[0]  # Campaign object
        counts = (
            scoped_stats.get(row.run_id, campaign_run_service.EMPTY_RUN_STATISTICS)
            if scoped_stats is not None
            else row._mapping
        )
        if (
            viewer_session is not None
            and c.scope == "personal"
            and c.owner_user_id != viewer_session.user_id
        ):
            campaign_access.audit(db, c, viewer_session.user_id, "list")
        result.append(
            CampaignListItem(
                scope=c.scope,
                owner_user_id=c.owner_user_id,
                proposed_by_user_id=c.proposed_by_user_id,
                proposed_by_name=c.proposed_by_name,
                **campaign_access.capabilities(db, viewer_session, c, permissions=permissions),
                id=c.id,
                name=c.name,
                channel=c.channel,
                email_template_name=c.email_template.name if c.email_template else None,
                message_template_name=(c.message_template.name if c.message_template else None),
                recipient_type=c.recipient_type,
                status=c.status,
                scheduled_at=c.scheduled_at,
                include_unsubscribed=getattr(c, "include_unsubscribed", False),
                total_recipients=counts["total_count"] or 0,
                sent_count=counts["sent_count"] or 0,
                delivered_count=counts["delivered_count"] or 0,
                failed_count=counts["failed_count"] or 0,
                opened_count=counts["opened_count"] or 0,
                clicked_count=counts["clicked_count"] or 0,
                created_at=c.created_at,
            )
        )

    return result, total


def get_campaign(db: Session, org_id: UUID, campaign_id: UUID) -> Campaign | None:
    """Get a campaign by ID."""
    return (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.organization_id == org_id)
        .options(
            joinedload(Campaign.email_template),
            joinedload(Campaign.message_template),
            joinedload(Campaign.created_by),
        )
        .first()
    )


def create_campaign(db: Session, org_id: UUID, user_id: UUID, data: CampaignCreate) -> Campaign:
    """Create a new campaign."""
    from app.services import permission_policy_service
    from app.services.workflow_execution_authority import active_session

    permission_policy_service.lock_configuration(db, org_id)
    actor = active_session(db, org_id, user_id)
    if campaign_access.enabled(db, org_id) and (
        actor is None or not campaign_access.can_create(db, actor, data.scope)
    ):
        raise ValueError("Cannot create this campaign scope")
    campaign_audience.ensure_supported_campaign_channel(data.channel, data.recipient_type)
    if data.channel == "email":
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
    else:
        campaign_content.load_published_message_template(
            db,
            org_id=org_id,
            template_version_id=data.message_template_version_id,
        )

    campaign_run_service.ensure_future_datetime(data.scheduled_at, "scheduled_at")

    campaign = Campaign(
        organization_id=org_id,
        scope=data.scope,
        owner_user_id=user_id if data.scope == "personal" else None,
        proposed_by_user_id=user_id,
        proposed_by_name=actor.display_name if actor else None,
        name=data.name,
        description=data.description,
        channel=data.channel,
        email_template_id=data.email_template_id,
        message_template_version_id=data.message_template_version_id,
        recipient_type=data.recipient_type,
        filter_criteria=campaign_audience.normalize_filter_criteria(
            db,
            org_id,
            data.recipient_type,
            data.filter_criteria,
        ),
        scheduled_at=data.scheduled_at,
        status=CampaignStatus.DRAFT.value,
        include_unsubscribed=(data.include_unsubscribed if data.channel == "email" else False),
        created_by_user_id=user_id,
    )
    campaign_access.validate_template_scope(db, campaign)
    db.add(campaign)
    db.flush()

    campaign_access.audit(db, campaign, user_id, "create")
    return campaign


def update_campaign(
    db: Session,
    org_id: UUID,
    campaign_id: UUID,
    data: CampaignUpdate,
    actor_user_id: UUID | None = None,
) -> Campaign | None:
    """Update a campaign (drafts or scheduled only)."""
    from app.services import permission_policy_service

    permission_policy_service.lock_configuration(db, org_id)
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == org_id,
            Campaign.status.in_(
                [
                    CampaignStatus.DRAFT.value,
                    CampaignStatus.SCHEDULED.value,
                ]
            ),
        )
        .first()
    )

    if not campaign:
        return None

    effective_channel = data.channel or campaign.channel
    effective_recipient_type = data.recipient_type or campaign.recipient_type
    campaign_audience.ensure_supported_campaign_channel(effective_channel, effective_recipient_type)
    if data.channel is not None and data.channel != campaign.channel:
        if campaign.status != CampaignStatus.DRAFT.value:
            raise ValueError("Cannot change channel after campaign is scheduled")
        if data.channel == "email" and data.email_template_id is None:
            raise ValueError("Changing to email requires email_template_id")
        if data.channel == "messaging" and data.message_template_version_id is None:
            raise ValueError("Changing to messaging requires message_template_version_id")
        campaign.channel = data.channel
        campaign.email_template_id = None
        campaign.message_template_version_id = None

    if effective_channel == "messaging" and data.include_unsubscribed:
        raise ValueError("include_unsubscribed is not available for messaging campaigns")

    if data.name is not None:
        campaign.name = data.name
    if data.description is not None:
        campaign.description = data.description
    if data.email_template_id is not None:
        if effective_channel != "email":
            raise ValueError("Messaging campaigns cannot use email templates")
        if (
            campaign.status == CampaignStatus.SCHEDULED.value
            and data.email_template_id != campaign.email_template_id
        ):
            raise ValueError("Cannot change email template after campaign is scheduled")
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
    if data.message_template_version_id is not None:
        if effective_channel != "messaging":
            raise ValueError("Email campaigns cannot use message templates")
        if (
            campaign.status == CampaignStatus.SCHEDULED.value
            and data.message_template_version_id != campaign.message_template_version_id
        ):
            raise ValueError("Cannot change message template after campaign is scheduled")
        campaign_content.load_published_message_template(
            db,
            org_id=org_id,
            template_version_id=data.message_template_version_id,
        )
        campaign.message_template_version_id = data.message_template_version_id
    if data.recipient_type is not None:
        campaign.recipient_type = data.recipient_type
        if data.filter_criteria is None:
            campaign.filter_criteria = campaign_audience.normalize_filter_criteria(
                db,
                org_id,
                data.recipient_type,
                campaign.filter_criteria,
            )
    if data.filter_criteria is not None:
        campaign.filter_criteria = campaign_audience.normalize_filter_criteria(
            db,
            org_id,
            data.recipient_type or campaign.recipient_type,
            data.filter_criteria,
        )
    if data.scheduled_at is not None:
        campaign_run_service.ensure_future_datetime(data.scheduled_at, "scheduled_at")
        campaign.scheduled_at = data.scheduled_at
        if campaign.status == CampaignStatus.SCHEDULED.value:
            latest_run = (
                db.query(CampaignRun)
                .filter(
                    CampaignRun.organization_id == org_id,
                    CampaignRun.campaign_id == campaign.id,
                )
                .order_by(CampaignRun.started_at.desc())
                .first()
            )
            if latest_run:
                pending_job = (
                    db.query(Job)
                    .filter(
                        Job.organization_id == org_id,
                        Job.job_type == JobType.CAMPAIGN_SEND.value,
                        Job.status == JobStatus.PENDING.value,
                        Job.payload["run_id"].astext == str(latest_run.id),
                    )
                    .order_by(Job.run_at.desc())
                    .first()
                )
                if pending_job:
                    pending_job.run_at = campaign.scheduled_at

    if data.include_unsubscribed is not None:
        campaign.include_unsubscribed = (
            data.include_unsubscribed if effective_channel == "email" else False
        )

    campaign_access.validate_template_scope(db, campaign)
    if campaign_access.enabled(db, org_id) and campaign.status == CampaignStatus.SCHEDULED.value:
        grant = campaign_access.authorize_send(db, campaign, actor_user_id)
        for queued_run in (
            db.query(CampaignRun)
            .filter(
                CampaignRun.organization_id == org_id,
                CampaignRun.campaign_id == campaign.id,
                CampaignRun.status == "running",
            )
            .all()
        ):
            queued_run.authority_snapshot = grant
    if actor_user_id:
        campaign_access.audit(db, campaign, actor_user_id, "update")
    db.flush()
    return campaign


def delete_campaign(db: Session, org_id: UUID, campaign_id: UUID) -> bool:
    """Delete a campaign (only drafts can be deleted)."""
    from app.services import permission_policy_service

    permission_policy_service.lock_configuration(db, org_id)
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


def publish_campaign(db, campaign, actor_user_id):

    from app.schemas.campaign import CampaignCreate
    from app.services import email_template_publication, permission_policy_service
    from app.services.workflow_execution_authority import active_session

    permission_policy_service.lock_configuration(db, campaign.organization_id)
    actor = active_session(db, campaign.organization_id, actor_user_id)
    if (
        not campaign_access.enabled(db, campaign.organization_id)
        or actor is None
        or campaign.scope != "personal"
        or not campaign_access.can_manage(db, actor, campaign)
        or not campaign_access.can_create(db, actor, "org")
    ):
        raise ValueError("Cannot publish this campaign")
    with db.begin_nested():
        template_id = campaign.email_template_id
        if campaign.channel == "email":
            campaign_access.validate_template_scope(db, campaign)
            template_id = email_template_publication.publish_template_to_org(
                db,
                org_id=campaign.organization_id,
                template_id=template_id,
                actor_user_id=actor_user_id,
            ).id
        base_name = campaign.name[:170] + " (Published)"
        name, counter = base_name, 1
        while (
            db.query(Campaign.id)
            .filter(
                Campaign.organization_id == campaign.organization_id,
                Campaign.scope == "org",
                Campaign.name == name,
            )
            .first()
        ):
            counter += 1
            name = f"{base_name} {counter}"
        published = create_campaign(
            db,
            campaign.organization_id,
            actor_user_id,
            CampaignCreate(
                name=name,
                description=campaign.description,
                scope="org",
                channel=campaign.channel,
                email_template_id=template_id,
                message_template_version_id=campaign.message_template_version_id,
                recipient_type=campaign.recipient_type,
                filter_criteria=deepcopy(campaign.filter_criteria),
                include_unsubscribed=campaign.include_unsubscribed,
            ),
        )
        proposer_id = campaign.proposed_by_user_id or campaign.owner_user_id
        from app.db.models import User

        proposer = db.get(User, proposer_id) if proposer_id else None
        published.proposed_by_user_id = proposer_id
        published.proposed_by_name = campaign.proposed_by_name or (
            proposer.display_name if proposer else None
        )
        campaign_access.audit(db, published, actor_user_id, "publish")
        campaign_access.audit(db, campaign, actor_user_id, "publish_source")
        db.flush()
    return published
