"""Renew push channels for explicitly scoped calendar bindings."""

from __future__ import annotations

import logging
import secrets
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CalendarBinding, Membership, UserIntegration
from app.db.session import SessionLocal
from app.services import calendar_service, oauth_service

logger = logging.getLogger(__name__)


def _binding_query(db: Session, binding_id: UUID, org_id: UUID):
    return (
        db.query(CalendarBinding)
        .join(
            Membership,
            (Membership.organization_id == CalendarBinding.organization_id)
            & (Membership.user_id == CalendarBinding.user_id),
        )
        .join(UserIntegration, UserIntegration.id == CalendarBinding.integration_id)
        .filter(
            CalendarBinding.id == binding_id,
            CalendarBinding.organization_id == org_id,
            CalendarBinding.is_active.is_(True),
            Membership.is_active.is_(True),
            UserIntegration.user_id == CalendarBinding.user_id,
            UserIntegration.integration_type == "google_calendar",
            UserIntegration.account_email == CalendarBinding.account_email,
        )
    )


async def _stop_channel(access_token: str, channel_id: str | None, resource_id: str | None):
    if channel_id and resource_id:
        try:
            await calendar_service._post_google_channel_stop(
                access_token=access_token, channel_id=channel_id, resource_id=resource_id
            )
        except Exception:
            # Channels expire independently. Never expose provider response bodies.
            logger.warning("Google Calendar superseded channel cleanup failed")


async def ensure_binding_watch(db: Session, *, binding_id: UUID, org_id: UUID) -> bool:
    """Publish a replacement before retiring the previous channel, with identity fencing."""
    if not settings.SCHEDULING_V2_ENABLED:
        return False
    binding = _binding_query(db, binding_id, org_id).one_or_none()
    if binding is None:
        return False
    if (
        binding.channel_id
        and binding.resource_id
        and binding.channel_token_encrypted
        and calendar_service._watch_is_fresh(
            binding.channel_expires_at, renew_before=calendar_service.WATCH_RENEW_BUFFER
        )
    ):
        return False
    identity = (binding.user_id, binding.integration_id, binding.account_email, binding.calendar_id)
    previous = (binding.channel_id, binding.resource_id)
    db.commit()

    # Token refresh has its own transaction; the job holds no binding lock during HTTP.
    with SessionLocal() as credentials:
        current = _binding_query(credentials, binding_id, org_id).one_or_none()
        if (
            current is None
            or (current.user_id, current.integration_id, current.account_email, current.calendar_id)
            != identity
        ):
            return False
        access_token = await calendar_service.get_google_access_token(credentials, identity[0])
    if not access_token:
        raise ValueError("Google Calendar authorization unavailable")
    channel_token = secrets.token_urlsafe(32)
    result = await calendar_service._post_google_events_watch(
        access_token=access_token,
        calendar_id=identity[3],
        channel_id=str(uuid4()),
        channel_token=channel_token,
        ttl_seconds=calendar_service.WATCH_CHANNEL_TTL_SECONDS,
    )
    if result is None:
        raise ValueError("Google Calendar watch renewal failed")

    binding = (
        _binding_query(db, binding_id, org_id)
        .populate_existing()
        .with_for_update(of=CalendarBinding)
        .one_or_none()
    )
    unchanged = (
        binding is not None
        and (binding.user_id, binding.integration_id, binding.account_email, binding.calendar_id)
        == identity
        and (binding.channel_id, binding.resource_id) == previous
    )
    if not unchanged:
        db.rollback()
        await _stop_channel(access_token, result["channel_id"], result["resource_id"])
        return False
    binding.channel_id = result["channel_id"]
    binding.resource_id = result["resource_id"]
    binding.channel_token_encrypted = oauth_service.encrypt_token(channel_token)
    binding.channel_expires_at = result["expires_at"]
    db.commit()
    await _stop_channel(access_token, *previous)
    return True
