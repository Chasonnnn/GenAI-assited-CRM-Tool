"""Zapier outbound job handlers."""

from __future__ import annotations

import logging

import httpx

from app.jobs.utils import safe_url

logger = logging.getLogger(__name__)


async def process_zapier_stage_event(db, job) -> None:
    """Send a Zapier stage event via webhook."""
    logger.info("Processing Zapier stage event job %s", job.id)
    payload = job.payload or {}

    webhook_url = payload.get("url")
    webhook_data = payload.get("data")
    webhook_headers = payload.get("headers", {})

    if not webhook_url or not webhook_data:
        logger.warning("Invalid Zapier stage event payload: missing url or data")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(webhook_url, json=webhook_data, headers=webhook_headers)
        response.raise_for_status()
        logger.info("Zapier stage event delivered: %s", safe_url(webhook_url))
