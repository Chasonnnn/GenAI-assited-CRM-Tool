"""Daily notification digest email.

Users who opt in get one email each morning (organization time zone) listing their
open action items and the updates they have not read from the last 24 hours. The
worker schedules one job per organization per local day; the job queues one platform
email per opted-in member in the transactional outbox. Nothing is sent inline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from html import escape as html_escape
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import JobType, NotificationTier
from app.db.models import Membership, Notification, Organization, User, UserNotificationSettings
from app.services import (
    job_service,
    notification_email_service,
    notification_service,
    org_service,
    platform_email_service,
)

logger = logging.getLogger(__name__)

SOURCE_TYPE = "notification_digest"
DIGEST_LOCAL_HOUR = 8
# A worker that was down at 8:00 still sends that morning, but not in the evening.
DIGEST_SEND_WINDOW = timedelta(hours=4)
DIGEST_LOOKBACK = timedelta(hours=24)
DIGEST_ITEM_LIMIT = 10


def _org_zone(org: Organization) -> ZoneInfo:
    try:
        return ZoneInfo(org.timezone or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def due_digest_date(org: Organization, now: datetime) -> date | None:
    """The org-local date whose digest is due now, or None outside the send window."""
    local_now = now.astimezone(_org_zone(org))
    send_at = datetime.combine(local_now.date(), time(DIGEST_LOCAL_HOUR), local_now.tzinfo)
    if send_at <= local_now < send_at + DIGEST_SEND_WINDOW:
        return local_now.date()
    return None


def job_idempotency_key(org_id: UUID, digest_date: date) -> str:
    return f"notification-digest:{org_id}:{digest_date.isoformat()}"


def email_idempotency_key(org_id: UUID, user_id: UUID, digest_date: date) -> str:
    return f"notification-digest:{org_id}:{user_id}:{digest_date.isoformat()}"


def _opted_in_recipients(db: Session, org_id: UUID, user_id: UUID | None = None) -> list[User]:
    query = (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .join(
            UserNotificationSettings,
            (UserNotificationSettings.user_id == User.id)
            & (UserNotificationSettings.organization_id == org_id),
        )
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
            UserNotificationSettings.email_daily_digest.is_(True),
        )
    )
    if user_id is not None:
        query = query.filter(User.id == user_id)
    return query.all()


def schedule_due_digest_jobs(db: Session, now: datetime) -> int:
    """Queue today's digest job for each org inside its morning send window."""
    scheduled = 0
    for org in org_service.list_orgs(db):
        digest_date = due_digest_date(org, now)
        if digest_date is None:
            continue
        key = job_idempotency_key(org.id, digest_date)
        if job_service.get_job_by_idempotency_key(db, org_id=org.id, idempotency_key=key):
            continue
        if not _opted_in_recipients(db, org.id):
            continue
        try:
            job_service.schedule_job(
                db=db,
                org_id=org.id,
                job_type=JobType.NOTIFICATION_DIGEST,
                payload={"org_id": str(org.id), "digest_date": digest_date.isoformat()},
                run_at=now,
                idempotency_key=key,
            )
        except IntegrityError:
            # Another worker queued the same org and day.
            db.rollback()
            continue
        scheduled += 1
    return scheduled


@dataclass(frozen=True)
class Digest:
    action_count: int
    actions: list[Notification]
    updates: list[Notification]
    more_updates: bool

    @property
    def is_empty(self) -> bool:
        return self.action_count == 0 and not self.updates


def build_digest(db: Session, user_id: UUID, org_id: UUID, now: datetime) -> Digest:
    actions, _ = notification_service.get_notifications(
        db, user_id, org_id, tier=NotificationTier.ACTION, limit=DIGEST_ITEM_LIMIT
    )
    updates, _ = notification_service.get_notifications(
        db,
        user_id,
        org_id,
        unread_only=True,
        tier=NotificationTier.UPDATE,
        created_after=now - DIGEST_LOOKBACK,
        limit=DIGEST_ITEM_LIMIT + 1,
    )
    counts = notification_service.get_notification_counts(db, user_id, org_id)
    return Digest(
        action_count=counts.action,
        actions=actions,
        updates=updates[:DIGEST_ITEM_LIMIT],
        more_updates=len(updates) > DIGEST_ITEM_LIMIT,
    )


def digest_title(digest: Digest) -> str:
    parts = []
    if digest.action_count:
        parts.append(f"{digest.action_count} need action")
    if digest.updates:
        count = f"{DIGEST_ITEM_LIMIT}+" if digest.more_updates else str(len(digest.updates))
        parts.append(f"{count} new update{'' if count == '1' else 's'}")
    return " · ".join(parts)


def _section_html(org: Organization, heading: str, items: list[Notification]) -> str:
    rows = []
    for notification in items:
        url = notification_email_service.record_url(org, notification)
        title = html_escape(notification.title)
        if url:
            title = (
                f'<a href="{html_escape(url, quote=True)}" target="_blank" '
                f'style="color: #111827; text-decoration: underline;">{title}</a>'
            )
        rows.append(
            '<li style="margin: 0 0 8px 0; font-size: 15px; line-height: 1.5; color: #374151;">'
            f"{title}</li>"
        )
    return (
        '<h2 style="margin: 16px 0 8px 0; font-size: 13px; letter-spacing: 0.05em; '
        f'text-transform: uppercase; color: #6b7280;">{html_escape(heading)}</h2>'
        f'<ul style="margin: 0; padding-left: 18px;">{"".join(rows)}</ul>'
    )


def _section_text(org: Organization, heading: str, items: list[Notification]) -> str:
    lines = [heading]
    for notification in items:
        url = notification_email_service.record_url(org, notification)
        lines.append(f"- {notification.title}" + (f" ({url})" if url else ""))
    return "\n".join(lines)


def render_digest(
    db: Session, *, org: Organization, digest: Digest
) -> tuple[str, str, str, str | None]:
    """Return (subject, html, text, from_email)."""
    sections: list[tuple[str, list[Notification]]] = []
    if digest.actions:
        heading = "Action needed"
        if digest.action_count > len(digest.actions):
            heading += f" ({len(digest.actions)} of {digest.action_count})"
        sections.append((heading, digest.actions))
    if digest.updates:
        heading = "Updates" + (f" (latest {DIGEST_ITEM_LIMIT})" if digest.more_updates else "")
        sections.append((heading, digest.updates))

    base_url = org_service.get_org_portal_base_url(org)
    inbox_url = f"{base_url}/notifications" if base_url else None
    title = digest_title(digest)
    subject, html, from_email = notification_email_service.render_staff_email(
        db,
        org=org,
        title=title,
        body_block="".join(_section_html(org, h, items) for h, items in sections),
        link_url=inbox_url,
        link_label="Open notifications",
    )
    text_parts = [title, *(_section_text(org, h, items) for h, items in sections)]
    if inbox_url:
        text_parts.append(f"Open notifications: {inbox_url}")
    return subject, html, "\n\n".join(text_parts) + "\n", from_email


def send_org_digests(db: Session, org_id: UUID, digest_date: date, now: datetime) -> dict:
    """Queue one digest email per opted-in member; skip members with nothing to report."""
    stats = {"queued": 0, "empty": 0, "failed": 0}
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None or org.deleted_at is not None:
        return stats
    if not platform_email_service.platform_sender_configured():
        logger.warning("Notification digest skipped: platform sender not configured org=%s", org_id)
        return stats

    for recipient in _opted_in_recipients(db, org_id):
        digest = build_digest(db, recipient.id, org_id, now)
        if digest.is_empty:
            stats["empty"] += 1
            continue
        subject, html, text, from_email = render_digest(db, org=org, digest=digest)
        result = platform_email_service.queue_email_logged(
            db=db,
            org_id=org_id,
            to_email=recipient.email,
            subject=subject,
            from_email=from_email,
            html=html,
            text=text,
            idempotency_key=email_idempotency_key(org_id, recipient.id, digest_date),
            source_type=SOURCE_TYPE,
            source_id=recipient.id,
            commit=False,
        )
        if result.get("success"):
            stats["queued"] += 1
        else:
            # Errors from queue_email_logged are fixed strings without recipient or content.
            logger.warning(
                "Notification digest not queued org=%s user=%s reason=%s",
                org_id,
                recipient.id,
                result.get("error"),
            )
            stats["failed"] += 1
    db.commit()
    return stats


def is_digest_delivery_eligible(
    db: Session,
    org_id: UUID,
    user_id: UUID | None,
    recipient_email: str | None,
) -> bool:
    """Re-check membership, opt-in, and address before the outbox sends."""
    if user_id is None:
        return False
    recipients = _opted_in_recipients(db, org_id, user_id)
    if not recipients:
        return False
    recipient = recipients[0]
    return (recipient.email or "").strip().lower() == (recipient_email or "").strip().lower()
