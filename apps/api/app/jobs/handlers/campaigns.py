"""Campaign job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_campaign_send(db, job) -> None:
    """
    Process a CAMPAIGN_SEND job - execute bulk email campaign.

    Payload:
        - campaign_id: UUID of the campaign
        - run_id: UUID of the campaign run
        - user_id: UUID of user who triggered the send
    """
    from app.services import campaign_service

    payload = job.payload or {}
    campaign_id = payload.get("campaign_id")
    run_id = payload.get("run_id")
    retry_failed_only = bool(payload.get("retry_failed_only"))

    if not campaign_id or not run_id:
        raise Exception("Missing campaign_id or run_id in campaign send job")

    logger.info("Starting campaign send: campaign=%s, run=%s", campaign_id, run_id)

    try:
        # Check if campaign was cancelled before executing
        from app.db.models import Campaign
        from app.db.enums import CampaignStatus

        campaign = db.query(Campaign).filter(Campaign.id == UUID(campaign_id)).first()
        if not campaign:
            raise Exception(f"Campaign {campaign_id} not found")

        if campaign.status == CampaignStatus.CANCELLED.value:
            logger.info("Campaign %s was cancelled, skipping execution", campaign_id)
            return

        # Execute the campaign send (full run or retry failed only)
        if retry_failed_only:
            result = campaign_service.retry_failed_campaign_run(
                db=db,
                org_id=job.organization_id,
                campaign_id=UUID(campaign_id),
                run_id=UUID(run_id),
            )
        else:
            result = campaign_service.execute_campaign_run(
                db=db,
                org_id=job.organization_id,
                campaign_id=UUID(campaign_id),
                run_id=UUID(run_id),
            )

        if retry_failed_only:
            logger.info(
                "Campaign retry completed: campaign=%s run=%s retried=%s skipped=%s",
                campaign_id,
                run_id,
                result.get("retried_count", 0),
                result.get("skipped_count", 0),
            )
        else:
            logger.info(
                "Campaign send completed: campaign=%s, sent=%s, failed=%s, skipped=%s",
                campaign_id,
                result.get("sent_count", 0),
                result.get("failed_count", 0),
                result.get("skipped_count", 0),
            )
    except Exception as e:
        logger.error(
            "Campaign send failed: campaign=%s error=%s",
            campaign_id,
            type(e).__name__,
        )
        raise
