"""Zoom webhook handler."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Appointment, ZoomWebhookEvent

logger = logging.getLogger(__name__)
MAX_PAYLOAD_BYTES = 1 * 1024 * 1024  # 1 MB


def _verify_zoom_webhook_signature(
    body: bytes,
    signature: str,
    timestamp: str,
    secret: str,
) -> bool:
    """
    Verify Zoom webhook signature.

    Zoom sends: v0:timestamp:body_string
    Then HMAC-SHA256 with webhook secret, compare to signature.
    """
    message = b"v0:" + timestamp.encode("utf-8") + b":" + body
    expected = hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    expected_signature = f"v0={expected}"
    return hmac.compare_digest(expected_signature, signature)


async def _read_body_safe(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_PAYLOAD_BYTES:
                raise HTTPException(413, "Payload too large")
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_PAYLOAD_BYTES:
            raise HTTPException(413, "Payload too large")
        chunks.append(chunk)
    return b"".join(chunks)


class ZoomWebhookHandler:
    async def handle(self, request: Request, db: Session, **kwargs):
        """
        Receive Zoom webhook events.

        Handles:
        - endpoint.url_validation: Zoom verification challenge
        - meeting.started: Log meeting start timestamp
        - meeting.ended: Log meeting end timestamp

        Security:
        - Validates webhook signature using ZOOM_WEBHOOK_SECRET
        - Deduplicates events via ZoomWebhookEvent table
        """
        body = await _read_body_safe(request)

        # Handle URL validation challenge from Zoom
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON")

        # URL validation event (during webhook setup)
        if data.get("event") == "endpoint.url_validation":
            plain_token = data.get("payload", {}).get("plainToken", "")
            if not plain_token:
                raise HTTPException(400, "Missing plainToken")

            # Encrypt the token with our webhook secret
            encrypted_token = hmac.new(
                settings.ZOOM_WEBHOOK_SECRET.encode("utf-8"),
                plain_token.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            return JSONResponse(
                {
                    "plainToken": plain_token,
                    "encryptedToken": encrypted_token,
                }
            )

        # Verify signature for other events
        signature = request.headers.get("x-zm-signature", "")
        timestamp = request.headers.get("x-zm-request-timestamp", "")

        if not signature or not timestamp:
            logger.warning("Zoom webhook missing signature or timestamp")
            raise HTTPException(403, "Missing signature")

        if not settings.ZOOM_WEBHOOK_SECRET:
            logger.error("ZOOM_WEBHOOK_SECRET not configured")
            raise HTTPException(500, "Webhook not configured")

        if not _verify_zoom_webhook_signature(
            body, signature, timestamp, settings.ZOOM_WEBHOOK_SECRET
        ):
            logger.warning("Zoom webhook invalid signature")
            raise HTTPException(403, "Invalid signature")

        # Extract event info
        event_type = data.get("event", "")
        payload = data.get("payload", {})
        event_id = data.get("event_ts", str(datetime.now(timezone.utc).timestamp()))

        # Meeting object from payload
        meeting_obj = payload.get("object", {})
        zoom_meeting_id = str(meeting_obj.get("id", ""))

        if not zoom_meeting_id:
            logger.warning("Zoom webhook missing meeting ID: %s", event_type)
            return {"status": "ok", "message": "No meeting ID"}

        # Dedupe: check if we've already processed this event
        provider_event_id = f"{event_type}:{zoom_meeting_id}:{event_id}"

        try:
            webhook_event = ZoomWebhookEvent(
                provider_event_id=provider_event_id,
                event_type=event_type,
                zoom_meeting_id=zoom_meeting_id,
                payload=data,
            )
            db.add(webhook_event)
            db.flush()
        except IntegrityError:
            db.rollback()
            logger.info("Zoom webhook duplicate event: %s", provider_event_id)
            return {"status": "ok", "message": "Duplicate event"}

        # Find appointment by zoom_meeting_id
        appointment = (
            db.query(Appointment).filter(Appointment.zoom_meeting_id == zoom_meeting_id).first()
        )

        if not appointment:
            logger.info("Zoom webhook: no appointment for meeting %s", zoom_meeting_id)
            db.commit()  # Commit the webhook event for audit
            return {"status": "ok", "message": "No matching appointment"}

        # Handle event types
        event_timestamp = datetime.now(timezone.utc)
        if event_type == "meeting.started":
            appointment.meeting_started_at = event_timestamp
            logger.info("Zoom meeting started: %s, appointment %s", zoom_meeting_id, appointment.id)

        elif event_type == "meeting.ended":
            appointment.meeting_ended_at = event_timestamp
            logger.info("Zoom meeting ended: %s, appointment %s", zoom_meeting_id, appointment.id)

        db.commit()

        return {"status": "ok", "event": event_type, "meeting_id": zoom_meeting_id}
