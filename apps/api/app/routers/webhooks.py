"""Webhooks router - external service integrations."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.services import google_calendar_sync_service
from app.services.webhooks import get_handler
from app.services.webhooks.meta import simulate_meta_webhook as simulate_meta_webhook_handler

# Rate limiting
from app.core.rate_limit import limiter

router = APIRouter()


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

    result = google_calendar_sync_service.process_google_calendar_push_notification(
        db=db,
        channel_id=channel_id,
        resource_id=resource_id,
        channel_token=channel_token,
        message_number=message_number,
        resource_state=resource_state,
    )
    return JSONResponse(result, status_code=202)


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
