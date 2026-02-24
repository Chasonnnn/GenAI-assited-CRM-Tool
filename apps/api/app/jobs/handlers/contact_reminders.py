"""Contact reminder job handlers."""

from __future__ import annotations

import logging

from app.services import contact_reminder_service

logger = logging.getLogger(__name__)


async def process_contact_reminder_check(db, job) -> None:
    """Process contact reminder checks for all organizations."""
    logger.info("Processing contact reminder check job %s", job.id)
    stats = contact_reminder_service.process_contact_reminder_jobs(db)
    logger.info(
        "Contact reminder check complete (orgs=%s checked=%s notifications=%s errors=%s)",
        stats.get("orgs_processed", 0),
        stats.get("total_surrogates_checked", 0),
        stats.get("total_notifications_created", 0),
        len(stats.get("errors", [])),
    )
