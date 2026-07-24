"""Distributed no-burst request admission for outbound email providers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import EmailProviderAdmission


@dataclass(frozen=True, slots=True)
class ProviderRequestReservation:
    """A committed provider request slot safe to wait for outside a transaction."""

    send_at: datetime
    next_slot_at: datetime


def _normalize_admission_account(
    *,
    provider: str,
    provider_account_id: str,
) -> tuple[str, str]:
    normalized_provider = provider.strip().lower()
    normalized_account_id = provider_account_id.strip()
    if not normalized_provider:
        raise ValueError("provider is required")
    if len(normalized_provider) > 20:
        raise ValueError("provider must be 20 characters or fewer")
    if not normalized_account_id:
        raise ValueError("provider_account_id is required")
    if len(normalized_account_id) > 255:
        raise ValueError("provider_account_id must be 255 characters or fewer")
    return normalized_provider, normalized_account_id


def _validate_optional_now(now: datetime | None) -> None:
    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("now must be timezone-aware")


def _slot_interval(requests_per_second: int) -> timedelta:
    if requests_per_second < 1:
        raise ValueError("requests_per_second must be at least 1")
    if requests_per_second > 1_000_000:
        raise ValueError("requests_per_second must be 1,000,000 or fewer")
    return timedelta(microseconds=math.ceil(1_000_000 / requests_per_second))


def reserve_provider_request_slot(
    db: Session,
    *,
    provider: str,
    provider_account_id: str,
    requests_per_second: int,
    now: datetime | None = None,
) -> ProviderRequestReservation:
    """Commit one strictly spaced request slot for a provider account.

    PostgreSQL's unique-key conflict handling serializes creation of a new
    account state, and the subsequent row lock serializes every reservation.
    The commit occurs before this function returns so callers can wait and
    perform provider I/O without holding a database transaction.
    """
    normalized_provider, normalized_account_id = _normalize_admission_account(
        provider=provider,
        provider_account_id=provider_account_id,
    )
    _validate_optional_now(now)
    interval = _slot_interval(requests_per_second)

    try:
        initial_time = now or db.execute(select(func.clock_timestamp())).scalar_one()
        db.execute(
            insert(EmailProviderAdmission)
            .values(
                provider=normalized_provider,
                provider_account_id=normalized_account_id,
                next_slot_at=initial_time,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    EmailProviderAdmission.provider,
                    EmailProviderAdmission.provider_account_id,
                ]
            )
        )
        state = db.execute(
            select(EmailProviderAdmission)
            .where(
                EmailProviderAdmission.provider == normalized_provider,
                EmailProviderAdmission.provider_account_id == normalized_account_id,
            )
            .with_for_update()
        ).scalar_one()
        reservation_time = now or db.execute(select(func.clock_timestamp())).scalar_one()
        send_at = max(reservation_time, state.next_slot_at)
        next_slot_at = send_at + interval
        state.next_slot_at = next_slot_at
        db.commit()
    except Exception:
        db.rollback()
        raise

    return ProviderRequestReservation(
        send_at=send_at,
        next_slot_at=next_slot_at,
    )


def defer_provider_request_slot(
    db: Session,
    *,
    provider: str,
    provider_account_id: str,
    retry_after: timedelta,
    max_delay: timedelta,
    now: datetime | None = None,
) -> datetime:
    """Commit a bounded, monotonic provider-account deferral.

    The account row is locked before its current slot is compared so concurrent
    workers cannot move the shared provider schedule backwards.
    """
    normalized_provider, normalized_account_id = _normalize_admission_account(
        provider=provider,
        provider_account_id=provider_account_id,
    )
    _validate_optional_now(now)
    if retry_after <= timedelta(0):
        raise ValueError("retry_after must be positive")
    if max_delay <= timedelta(0):
        raise ValueError("max_delay must be positive")

    try:
        initial_time = now or db.execute(select(func.clock_timestamp())).scalar_one()
        db.execute(
            insert(EmailProviderAdmission)
            .values(
                provider=normalized_provider,
                provider_account_id=normalized_account_id,
                next_slot_at=initial_time,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    EmailProviderAdmission.provider,
                    EmailProviderAdmission.provider_account_id,
                ]
            )
        )
        state = db.execute(
            select(EmailProviderAdmission)
            .where(
                EmailProviderAdmission.provider == normalized_provider,
                EmailProviderAdmission.provider_account_id == normalized_account_id,
            )
            .with_for_update()
        ).scalar_one()
        reference_time = now or db.execute(select(func.clock_timestamp())).scalar_one()
        requested_next_slot = reference_time + min(retry_after, max_delay)
        deferred_until = max(state.next_slot_at, requested_next_slot)
        state.next_slot_at = deferred_until
        db.commit()
    except Exception:
        db.rollback()
        raise

    return deferred_until
