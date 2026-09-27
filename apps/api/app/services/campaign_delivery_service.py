"""Campaign delivery locks, projections, and aggregate state."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.enums import CampaignRecipientStatus, CampaignStatus, EmailStatus
from app.db.models import (
    Campaign,
    CampaignRecipient,
    CampaignRun,
)
from app.services import campaign_access


def lock_campaign_run_and_campaign(
    db: Session,
    *,
    organization_id: UUID,
    run_id: UUID,
) -> tuple[CampaignRun, Campaign] | None:
    """Acquire the canonical run -> campaign row-lock order."""
    run = (
        db.query(CampaignRun)
        .filter(
            CampaignRun.id == run_id,
            CampaignRun.organization_id == organization_id,
        )
        .with_for_update(of=CampaignRun)
        .populate_existing()
        .one_or_none()
    )
    if run is None:
        return None
    campaign = (
        db.query(Campaign)
        .filter(
            Campaign.id == run.campaign_id,
            Campaign.organization_id == organization_id,
        )
        .with_for_update(of=Campaign)
        .populate_existing()
        .one_or_none()
    )
    if campaign is None:
        return None
    return run, campaign


def _campaign_run_id_for_email_log(
    db: Session,
    *,
    organization_id: UUID,
    email_log_id: UUID,
) -> UUID | None:
    return (
        db.query(CampaignRecipient.run_id)
        .join(CampaignRun, CampaignRun.id == CampaignRecipient.run_id)
        .join(Campaign, Campaign.id == CampaignRun.campaign_id)
        .filter(
            CampaignRecipient.email_log_id == email_log_id,
            CampaignRun.organization_id == organization_id,
            Campaign.organization_id == organization_id,
        )
        .scalar()
    )


def lock_campaign_run_for_email_log(
    db: Session,
    *,
    organization_id: UUID,
    email_log_id: UUID,
) -> UUID | None:
    """Pre-lock campaign aggregates before a delivery or webhook row mutation."""
    run_id = _campaign_run_id_for_email_log(
        db,
        organization_id=organization_id,
        email_log_id=email_log_id,
    )
    if run_id is None:
        return None
    if (
        lock_campaign_run_and_campaign(
            db,
            organization_id=organization_id,
            run_id=run_id,
        )
        is None
    ):
        return None
    return run_id


def lock_campaign_run_for_message_delivery(
    db: Session, *, organization_id: UUID, message_delivery_id: UUID
) -> None:
    """Acquire campaign aggregates before the messaging outbox row."""
    run_id = (
        db.query(CampaignRecipient.run_id)
        .join(CampaignRun, CampaignRun.id == CampaignRecipient.run_id)
        .filter(
            CampaignRecipient.message_delivery_id == message_delivery_id,
            CampaignRun.organization_id == organization_id,
        )
        .scalar()
    )
    if run_id is not None:
        lock_campaign_run_and_campaign(db, organization_id=organization_id, run_id=run_id)


def is_campaign_recipient_delivery_eligible(
    db: Session,
    org_id: UUID,
    recipient_id: UUID,
    *,
    email_log_id: UUID | None = None,
    message_delivery_id: UUID | None = None,
) -> bool:
    """Lock and check whether a campaign recipient may still be sent."""
    run_id = (
        db.query(CampaignRecipient.run_id)
        .join(CampaignRun, CampaignRun.id == CampaignRecipient.run_id)
        .join(Campaign, Campaign.id == CampaignRun.campaign_id)
        .filter(
            CampaignRecipient.id == recipient_id,
            CampaignRun.organization_id == org_id,
            Campaign.organization_id == org_id,
        )
        .scalar()
    )
    if run_id is None:
        return False
    locked = lock_campaign_run_and_campaign(
        db,
        organization_id=org_id,
        run_id=run_id,
    )
    if locked is None:
        return False
    run, campaign = locked
    recipient = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.id == recipient_id,
            CampaignRecipient.run_id == run.id,
        )
        .with_for_update(of=CampaignRecipient)
        .one_or_none()
    )
    if recipient is not None and (
        (email_log_id is not None and recipient.email_log_id != email_log_id)
        or (
            message_delivery_id is not None and recipient.message_delivery_id != message_delivery_id
        )
    ):
        return False
    if recipient is not None and not campaign_access.recipient_allowed(
        db, campaign, run, recipient.entity_id
    ):
        recipient.status = CampaignRecipientStatus.SKIPPED.value
        recipient.skip_reason = "permission_revoked"
        recipient.error = None
        recompute_campaign_run_aggregates(db, organization_id=org_id, run_id=run.id, commit=False)
        return False
    return bool(
        recipient is not None
        and recipient.status == CampaignRecipientStatus.PENDING.value
        and run.status == "running"
        and campaign.status == CampaignStatus.SENDING.value
    )


def recompute_campaign_run_aggregates(
    db: Session,
    *,
    organization_id: UUID,
    run_id: UUID,
    commit: bool = True,
) -> bool:
    """Recompute one tenant campaign run from its recipient source of truth."""
    # The stable run -> campaign lock order serializes outbox and webhook
    # projections without allowing concurrent writers to publish stale totals.
    db.flush()
    locked = lock_campaign_run_and_campaign(
        db,
        organization_id=organization_id,
        run_id=run_id,
    )
    if locked is None:
        return False
    run, campaign = locked

    status_rows = (
        db.query(CampaignRecipient.status, func.count(CampaignRecipient.id))
        .filter(CampaignRecipient.run_id == run.id)
        .group_by(CampaignRecipient.status)
        .all()
    )
    status_counts = {status: count for status, count in status_rows}
    engagement_counts = (
        db.query(
            func.count(CampaignRecipient.id)
            .filter(CampaignRecipient.opened_at.isnot(None))
            .label("opened_count"),
            func.count(CampaignRecipient.id)
            .filter(CampaignRecipient.clicked_at.isnot(None))
            .label("clicked_count"),
        )
        .filter(CampaignRecipient.run_id == run.id)
        .one()
    )

    delivered_count = status_counts.get(CampaignRecipientStatus.DELIVERED.value, 0)
    failed_count = status_counts.get(CampaignRecipientStatus.FAILED.value, 0)
    pending_count = status_counts.get(CampaignRecipientStatus.PENDING.value, 0)
    run.sent_count = status_counts.get(CampaignRecipientStatus.SENT.value, 0) + delivered_count
    run.delivered_count = delivered_count
    run.failed_count = failed_count
    run.skipped_count = status_counts.get(CampaignRecipientStatus.SKIPPED.value, 0)
    run.opened_count = engagement_counts.opened_count
    run.clicked_count = engagement_counts.clicked_count

    now = datetime.now(UTC)
    was_terminal = run.status in {"completed", "failed"} and run.completed_at is not None
    if campaign.status == CampaignStatus.CANCELLED.value:
        run.status = "failed"
        run.completed_at = run.completed_at or now
        run.error_message = run.error_message or "cancelled"
    elif pending_count:
        run.status = "running"
        run.completed_at = None
        campaign.status = CampaignStatus.SENDING.value
    else:
        run.status = "failed" if failed_count else "completed"
        if not was_terminal:
            run.completed_at = now
        campaign.status = (
            CampaignStatus.FAILED.value if failed_count else CampaignStatus.COMPLETED.value
        )

    campaign.sent_count = run.sent_count
    campaign.delivered_count = run.delivered_count
    campaign.failed_count = run.failed_count
    campaign.skipped_count = run.skipped_count
    campaign.total_recipients = run.total_count

    if commit:
        db.commit()
    else:
        db.flush()
    return True


def project_campaign_recipient_delivery(
    db: Session,
    *,
    organization_id: UUID,
    email_log_id: UUID,
    status: str,
    provider_message_id: str | None = None,
    error: str | None = None,
    occurred_at: datetime | None = None,
    commit: bool = True,
) -> bool:
    """Project a fenced outbox result onto its tenant-scoped campaign recipient."""
    if status not in {
        EmailStatus.SENT.value,
        EmailStatus.FAILED.value,
        EmailStatus.SKIPPED.value,
    }:
        raise ValueError("unsupported campaign delivery projection status")
    if status == EmailStatus.SENT.value and not provider_message_id:
        raise ValueError("provider_message_id is required for sent projection")

    run_id = _campaign_run_id_for_email_log(
        db,
        organization_id=organization_id,
        email_log_id=email_log_id,
    )
    if run_id is None:
        return False
    if (
        lock_campaign_run_and_campaign(
            db,
            organization_id=organization_id,
            run_id=run_id,
        )
        is None
    ):
        return False

    recipient = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.email_log_id == email_log_id,
            CampaignRecipient.run_id == run_id,
        )
        .with_for_update(of=CampaignRecipient)
        .one_or_none()
    )
    if recipient is None:
        return False

    if status == EmailStatus.SENT.value:
        if recipient.status in {
            CampaignRecipientStatus.PENDING.value,
            CampaignRecipientStatus.SENT.value,
        }:
            recipient.status = CampaignRecipientStatus.SENT.value
        if recipient.status in {
            CampaignRecipientStatus.SENT.value,
            CampaignRecipientStatus.DELIVERED.value,
        }:
            projected_at = occurred_at or datetime.now(UTC)
            if recipient.sent_at is None or projected_at < recipient.sent_at:
                recipient.sent_at = projected_at
            if recipient.external_message_id is None:
                recipient.external_message_id = provider_message_id
            recipient.error = None
            recipient.skip_reason = None
    elif status == EmailStatus.FAILED.value and recipient.status in {
        CampaignRecipientStatus.PENDING.value,
        CampaignRecipientStatus.FAILED.value,
    }:
        recipient.status = CampaignRecipientStatus.FAILED.value
        recipient.error = (error or "Send failed")[:500]
        recipient.skip_reason = None
    elif recipient.status in {
        CampaignRecipientStatus.PENDING.value,
        CampaignRecipientStatus.SKIPPED.value,
    }:
        recipient.status = CampaignRecipientStatus.SKIPPED.value
        recipient.error = None
        recipient.skip_reason = (error or "skipped")[:100]

    if not recompute_campaign_run_aggregates(
        db,
        organization_id=organization_id,
        run_id=recipient.run_id,
        commit=False,
    ):
        raise RuntimeError("Campaign aggregate projection target is missing")

    if commit:
        db.commit()
    else:
        db.flush()
    return True


def project_campaign_message_delivery(
    db: Session,
    *,
    organization_id: UUID,
    message_delivery_id: UUID,
    status: str,
    provider_message_id: str | None = None,
    error: str | None = None,
    occurred_at: datetime | None = None,
    commit: bool = True,
) -> bool:
    """Project a messaging outbox status onto its campaign recipient."""
    if status not in {
        "submitted",
        "delivered",
        "failed",
        "cancelled",
        "reconciliation_required",
    }:
        raise ValueError("unsupported campaign message delivery projection status")
    run_id = (
        db.query(CampaignRecipient.run_id)
        .join(CampaignRun, CampaignRun.id == CampaignRecipient.run_id)
        .filter(
            CampaignRecipient.message_delivery_id == message_delivery_id,
            CampaignRun.organization_id == organization_id,
        )
        .scalar()
    )
    if run_id is None:
        return False
    if (
        lock_campaign_run_and_campaign(
            db,
            organization_id=organization_id,
            run_id=run_id,
        )
        is None
    ):
        return False
    recipient = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.run_id == run_id,
            CampaignRecipient.message_delivery_id == message_delivery_id,
        )
        .with_for_update(of=CampaignRecipient)
        .one_or_none()
    )
    if recipient is None:
        return False

    projected_at = occurred_at or datetime.now(UTC)
    if status == "delivered":
        recipient.status = CampaignRecipientStatus.DELIVERED.value
        recipient.sent_at = recipient.sent_at or projected_at
        recipient.external_message_id = recipient.external_message_id or provider_message_id
        recipient.error = None
        recipient.skip_reason = None
    elif status == "submitted" and recipient.status in {
        CampaignRecipientStatus.PENDING.value,
        CampaignRecipientStatus.SENT.value,
    }:
        recipient.status = CampaignRecipientStatus.SENT.value
        recipient.sent_at = recipient.sent_at or projected_at
        recipient.external_message_id = recipient.external_message_id or provider_message_id
        recipient.error = None
        recipient.skip_reason = None
    elif status in {"failed", "reconciliation_required"} and recipient.status in {
        CampaignRecipientStatus.PENDING.value,
        CampaignRecipientStatus.SENT.value,
        CampaignRecipientStatus.FAILED.value,
    }:
        recipient.status = CampaignRecipientStatus.FAILED.value
        recipient.error = (error or status)[:500]
        recipient.skip_reason = None
    elif status == "cancelled" and recipient.status == CampaignRecipientStatus.PENDING.value:
        recipient.status = CampaignRecipientStatus.SKIPPED.value
        recipient.error = None
        recipient.skip_reason = (error or "cancelled")[:100]

    if not recompute_campaign_run_aggregates(
        db,
        organization_id=organization_id,
        run_id=run_id,
        commit=False,
    ):
        raise RuntimeError("Campaign aggregate projection target is missing")
    if commit:
        db.commit()
    else:
        db.flush()
    return True
