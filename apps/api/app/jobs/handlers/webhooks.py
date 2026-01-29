"""Webhook retry job handlers."""

from __future__ import annotations

import logging

from app.jobs.utils import safe_url

logger = logging.getLogger(__name__)


async def process_webhook_retry(db, job) -> None:
    """Retry failed webhook delivery."""
    logger.info("Processing webhook retry job %s", job.id)
    payload = job.payload or {}

    # Extract webhook details
    webhook_url = payload.get("url")
    webhook_data = payload.get("data")
    webhook_headers = payload.get("headers", {})

    if webhook_url and webhook_data:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook_url, json=webhook_data, headers=webhook_headers
                )
                response.raise_for_status()
                logger.info("Webhook retry successful: %s", safe_url(webhook_url))
        except Exception as e:
            logger.error(
                "Webhook retry failed: %s (%s)",
                safe_url(webhook_url),
                type(e).__name__,
            )
            raise
    else:
        logger.warning("Invalid webhook retry payload: missing url or data")
