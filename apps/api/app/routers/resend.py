"""Resend email configuration router.

Endpoints for managing org-level email provider settings (Resend or Gmail).
"""

from typing import Annotated

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession
from app.services import resend_admission_identity, resend_settings_service

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
    rate_limit_group_configured: bool
    current_version: int


class ResendSettingsUpdate(BaseModel):
    """Update Resend settings."""

    email_provider: str | None = Field(None, pattern="^(resend|gmail|)$")
    api_key: str | None = None  # Plain text, will be encrypted
    from_email: str | None = None
    from_name: str | None = None
    reply_to_email: str | None = None
    verified_domain: str | None = None
    webhook_signing_secret: str | None = None  # Plain text, stored encrypted
    rate_limit_group_token: str | None = None
    default_sender_user_id: str | None = None
    expected_version: int | None = Field(None, description="Required for optimistic locking")

    @field_validator("rate_limit_group_token")
    @classmethod
    def validate_rate_limit_group_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized and not 32 <= len(normalized) <= 256:
            raise ValueError("rate_limit_group_token must be between 32 and 256 characters")
        return normalized


class TestKeyRequest(BaseModel):
    """Test a Resend API key."""

    api_key: str


class TestKeyResponse(BaseModel):
    """API key test result."""

    valid: bool
    error: str | None = None
    verified_domains: list[str] = Field(default_factory=list)
    permission_limited: bool = False
    warning: str | None = None


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
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
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
        rate_limit_group_configured=bool(settings.rate_limit_group_fingerprint),
        current_version=settings.current_version,
    )


@router.patch(
    "/settings",
    response_model=ResendSettingsResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def update_settings(
    update: ResendSettingsUpdate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
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

    current_settings = resend_settings_service.get_resend_settings(db, session.org_id)
    fields_set = update.model_fields_set
    if "rate_limit_group_token" in fields_set:
        rate_limit_group_fingerprint = (
            resend_admission_identity.admission_group_fingerprint(update.rate_limit_group_token)
            if update.rate_limit_group_token
            else None
        )
    else:
        rate_limit_group_fingerprint = (
            current_settings.rate_limit_group_fingerprint if current_settings is not None else None
        )
    explicit_domain = (
        update.verified_domain.strip().lower()
        if "verified_domain" in fields_set and update.verified_domain
        else None
    )
    explicit_from_email = (
        update.from_email.strip() if "from_email" in fields_set and update.from_email else None
    )
    new_api_key = update.api_key.strip() if "api_key" in fields_set and update.api_key else None
    requested_provider = (
        update.email_provider
        if "email_provider" in fields_set
        else (current_settings.email_provider if current_settings else None)
    )
    sender_identity_changed = bool(
        current_settings
        and (
            (
                "verified_domain" in fields_set
                and explicit_domain != current_settings.verified_domain
            )
            or ("from_email" in fields_set and explicit_from_email != current_settings.from_email)
        )
    )
    if requested_provider == "resend" and sender_identity_changed and not new_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Re-enter the Resend API key to revalidate a changed sender "
                "email or verified domain."
            ),
        )

    # A new key must always be paired with administrator-supplied route identity.
    # Domain-list results are evidence only and never select configuration.
    if new_api_key:
        if not explicit_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verified domain is required when saving a Resend API key.",
            )
        if not explicit_from_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="From email is required when saving a Resend API key.",
            )

        validation = await resend_settings_service.test_api_key(
            new_api_key,
            db=db,
            rate_limit_group_fingerprint=rate_limit_group_fingerprint,
        )
        if not validation.valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid API key: {validation.error}",
            )

        if not validation.permission_limited and explicit_domain not in set(
            validation.verified_domains
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Verified domain is not in the verified domains available "
                    "to this Resend API key."
                ),
            )

    effective_provider = current_settings.email_provider if current_settings else None
    effective_domain = current_settings.verified_domain if current_settings else None
    effective_from_email = current_settings.from_email if current_settings else None
    if "email_provider" in fields_set:
        effective_provider = update.email_provider
    if "verified_domain" in fields_set:
        effective_domain = explicit_domain
    if "from_email" in fields_set:
        effective_from_email = explicit_from_email
    effective_key_configured = bool(
        new_api_key
        or ("api_key" not in fields_set and current_settings and current_settings.api_key_encrypted)
    )

    if effective_provider == "resend":
        if not effective_key_configured:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resend API key is required.",
            )
        if not effective_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verified domain is required.",
            )
        if not effective_from_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="From email is required.",
            )
        is_valid, error = resend_settings_service.validate_from_email(
            effective_from_email,
            effective_domain,
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

    api_key_arg = None
    if "api_key" in fields_set:
        api_key_arg = new_api_key or ""
    verified_domain_arg = None
    if "verified_domain" in fields_set:
        verified_domain_arg = explicit_domain or ""
    from_email_arg = None
    if "from_email" in fields_set:
        from_email_arg = explicit_from_email or ""
    rate_limit_group_token_arg = resend_settings_service.UNSET
    if "rate_limit_group_token" in fields_set:
        rate_limit_group_token_arg = update.rate_limit_group_token or ""

    try:
        settings = resend_settings_service.update_resend_settings(
            db,
            session.org_id,
            session.user_id,
            email_provider=update.email_provider,
            api_key=api_key_arg,
            from_email=from_email_arg,
            from_name=update.from_name,
            reply_to_email=update.reply_to_email,
            verified_domain=verified_domain_arg,
            webhook_signing_secret=update.webhook_signing_secret,
            rate_limit_group_token=rate_limit_group_token_arg,
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
    if new_api_key:
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
        rate_limit_group_configured=bool(settings.rate_limit_group_fingerprint),
        current_version=settings.current_version,
    )


@router.post(
    "/settings/test",
    response_model=TestKeyResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def test_api_key(
    request: TestKeyRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
) -> TestKeyResponse:
    """Test if a Resend API key is valid."""
    current_settings = resend_settings_service.get_resend_settings(db, session.org_id)
    result = await resend_settings_service.test_api_key(
        request.api_key,
        db=db,
        rate_limit_group_fingerprint=(
            current_settings.rate_limit_group_fingerprint if current_settings is not None else None
        ),
    )
    return TestKeyResponse(
        valid=result.valid,
        error=result.error,
        verified_domains=result.verified_domains,
        permission_limited=result.permission_limited,
        warning=result.warning,
    )


@router.post(
    "/settings/rotate-webhook",
    response_model=RotateWebhookResponse,
    dependencies=[Depends(require_csrf_header)],
)
def rotate_webhook(
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
) -> RotateWebhookResponse:
    """Rotate the webhook URL routing token (webhook_id)."""
    settings = resend_settings_service.rotate_webhook_id(db, session.org_id, session.user_id)
    return RotateWebhookResponse(
        webhook_url=resend_settings_service.get_webhook_url(settings.webhook_id),
    )


@router.get("/eligible-senders", response_model=list[EligibleSenderResponse])
def list_eligible_senders(
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
) -> list[EligibleSenderResponse]:
    """List users eligible to be default Gmail senders (admin + Gmail connected)."""
    senders = resend_settings_service.list_eligible_senders(db, session.org_id)
    return [EligibleSenderResponse(**s) for s in senders]
