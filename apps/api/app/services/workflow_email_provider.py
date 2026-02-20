"""Centralized email provider resolution for workflows.

Resolves the correct email provider based on workflow scope:
- Personal workflows: User's connected Gmail (no fallback)
- Org workflows: Org's Resend or org's default Gmail sender (no fallback)

This module enforces no silent fallbacks - if the configured provider
is unavailable, it fails explicitly with a clear error message.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.services import oauth_service, resend_settings_service


class EmailProviderError(Exception):
    """Raised when email provider is not available for a workflow."""

    pass


def resolve_workflow_email_provider(
    db: Session,
    scope: str,
    org_id: UUID,
    owner_user_id: UUID | None,
) -> tuple[str, dict]:
    """
    Resolve email provider for a workflow.

    Args:
        db: Database session
        scope: Workflow scope ('org' or 'personal')
        org_id: Organization ID
        owner_user_id: Owner user ID (required for personal workflows)

    Returns:
        Tuple of (provider_type, config):
        - "resend": config = {"api_key_encrypted": ..., "from_email": ..., ...}
        - "org_gmail": config = {"sender_user_id": ..., "email": ...}
        - "user_gmail": config = {"user_id": ..., "email": ...}

    Raises:
        EmailProviderError: If the email provider is not available or misconfigured
    """
    if scope == "personal":
        return _resolve_personal_provider(db, owner_user_id)
    else:
        return _resolve_org_provider(db, org_id)


def _resolve_personal_provider(
    db: Session,
    owner_user_id: UUID | None,
) -> tuple[str, dict]:
    """Resolve email provider for personal workflows (user's Gmail)."""
    if not owner_user_id:
        raise EmailProviderError("Personal workflow missing owner")

    gmail = oauth_service.get_user_integration(db, owner_user_id, "gmail")
    if not gmail:
        raise EmailProviderError(
            "Workflow owner's Gmail is disconnected. Reconnect Gmail to enable email actions."
        )

    return "user_gmail", {
        "user_id": owner_user_id,
        "email": gmail.account_email,
    }


def _resolve_org_provider(
    db: Session,
    org_id: UUID,
) -> tuple[str, dict]:
    """Resolve email provider for org workflows (Resend or org Gmail)."""
    settings = resend_settings_service.get_resend_settings(db, org_id)

    if not settings or not settings.email_provider:
        raise EmailProviderError(
            "Org email provider not configured. "
            "Go to Settings → Integrations → Email Configuration."
        )

    # Check for Resend provider
    if settings.email_provider == "resend":
        if not settings.api_key_encrypted:
            raise EmailProviderError(
                "Resend API key not configured. "
                "Go to Settings → Integrations → Email Configuration."
            )
        if not settings.from_email:
            raise EmailProviderError(
                "Resend from_email not configured. "
                "Go to Settings → Integrations → Email Configuration."
            )

        return "resend", {
            "api_key_encrypted": settings.api_key_encrypted,
            "from_email": settings.from_email,
            "from_name": settings.from_name,
            "reply_to": settings.reply_to_email,
        }

    # Check for Gmail provider
    if settings.email_provider == "gmail":
        if not settings.default_sender_user_id:
            raise EmailProviderError(
                "Org Gmail default sender not configured. "
                "Go to Settings → Integrations → Email Configuration."
            )

        gmail = oauth_service.get_user_integration(db, settings.default_sender_user_id, "gmail")
        if not gmail:
            raise EmailProviderError(
                "Org default Gmail sender is disconnected. "
                "The selected sender needs to reconnect their Gmail."
            )

        return "org_gmail", {
            "sender_user_id": settings.default_sender_user_id,
            "email": gmail.account_email,
        }

    raise EmailProviderError(
        f"Unknown email provider: {settings.email_provider}. "
        "Go to Settings → Integrations → Email Configuration."
    )


def validate_email_provider(
    db: Session,
    scope: str,
    org_id: UUID,
    owner_user_id: UUID | None,
) -> tuple[bool, str | None]:
    """
    Check if email provider is available for a workflow.

    This is a validation helper for workflow creation/update to provide
    early feedback before the workflow is saved.

    Args:
        db: Database session
        scope: Workflow scope ('org' or 'personal')
        org_id: Organization ID
        owner_user_id: Owner user ID (required for personal workflows)

    Returns:
        Tuple of (is_valid, error_message):
        - (True, None) if provider is available
        - (False, "error message") if provider is not available
    """
    try:
        provider_type, _config = resolve_workflow_email_provider(db, scope, org_id, owner_user_id)
        if scope == "org" and provider_type != "resend":
            return (
                False,
                "Org workflows must use Resend. "
                "Set Email provider to Resend in Settings → Integrations → Email Configuration.",
            )
        return True, None
    except EmailProviderError as e:
        return False, str(e)


def get_provider_display_info(
    db: Session,
    scope: str,
    org_id: UUID,
    owner_user_id: UUID | None,
) -> dict:
    """
    Get display information about the email provider for a workflow.

    Returns a dict with provider info for the UI, or error info if not available.
    """
    try:
        provider_type, config = resolve_workflow_email_provider(db, scope, org_id, owner_user_id)
        return {
            "available": True,
            "provider_type": provider_type,
            "from_email": config.get("email") or config.get("from_email"),
            "error": None,
        }
    except EmailProviderError as e:
        return {
            "available": False,
            "provider_type": None,
            "from_email": None,
            "error": str(e),
        }
