"""Campaigns router - CRUD and send operations for bulk email campaigns."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.schemas.campaign import (
    CampaignCreate,
    CampaignListItem,
    CampaignPreviewResponse,
    CampaignRecipientResponse,
    CampaignResponse,
    CampaignRetryResponse,
    CampaignRunResponse,
    CampaignSendRequest,
    CampaignSendResponse,
    CampaignUpdate,
    PreviewFiltersRequest,
    SuppressionCreate,
    SuppressionResponse,
)
from app.services import campaign_service, permission_service

csrf_header_dependency = require_csrf_header


router = APIRouter(
    tags=["Campaigns"],
    dependencies=[Depends(require_permission(POLICIES["email_templates"].default))],
    prefix="/campaigns",
)

DONOR_RECIPIENT_TYPES = {"egg_donor", "sperm_donor"}


def _require_donor_recipient_access(
    db: Session,
    session: UserSession,
    recipient_type: str,
    *,
    require_write: bool = False,
) -> None:
    """Require donor access before reading or mutating a donor campaign."""
    if recipient_type not in DONOR_RECIPIENT_TYPES:
        return
    permission = (
        POLICIES["donors"].actions["edit"]
        if require_write
        else POLICIES["donors"].default
    )
    role = getattr(session.role, "value", session.role)
    if not permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        role,
        permission.value,
    ):
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission.value}")


def _require_messaging_operator(session: UserSession) -> None:
    if session.role not in {Role.ADMIN, Role.DEVELOPER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Messaging campaigns require an organization admin or developer",
        )


# =============================================================================
# Campaign CRUD
# =============================================================================


@router.get("", response_model=list[CampaignListItem])
def list_campaigns(
    status: Annotated[str | None, "fastapi_param"] = Query(None, description="Filter by status"),
    limit: Annotated[int, "fastapi_param"] = Query(50, ge=1, le=100),
    offset: Annotated[int, "fastapi_param"] = Query(0, ge=0),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    """List campaigns for the organization."""
    role = getattr(session.role, "value", session.role)
    can_view_donors = permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        role,
        POLICIES["donors"].default.value,
    )
    campaigns, total = campaign_service.list_campaigns(
        db,
        org_id=session.org_id,
        status=status,
        limit=limit,
        offset=offset,
        exclude_recipient_types=None if can_view_donors else DONOR_RECIPIENT_TYPES,
    )
    return campaigns


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    data: CampaignCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
    _csrf: Annotated[object, "fastapi_param"] = Depends(csrf_header_dependency),
):
    """Create a new campaign (draft status)."""
    if data.channel == "messaging":
        _require_messaging_operator(session)
    _require_donor_recipient_access(
        db,
        session,
        data.recipient_type,
        require_write=True,
    )
    try:
        campaign = campaign_service.create_campaign(
            db, org_id=session.org_id, user_id=session.user_id, data=data
        )
        db.commit()
        return _campaign_to_response(db, campaign)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    """Get a campaign by ID with stats."""
    campaign = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    _require_donor_recipient_access(db, session, campaign.recipient_type)

    return _campaign_to_response(db, campaign)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
    _csrf: Annotated[object, "fastapi_param"] = Depends(csrf_header_dependency),
):
    """Update a draft or scheduled campaign."""
    current = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if current.channel == "messaging" or data.channel == "messaging":
        _require_messaging_operator(session)
    _require_donor_recipient_access(
        db,
        session,
        current.recipient_type,
        require_write=True,
    )
    if data.recipient_type is not None:
        _require_donor_recipient_access(
            db,
            session,
            data.recipient_type,
            require_write=True,
        )
    try:
        campaign = campaign_service.update_campaign(
            db, org_id=session.org_id, campaign_id=campaign_id, data=data
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not campaign:
        raise HTTPException(
            status_code=400,
            detail="Campaign not found or cannot be updated (only drafts or scheduled can be edited)",
        )

    db.commit()
    return _campaign_to_response(db, campaign)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
    _csrf: Annotated[object, "fastapi_param"] = Depends(csrf_header_dependency),
) -> Response:
    """Delete a draft campaign."""
    campaign = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if campaign is not None and campaign.channel == "messaging":
        _require_messaging_operator(session)
    if campaign is not None:
        _require_donor_recipient_access(
            db,
            session,
            campaign.recipient_type,
            require_write=True,
        )
    deleted = campaign_service.delete_campaign(db, session.org_id, campaign_id)
    if not deleted:
        raise HTTPException(
            status_code=400,
            detail="Campaign not found or cannot be deleted (only drafts can be deleted)",
        )
    db.commit()


# =============================================================================
# Preview & Send
# =============================================================================


@router.post("/preview-filters", response_model=CampaignPreviewResponse)
def preview_filters(
    data: PreviewFiltersRequest,
    limit: Annotated[int, "fastapi_param"] = Query(50, ge=1, le=100),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
):
    """
    Preview recipients that match filter criteria BEFORE creating a campaign.

    Returns total count and sample recipients.
    """
    if data.channel == "messaging":
        _require_messaging_operator(session)
    _require_donor_recipient_access(db, session, data.recipient_type)
    # Convert FilterCriteria to dict for service call
    filter_dict = data.filter_criteria.model_dump(exclude_none=True) if data.filter_criteria else {}

    return campaign_service.preview_recipients(
        db,
        org_id=session.org_id,
        recipient_type=data.recipient_type,
        filter_criteria=filter_dict,
        limit=limit,
        ignore_opt_out=bool(getattr(data, "include_unsubscribed", False)),
        channel=data.channel,
    )


@router.get("/{campaign_id}/preview", response_model=CampaignPreviewResponse)
def preview_recipients(
    campaign_id: UUID,
    limit: Annotated[int, "fastapi_param"] = Query(50, ge=1, le=100),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
):
    """Preview recipients that match the campaign filter."""
    campaign = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.channel == "messaging":
        _require_messaging_operator(session)
    _require_donor_recipient_access(db, session, campaign.recipient_type)

    return campaign_service.preview_recipients(
        db,
        org_id=session.org_id,
        recipient_type=campaign.recipient_type,
        filter_criteria=campaign.filter_criteria,
        limit=limit,
        ignore_opt_out=bool(getattr(campaign, "include_unsubscribed", False)),
        channel=campaign.channel,
    )


@router.post(
    "/{campaign_id}/send",
    response_model=CampaignSendResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def send_campaign(
    campaign_id: UUID,
    data: CampaignSendRequest | None = None,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
    _csrf: Annotated[object, "fastapi_param"] = Depends(csrf_header_dependency),
):
    """
    Enqueue a campaign for sending.

    Returns 202 Accepted as sending happens asynchronously.
    """
    send_now = data.send_now if data else True

    campaign = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.channel == "messaging":
        _require_messaging_operator(session)
    _require_donor_recipient_access(
        db,
        session,
        campaign.recipient_type,
        require_write=True,
    )

    try:
        message, run_id, scheduled_at = campaign_service.enqueue_campaign_send(
            db,
            org_id=session.org_id,
            campaign_id=campaign_id,
            user_id=session.user_id,
            send_now=send_now,
        )
        db.commit()

        return CampaignSendResponse(
            message=message,
            run_id=run_id,
            scheduled_at=scheduled_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{campaign_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_campaign(
    campaign_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
    _csrf: Annotated[object, "fastapi_param"] = Depends(csrf_header_dependency),
) -> object:
    """Cancel a scheduled or in-progress campaign."""
    campaign = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if campaign is not None and campaign.channel == "messaging":
        _require_messaging_operator(session)
    if campaign is not None:
        _require_donor_recipient_access(
            db,
            session,
            campaign.recipient_type,
            require_write=True,
        )
    cancelled = campaign_service.cancel_campaign(db, session.org_id, campaign_id)
    if not cancelled:
        raise HTTPException(
            status_code=400,
            detail="Campaign not found or cannot be cancelled (only scheduled or sending campaigns can be stopped)",
        )
    db.commit()
    return {"message": "Campaign cancelled"}


# =============================================================================
# Runs
# =============================================================================


@router.get("/{campaign_id}/runs", response_model=list[CampaignRunResponse])
def list_campaign_runs(
    campaign_id: UUID,
    limit: Annotated[int, "fastapi_param"] = Query(20, ge=1, le=100),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    """List execution history for a campaign."""
    campaign = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    _require_donor_recipient_access(db, session, campaign.recipient_type)
    return campaign_service.list_campaign_runs(
        db, org_id=session.org_id, campaign_id=campaign_id, limit=limit
    )


@router.get("/{campaign_id}/runs/{run_id}", response_model=CampaignRunResponse)
def get_campaign_run(
    campaign_id: UUID,
    run_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    """Get run details with recipients."""
    run = campaign_service.get_campaign_run(db, session.org_id, run_id)
    if not run or run.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Run not found")
    campaign = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    _require_donor_recipient_access(db, session, campaign.recipient_type)

    return CampaignRunResponse.model_validate(run)


@router.post(
    "/{campaign_id}/runs/{run_id}/retry-failed",
    response_model=CampaignRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf_header)],
)
def retry_failed_campaign_run(
    campaign_id: UUID,
    run_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
):
    """Retry failed recipients for a campaign run."""
    campaign = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if campaign is not None and campaign.channel == "messaging":
        _require_messaging_operator(session)
    if campaign is not None:
        _require_donor_recipient_access(
            db,
            session,
            campaign.recipient_type,
            require_write=True,
        )
    try:
        message, resolved_run_id, job_id, failed_count = (
            campaign_service.enqueue_campaign_retry_failed(
                db=db,
                org_id=session.org_id,
                campaign_id=campaign_id,
                run_id=run_id,
                user_id=session.user_id,
            )
        )
        db.commit()
        return CampaignRetryResponse(
            message=message,
            run_id=resolved_run_id,
            job_id=job_id,
            failed_count=failed_count,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{campaign_id}/runs/{run_id}/recipients",
    response_model=list[CampaignRecipientResponse],
)
def list_run_recipients(
    campaign_id: UUID,
    run_id: UUID,
    status: Annotated[str | None, "fastapi_param"] = Query(None, description="Filter by status"),
    limit: Annotated[int, "fastapi_param"] = Query(100, ge=1, le=500),
    offset: Annotated[int, "fastapi_param"] = Query(0, ge=0),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    """List recipients for a campaign run."""
    run = campaign_service.get_campaign_run(db, session.org_id, run_id)
    if not run or run.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Run not found")
    campaign = campaign_service.get_campaign(db, session.org_id, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    _require_donor_recipient_access(db, session, campaign.recipient_type)

    recipients = campaign_service.list_run_recipients(
        db=db,
        run_id=run_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [CampaignRecipientResponse.model_validate(r) for r in recipients]


# =============================================================================
# Suppression List
# =============================================================================


@router.get("/suppressions", response_model=list[SuppressionResponse])
def list_suppressions(
    limit: Annotated[int, "fastapi_param"] = Query(100, ge=1, le=500),
    offset: Annotated[int, "fastapi_param"] = Query(0, ge=0),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
):
    """List suppressed emails for the organization."""
    items, total = campaign_service.list_suppressions(
        db, org_id=session.org_id, limit=limit, offset=offset
    )
    return [SuppressionResponse.model_validate(s) for s in items]


@router.post(
    "/suppressions",
    response_model=SuppressionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_suppression(
    data: SuppressionCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
    _csrf: Annotated[object, "fastapi_param"] = Depends(csrf_header_dependency),
):
    """Add an email to the suppression list."""
    suppression = campaign_service.add_to_suppression(
        db, org_id=session.org_id, email=data.email, reason=data.reason
    )
    db.commit()
    return SuppressionResponse.model_validate(suppression)


@router.delete("/suppressions/{email}", status_code=status.HTTP_204_NO_CONTENT)
def remove_suppression(
    email: str,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(
        require_permission(POLICIES["email_templates"].actions["manage"])
    ),
    _csrf: Annotated[object, "fastapi_param"] = Depends(csrf_header_dependency),
) -> Response:
    """Remove an email from the suppression list."""
    removed = campaign_service.remove_from_suppression(db, session.org_id, email)
    if not removed:
        raise HTTPException(status_code=404, detail="Email not found in suppression list")
    db.commit()


# =============================================================================
# Helpers
# =============================================================================


def _campaign_to_response(db: Session, campaign) -> CampaignResponse:
    """Convert campaign model to response with stats."""
    # Get latest run stats
    latest_run = campaign_service.get_latest_run_for_campaign(db, campaign.id)

    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        channel=campaign.channel,
        email_template_id=campaign.email_template_id,
        email_template_name=campaign.email_template.name if campaign.email_template else None,
        message_template_version_id=campaign.message_template_version_id,
        message_template_name=(
            campaign.message_template.name if campaign.message_template else None
        ),
        recipient_type=campaign.recipient_type,
        filter_criteria=campaign.filter_criteria,
        scheduled_at=campaign.scheduled_at,
        status=campaign.status,
        include_unsubscribed=getattr(campaign, "include_unsubscribed", False),
        created_by_user_id=campaign.created_by_user_id,
        created_by_name=campaign.created_by.display_name if campaign.created_by else None,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        total_recipients=latest_run.total_count if latest_run else 0,
        sent_count=latest_run.sent_count if latest_run else 0,
        delivered_count=latest_run.delivered_count if latest_run else 0,
        failed_count=latest_run.failed_count if latest_run else 0,
        skipped_count=latest_run.skipped_count if latest_run else 0,
        opened_count=latest_run.opened_count if latest_run else 0,
        clicked_count=latest_run.clicked_count if latest_run else 0,
    )
