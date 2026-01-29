"""Interview-related job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_interview_transcription(db, job) -> None:
    """
    Process interview transcription job.

    Payload:
      - interview_attachment_id
      - language (optional)
      - prompt (optional)
      - requested_by_user_id (optional)
    """
    from sqlalchemy.orm import joinedload

    from app.db.enums import NotificationType
    from app.db.models import CaseInterview, InterviewAttachment
    from app.services import notification_service, transcription_service

    payload = job.payload or {}
    link_id = payload.get("interview_attachment_id")
    if not link_id:
        raise Exception("Missing interview_attachment_id in job payload")

    link = (
        db.query(InterviewAttachment)
        .options(
            joinedload(InterviewAttachment.attachment),
            joinedload(InterviewAttachment.interview).joinedload(CaseInterview.case),
        )
        .filter(
            InterviewAttachment.id == UUID(link_id),
            InterviewAttachment.organization_id == job.organization_id,
        )
        .first()
    )
    if not link:
        raise Exception(f"InterviewAttachment {link_id} not found")

    language = payload.get("language") or "en"
    prompt = payload.get("prompt")
    requested_by = payload.get("requested_by_user_id")
    requested_by_user_id = UUID(requested_by) if requested_by else None

    await transcription_service.request_transcription(
        db=db,
        interview_attachment=link,
        language=language,
        prompt=prompt,
        requested_by_user_id=requested_by_user_id,
    )

    if requested_by_user_id and link.interview:
        interview_date = link.interview.conducted_at.strftime("%b %d, %Y")
        notification_service.create_notification(
            db=db,
            org_id=job.organization_id,
            user_id=requested_by_user_id,
            type=NotificationType.INTERVIEW_TRANSCRIPTION_COMPLETED,
            title="Interview transcription ready",
            body=f"Transcription completed for interview on {interview_date}.",
            entity_type="case",
            entity_id=link.interview.surrogate_id,
            dedupe_key=f"interview_transcription_completed:{job.id}",
            dedupe_window_hours=None,
        )
