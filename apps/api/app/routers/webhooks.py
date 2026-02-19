"""Webhooks router - external service integrations."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import JobType
from app.core.deps import get_db
from app.db.models import Job, Membership, UserIntegration
from app.services import job_service
from app.services import calendar_service
from app.services.webhooks import get_handler
from app.services.webhooks.meta import simulate_meta_webhook as simulate_meta_webhook_handler

# Rate limiting
from app.core.rate_limit import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/meta")
async def verify_meta_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    handler = get_handler("meta")
    return handler.verify(mode, token, challenge)


@router.post("/meta")
@limiter.limit(f"{settings.RATE_LIMIT_WEBHOOK}/minute")
async def receive_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    handler = get_handler("meta")
    return await handler.handle(request, db)


# =============================================================================
# Dev/Test endpoint for simulating Meta webhook
# =============================================================================


@router.post("/meta/simulate", include_in_schema=False)
async def simulate_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    return await simulate_meta_webhook_handler(request, db)


# =============================================================================
# Zoom Webhooks
# =============================================================================


@router.post("/zoom")
@limiter.limit(f"{settings.RATE_LIMIT_WEBHOOK}/minute")
async def zoom_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    handler = get_handler("zoom")
    return await handler.handle(request, db)


# =============================================================================
# Google Calendar Push Notifications (events.watch)
# =============================================================================


@router.post("/google-calendar")
@limiter.limit(f"{settings.RATE_LIMIT_WEBHOOK}/minute")
async def google_calendar_push_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receive Google Calendar events.watch notifications and enqueue reconciliation.

    Push notifications do not include event payloads; this endpoint schedules a
    near-immediate sync job for the matching connected user.
    """
    channel_id = request.headers.get("x-goog-channel-id")
    resource_id = request.headers.get("x-goog-resource-id")
    channel_token = request.headers.get("x-goog-channel-token")
    message_number = request.headers.get("x-goog-message-number", "0")
    resource_state = request.headers.get("x-goog-resource-state", "unknown")

    if not channel_id or not resource_id or not channel_token:
        return JSONResponse({"status": "ignored", "reason": "missing_headers"}, status_code=202)

    integration = (
        db.query(UserIntegration)
        .filter(
            UserIntegration.integration_type == "google_calendar",
            UserIntegration.google_calendar_channel_id == channel_id,
            UserIntegration.google_calendar_resource_id == resource_id,
        )
        .first()
    )
    if not integration:
        return JSONResponse({"status": "ignored", "reason": "unknown_channel"}, status_code=202)

    if not calendar_service.verify_watch_channel_token(
        integration.google_calendar_channel_token_encrypted,
        channel_token,
    ):
        logger.warning(
            "Ignored Google Calendar push with invalid channel token user=%s channel=%s",
            integration.user_id,
            channel_id,
        )
        return JSONResponse({"status": "ignored", "reason": "invalid_token"}, status_code=202)

    membership = (
        db.query(Membership)
        .filter(Membership.user_id == integration.user_id, Membership.is_active.is_(True))
        .first()
    )
    if not membership:
        return JSONResponse({"status": "ignored", "reason": "inactive_membership"}, status_code=202)

    idempotency_key = f"google-calendar-push:{channel_id}:{message_number}"
    existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
    if existing:
        return JSONResponse({"status": "accepted"}, status_code=202)

    try:
        job_service.enqueue_job(
            db=db,
            org_id=membership.organization_id,
            job_type=JobType.GOOGLE_CALENDAR_SYNC,
            payload={
                "user_id": str(integration.user_id),
                "source": "google_push",
                "resource_state": resource_state,
            },
            run_at=datetime.now(timezone.utc),
            idempotency_key=idempotency_key,
            commit=True,
        )
    except IntegrityError:
        db.rollback()

    return JSONResponse({"status": "accepted"}, status_code=202)


# =============================================================================
# Resend Webhooks (Email Delivery Events)
# =============================================================================


@router.post("/resend/{webhook_id}")
@limiter.limit(f"{settings.RATE_LIMIT_WEBHOOK}/minute")
async def resend_webhook(
    webhook_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    handler = get_handler("resend")
    return await handler.handle(request, db, webhook_id=webhook_id)


@router.post("/resend/platform")
@limiter.limit(f"{settings.RATE_LIMIT_WEBHOOK}/minute")
async def resend_platform_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    handler = get_handler("resend_platform")
    return await handler.handle(request, db)


# =============================================================================
# Zapier Webhooks (Inbound leads)
# =============================================================================


@router.post("/zapier/{webhook_id}")
@limiter.limit(f"{settings.RATE_LIMIT_WEBHOOK}/minute")
async def zapier_webhook(
    webhook_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    handler = get_handler("zapier")
    return await handler.handle(request, db, webhook_id=webhook_id)
