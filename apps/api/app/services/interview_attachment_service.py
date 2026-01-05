"""Interview attachment service - link existing attachments to interviews."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Attachment, CaseInterview, InterviewAttachment
from app.services import attachment_service


# Audio/video MIME types that support transcription
AUDIO_VIDEO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/ogg",
    "audio/webm",
    "audio/m4a",
    "audio/aac",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
}

# Allow standard attachments plus audio/video for interviews
INTERVIEW_ALLOWED_EXTENSIONS = attachment_service.ALLOWED_EXTENSIONS | {
    "aac",
    "avi",
    "m4a",
    "mkv",
    "mov",
    "mp3",
    "mp4",
    "mpeg",
    "ogg",
    "wav",
    "webm",
}

INTERVIEW_ALLOWED_MIME_TYPES = attachment_service.ALLOWED_MIME_TYPES | AUDIO_VIDEO_MIME_TYPES


# =============================================================================
# Link Operations
# =============================================================================


def link_attachment(
    db: Session,
    org_id: UUID,
    interview: CaseInterview,
    attachment_id: UUID,
) -> InterviewAttachment:
    """
    Link an existing attachment to an interview.

    The attachment must belong to the same organization.
    """
    # Verify attachment exists and belongs to org
    attachment = db.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.organization_id == org_id,
            Attachment.deleted_at.is_(None),
        )
    )
    if not attachment:
        raise ValueError("Attachment not found")

    # Check if already linked
    existing = db.scalar(
        select(InterviewAttachment).where(
            InterviewAttachment.interview_id == interview.id,
            InterviewAttachment.attachment_id == attachment_id,
        )
    )
    if existing:
        raise ValueError("Attachment already linked to this interview")

    # Create link
    link = InterviewAttachment(
        interview_id=interview.id,
        attachment_id=attachment_id,
        organization_id=org_id,
        transcription_status=None,
        transcription_job_id=None,
        transcription_error=None,
        transcription_completed_at=None,
    )
    db.add(link)
    db.flush()
    return link


def unlink_attachment(
    db: Session,
    org_id: UUID,
    interview_id: UUID,
    attachment_id: UUID,
) -> bool:
    """
    Unlink an attachment from an interview.

    Returns True if unlinked, False if not found.
    """
    link = db.scalar(
        select(InterviewAttachment).where(
            InterviewAttachment.interview_id == interview_id,
            InterviewAttachment.attachment_id == attachment_id,
            InterviewAttachment.organization_id == org_id,
        )
    )
    if not link:
        return False

    db.delete(link)
    db.flush()
    return True


def get_interview_attachment(
    db: Session,
    org_id: UUID,
    interview_id: UUID,
    attachment_id: UUID,
) -> InterviewAttachment | None:
    """Get interview-attachment link."""
    return db.scalar(
        select(InterviewAttachment)
        .options(joinedload(InterviewAttachment.attachment))
        .where(
            InterviewAttachment.interview_id == interview_id,
            InterviewAttachment.attachment_id == attachment_id,
            InterviewAttachment.organization_id == org_id,
        )
    )


def list_interview_attachments(
    db: Session,
    org_id: UUID,
    interview_id: UUID,
) -> list[InterviewAttachment]:
    """List all attachments linked to an interview."""
    return list(
        db.scalars(
            select(InterviewAttachment)
            .options(
                joinedload(InterviewAttachment.attachment).joinedload(
                    Attachment.uploaded_by
                )
            )
            .where(
                InterviewAttachment.interview_id == interview_id,
                InterviewAttachment.organization_id == org_id,
            )
            .order_by(InterviewAttachment.created_at.desc())
        ).all()
    )


# =============================================================================
# Transcription Status
# =============================================================================


def update_transcription_status(
    db: Session,
    link: InterviewAttachment,
    status: str,
    job_id: str | None = None,
    error: str | None = None,
) -> InterviewAttachment:
    """
    Update transcription status for an attachment.

    Status: 'pending', 'processing', 'completed', 'failed'
    """
    link.transcription_status = status
    link.transcription_job_id = job_id
    link.transcription_error = error[:500] if error else None

    if status == "completed":
        link.transcription_completed_at = datetime.now(timezone.utc)

    db.flush()
    return link


def is_audio_video(content_type: str) -> bool:
    """Check if content type is audio or video."""
    return content_type in AUDIO_VIDEO_MIME_TYPES


# =============================================================================
# Response Builders
# =============================================================================


def to_attachment_read(link: InterviewAttachment) -> dict:
    """Convert interview attachment to response dict."""
    attachment = link.attachment

    uploaded_by_name = "Unknown"
    if attachment.uploaded_by:
        uploaded_by_name = (
            attachment.uploaded_by.display_name or attachment.uploaded_by.email
        )

    return {
        "id": link.id,
        "attachment_id": attachment.id,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "file_size": attachment.file_size,
        "is_audio_video": is_audio_video(attachment.content_type),
        "transcription_status": link.transcription_status,
        "transcription_error": link.transcription_error,
        "uploaded_by_name": uploaded_by_name,
        "created_at": link.created_at,
    }
