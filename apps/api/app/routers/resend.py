"""Resend email configuration router.

Endpoints for managing org-level email provider settings (Resend or Gmail).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession
from app.services import resend_settings_service

router = APIRouter(prefix="/resend", tags=["resend"])
logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================


class ResendSettingsResponse(BaseModel):
    """Resend settings for display (with masked key)."""

    email_provider: str | None
    api_key_masked: str | None
    from_email: str | None
    from_name: str | None
    reply_to_email: str | None
    verified_domain: str | None
    last_key_validated_at: str | None
    default_sender_user_id: str | None
    default_sender_name: str | None
    default_sender_email: str | None
    webhook_url: str
    webhook_signing_secret_configured: bool
    current_version: int


class ResendSettingsUpdate(BaseModel):
    """Update Resend settings."""

    email_provider: str | None = Field(None, pattern="^(resend|gmail|)$")
    api_key: str | None = None  # Plain text, will be encrypted
    from_email: str | None = None
    from_name: str | None = None
    reply_to_email: str | None = None
    webhook_signing_secret: str | None = None  # Plain text, stored encrypted
    default_sender_user_id: str | None = None
    expected_version: int | None = Field(None, description="Required for optimistic locking")


class TestKeyRequest(BaseModel):
    """Test a Resend API key."""

    api_key: str


class TestKeyResponse(BaseModel):
    """API key test result."""

    valid: bool
    error: str | None = None
    verified_domains: list[str] = []


class RotateWebhookResponse(BaseModel):
    """Response after rotating webhook URL routing token."""

    webhook_url: str


class EligibleSenderResponse(BaseModel):
    """A user eligible to be default Gmail sender."""

    user_id: str
    display_name: str
    email: str
    gmail_email: str


# ============================================================================
# Settings Endpoints (Admin Only)
# ============================================================================


@router.get("/settings", response_model=ResendSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
) -> ResendSettingsResponse:
    """Get Resend settings for the organization."""
    settings = resend_settings_service.get_or_create_resend_settings(
        db, session.org_id, session.user_id
    )

    # Get default sender info if set
    default_sender_name = None
    default_sender_email = None
    if settings.default_sender and settings.default_sender_user_id:
        default_sender_name = settings.default_sender.display_name
        default_sender_email = settings.default_sender.email

    return ResendSettingsResponse(
        email_provider=settings.email_provider,
        api_key_masked=resend_settings_service.mask_api_key(settings.api_key_encrypted),
        from_email=settings.from_email,
        from_name=settings.from_name,
        reply_to_email=settings.reply_to_email,
        verified_domain=settings.verified_domain,
        last_key_validated_at=(
            settings.last_key_validated_at.isoformat() if settings.last_key_validated_at else None
        ),
        default_sender_user_id=(
            str(settings.default_sender_user_id) if settings.default_sender_user_id else None
        ),
        default_sender_name=default_sender_name,
        default_sender_email=default_sender_email,
        webhook_url=resend_settings_service.get_webhook_url(settings.webhook_id),
        webhook_signing_secret_configured=bool(settings.webhook_secret_encrypted),
        current_version=settings.current_version,
    )


@router.patch(
    "/settings",
    response_model=ResendSettingsResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def update_settings(
    update: ResendSettingsUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
) -> ResendSettingsResponse:
    """Update Resend settings for the organization."""
    # Validate default sender if provided (non-empty)
    if "default_sender_user_id" in update.model_fields_set and update.default_sender_user_id:
        try:
            sender_id = uuid.UUID(update.default_sender_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid default_sender_user_id format",
            )

        is_valid, error = resend_settings_service.validate_default_sender(
            db, session.org_id, sender_id
        )
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # If API key is being updated, validate and get verified domain
    verified_domain = None
    if update.api_key:
        is_valid, error, domains = await resend_settings_service.test_api_key(update.api_key)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid API key: {error}",
            )
        if domains:
            verified_domain = domains[0]  # Use first verified domain

    # If from_email is being updated, validate it matches verified domain
    current_settings = resend_settings_service.get_resend_settings(db, session.org_id)
    if update.from_email:
        domain_to_check = verified_domain or (
            current_settings.verified_domain if current_settings else None
        )
        is_valid, error = resend_settings_service.validate_from_email(
            update.from_email, domain_to_check
        )
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Parse default sender ID (allow explicit clearing when field is set)
    default_sender_arg = resend_settings_service.UNSET
    if "default_sender_user_id" in update.model_fields_set:
        if update.default_sender_user_id:
            default_sender_arg = uuid.UUID(update.default_sender_user_id)
        else:
            default_sender_arg = None

    try:
        settings = resend_settings_service.update_resend_settings(
            db,
            session.org_id,
            session.user_id,
            email_provider=update.email_provider,
            api_key=update.api_key,
            from_email=update.from_email,
            from_name=update.from_name,
            reply_to_email=update.reply_to_email,
            verified_domain=verified_domain,
            webhook_signing_secret=update.webhook_signing_secret,
            default_sender_user_id=default_sender_arg,
            expected_version=update.expected_version,
        )
    except ValueError as e:
        if "Version conflict" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Update last_key_validated_at if key was tested
    if update.api_key:
        from datetime import datetime, timezone

        settings.last_key_validated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(settings)

    # Get default sender info
    default_sender_name = None
    default_sender_email = None
    if settings.default_sender and settings.default_sender_user_id:
        default_sender_name = settings.default_sender.display_name
        default_sender_email = settings.default_sender.email

    return ResendSettingsResponse(
        email_provider=settings.email_provider,
        api_key_masked=resend_settings_service.mask_api_key(settings.api_key_encrypted),
        from_email=settings.from_email,
        from_name=settings.from_name,
        reply_to_email=settings.reply_to_email,
        verified_domain=settings.verified_domain,
        last_key_validated_at=(
            settings.last_key_validated_at.isoformat() if settings.last_key_validated_at else None
        ),
        default_sender_user_id=(
            str(settings.default_sender_user_id) if settings.default_sender_user_id else None
        ),
        default_sender_name=default_sender_name,
        default_sender_email=default_sender_email,
        webhook_url=resend_settings_service.get_webhook_url(settings.webhook_id),
        webhook_signing_secret_configured=bool(settings.webhook_secret_encrypted),
        current_version=settings.current_version,
    )


@router.post(
    "/settings/test",
    response_model=TestKeyResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def test_api_key(
    request: TestKeyRequest,
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
) -> TestKeyResponse:
    """Test if a Resend API key is valid."""
    is_valid, error, domains = await resend_settings_service.test_api_key(request.api_key)
    return TestKeyResponse(valid=is_valid, error=error, verified_domains=domains)


@router.post(
    "/settings/rotate-webhook",
    response_model=RotateWebhookResponse,
    dependencies=[Depends(require_csrf_header)],
)
def rotate_webhook(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
) -> RotateWebhookResponse:
    """Rotate the webhook URL routing token (webhook_id)."""
    settings = resend_settings_service.rotate_webhook_id(db, session.org_id, session.user_id)
    return RotateWebhookResponse(
        webhook_url=resend_settings_service.get_webhook_url(settings.webhook_id),
    )


@router.get("/eligible-senders", response_model=list[EligibleSenderResponse])
def list_eligible_senders(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
) -> list[EligibleSenderResponse]:
    """List users eligible to be default Gmail senders (admin + Gmail connected)."""
    senders = resend_settings_service.list_eligible_senders(db, session.org_id)
    return [EligibleSenderResponse(**s) for s in senders]
