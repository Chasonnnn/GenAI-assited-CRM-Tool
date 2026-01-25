"""Resend Settings service.

Manages org-level email provider configuration with BYOK key storage.
Supports Resend API and Gmail default sender.
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Membership, ResendSettings, User, UserIntegration

UNSET = object()

logger = logging.getLogger(__name__)

# Resend API
RESEND_API_BASE = "https://api.resend.com"
RESEND_TIMEOUT = 10.0


def _get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    key = settings.FERNET_KEY
    if not key:
        raise ValueError("FERNET_KEY not configured")
    return Fernet(key.encode())


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    fernet = _get_fernet()
    return fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt a stored API key."""
    fernet = _get_fernet()
    return fernet.decrypt(encrypted_key.encode()).decode()


def mask_api_key(api_key_encrypted: str | None) -> str | None:
    """Return masked version of API key for display.

    Shows first 4 and last 4 characters: re_ab...yz
    """
    if not api_key_encrypted:
        return None

    try:
        decrypted = decrypt_api_key(api_key_encrypted)
        if len(decrypted) <= 8:
            return "****"
        return f"{decrypted[:4]}...{decrypted[-4:]}"
    except Exception:
        return "****"


def get_resend_settings(db: Session, organization_id: uuid.UUID) -> ResendSettings | None:
    """Get Resend settings for an organization."""
    return (
        db.query(ResendSettings).filter(ResendSettings.organization_id == organization_id).first()
    )


def get_settings_by_webhook_id(db: Session, webhook_id: str) -> ResendSettings | None:
    """Get Resend settings by webhook ID (for webhook routing)."""
    return db.query(ResendSettings).filter(ResendSettings.webhook_id == webhook_id).first()


def _generate_webhook_secret() -> str:
    """Generate a Svix-compatible webhook secret (whsec_ prefix)."""
    import base64

    raw = secrets.token_bytes(32)
    encoded = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    return f"whsec_{encoded}"


def get_or_create_resend_settings(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> ResendSettings:
    """Get or create Resend settings for an organization."""
    s = get_resend_settings(db, organization_id)
    if s:
        return s

    # Generate webhook ID and initial secret
    webhook_id = str(uuid.uuid4())
    webhook_secret = _generate_webhook_secret()

    s = ResendSettings(
        organization_id=organization_id,
        email_provider=None,  # Not configured
        webhook_id=webhook_id,
        webhook_secret_encrypted=encrypt_api_key(webhook_secret),
        current_version=1,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def update_resend_settings(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    email_provider: str | None = None,
    api_key: str | None = None,  # Plain text, will be encrypted
    from_email: str | None = None,
    from_name: str | None = None,
    reply_to_email: str | None = None,
    verified_domain: str | None = None,
    default_sender_user_id: uuid.UUID | None | object = UNSET,
    expected_version: int | None = None,
) -> ResendSettings:
    """Update Resend settings with optimistic locking."""
    s = get_or_create_resend_settings(db, organization_id, user_id)

    # Optimistic locking
    if expected_version is not None and s.current_version != expected_version:
        raise ValueError(f"Version conflict: expected {expected_version}, got {s.current_version}")

    if email_provider is not None:
        if email_provider not in ("resend", "gmail", ""):
            raise ValueError("email_provider must be 'resend', 'gmail', or empty")
        s.email_provider = email_provider if email_provider else None

    if api_key is not None:
        s.api_key_encrypted = encrypt_api_key(api_key) if api_key else None

    if from_email is not None:
        s.from_email = from_email if from_email else None

    if from_name is not None:
        s.from_name = from_name if from_name else None

    if reply_to_email is not None:
        s.reply_to_email = reply_to_email if reply_to_email else None

    if verified_domain is not None:
        s.verified_domain = verified_domain if verified_domain else None

    if default_sender_user_id is not UNSET:
        s.default_sender_user_id = default_sender_user_id

    s.current_version += 1
    s.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(s)
    return s


def clear_default_sender(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ResendSettings:
    """Clear the default sender (used when clearing Gmail sender selection)."""
    s = get_or_create_resend_settings(db, organization_id, user_id)
    s.default_sender_user_id = None
    s.current_version += 1
    s.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(s)
    return s


def rotate_webhook_secret(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[ResendSettings, str]:
    """Rotate the webhook secret. Returns the new plain secret (shown once)."""
    s = get_or_create_resend_settings(db, organization_id, user_id)

    # Generate new secret
    new_secret = _generate_webhook_secret()
    s.webhook_secret_encrypted = encrypt_api_key(new_secret)
    s.current_version += 1
    s.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(s)
    return s, new_secret


async def test_api_key(api_key: str) -> tuple[bool, str | None, list[str]]:
    """
    Test if a Resend API key is valid by fetching domains.

    Returns (is_valid, error_message, verified_domains).
    """
    try:
        async with httpx.AsyncClient(timeout=RESEND_TIMEOUT) as client:
            response = await client.get(
                f"{RESEND_API_BASE}/domains",
                headers={"Authorization": f"Bearer {api_key}"},
            )

        if response.status_code == 401:
            return False, "Invalid API key", []

        if response.status_code == 403:
            return False, "API key lacks permission to access domains", []

        if response.status_code != 200:
            return False, f"Resend API error: {response.status_code}", []

        data = response.json()
        domains = data.get("data", [])

        # Extract verified domains
        verified = [
            d.get("name")
            for d in domains
            if isinstance(d, dict) and d.get("status") == "verified" and d.get("name")
        ]

        return True, None, verified

    except httpx.TimeoutException:
        return False, "Connection timeout", []
    except Exception as e:
        logger.exception("Error testing Resend API key")
        return False, f"Connection error: {e.__class__.__name__}", []


def validate_from_email(from_email: str, verified_domain: str | None) -> tuple[bool, str | None]:
    """
    Validate that from_email matches the verified domain.

    Returns (is_valid, error_message).
    """
    if not verified_domain:
        return False, "No verified domain configured"

    if not from_email:
        return False, "From email is required"

    # Extract domain from email
    if "@" not in from_email:
        return False, "Invalid email format"

    email_domain = from_email.split("@")[1].lower()
    if email_domain != verified_domain.lower():
        return False, f"From email must use the verified domain: {verified_domain}"

    return True, None


def list_eligible_senders(
    db: Session,
    organization_id: uuid.UUID,
) -> list[dict]:
    """
    List users eligible to be default Gmail senders.

    Eligibility: same org + admin role + Gmail connected.
    """
    # Get all admin users in the org with active memberships
    admin_memberships = (
        db.query(Membership)
        .filter(
            Membership.organization_id == organization_id,
            Membership.role == "admin",
            Membership.is_active == True,  # noqa: E712
        )
        .all()
    )

    if not admin_memberships:
        return []

    admin_user_ids = [m.user_id for m in admin_memberships]

    # Get users with Gmail connected
    users_with_gmail = (
        db.query(User, UserIntegration)
        .join(UserIntegration, User.id == UserIntegration.user_id)
        .filter(
            User.id.in_(admin_user_ids),
            User.is_active == True,  # noqa: E712
            UserIntegration.integration_type == "gmail",
        )
        .all()
    )

    result = []
    for user, integration in users_with_gmail:
        result.append(
            {
                "user_id": str(user.id),
                "display_name": user.display_name,
                "email": user.email,
                "gmail_email": integration.account_email or user.email,
            }
        )

    return result


def validate_default_sender(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[bool, str | None]:
    """
    Validate that a user is eligible to be the default sender.

    Requirements: same org + admin role + Gmail connected.
    Returns (is_valid, error_message).
    """
    # Check membership
    membership = (
        db.query(Membership)
        .filter(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
            Membership.is_active == True,  # noqa: E712
        )
        .first()
    )

    if not membership:
        return False, "User is not a member of this organization"

    if membership.role != "admin":
        return False, "Only admin users can be default senders"

    # Check Gmail connection
    gmail = (
        db.query(UserIntegration)
        .filter(
            UserIntegration.user_id == user_id,
            UserIntegration.integration_type == "gmail",
        )
        .first()
    )

    if not gmail:
        return False, "User does not have Gmail connected"

    return True, None


def get_webhook_url(webhook_id: str) -> str:
    """Generate the webhook URL for Resend configuration."""
    base_url = settings.API_BASE_URL or settings.FRONTEND_URL or ""
    if not base_url:
        logger.warning("API_BASE_URL not configured; webhook URL unavailable")
        return ""
    return f"{base_url.rstrip('/')}/webhooks/resend/{webhook_id}"
