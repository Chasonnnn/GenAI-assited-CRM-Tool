"""Email Provider Service.

Resolves which email provider to use for campaigns and provides the necessary config.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ResendSettings, UserIntegration
from app.services import oauth_service, resend_settings_service

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when email provider is not properly configured."""

    pass


def resolve_campaign_provider(
    db: Session,
    org_id: uuid.UUID,
) -> tuple[str, Any]:
    """
    Resolve email provider for a campaign.

    Returns (provider_type, config).
    - For "resend": config is ResendSettings

    Raises ConfigurationError with a clear message for UI.
    """
    settings = resend_settings_service.get_resend_settings(db, org_id)

    if not settings or settings.email_provider is None:
        raise ConfigurationError(
            "Email provider not configured. Go to Settings → Integrations → Email Configuration."
        )

    if settings.email_provider != "resend":
        raise ConfigurationError(
            "Campaign emails must use Resend. "
            "Set Email provider to Resend in Settings → Integrations → Email Configuration."
        )

    return _resolve_resend(settings)


def _resolve_resend(settings: ResendSettings) -> tuple[str, ResendSettings]:
    """Validate and return Resend configuration."""
    if not settings.api_key_encrypted:
        raise ConfigurationError("Resend API key not configured.")

    if not settings.from_email:
        raise ConfigurationError("Resend from email not configured.")

    if not settings.verified_domain:
        raise ConfigurationError("Resend domain not verified.")

    return "resend", settings


def _resolve_gmail(db: Session, settings: ResendSettings) -> tuple[str, UserIntegration]:
    """Validate and return Gmail configuration."""
    if not settings.default_sender_user_id:
        raise ConfigurationError("Default Gmail sender not configured.")

    is_valid, error = resend_settings_service.validate_default_sender(
        db, settings.organization_id, settings.default_sender_user_id
    )
    if not is_valid:
        raise ConfigurationError(error or "Default Gmail sender is not eligible.")

    gmail = oauth_service.get_user_integration(db, settings.default_sender_user_id, "gmail")

    if not gmail:
        raise ConfigurationError(
            "Default sender's Gmail is no longer connected. "
            "Please select a different sender or reconnect Gmail."
        )

    return "gmail", gmail


def get_provider_display_name(provider: str | None) -> str:
    """Get display name for a provider."""
    if provider == "resend":
        return "Resend"
    if provider == "gmail":
        return "Gmail"
    return "Not configured"


def is_provider_configured(db: Session, org_id: uuid.UUID) -> tuple[bool, str | None]:
    """
    Check if an email provider is properly configured.

    Returns (is_configured, error_message).
    """
    try:
        resolve_campaign_provider(db, org_id)
        return True, None
    except ConfigurationError as e:
        return False, str(e)
