"""AI Transcription service using OpenAI Whisper API."""

import io
import logging
import os
import tempfile
from uuid import UUID

import boto3
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Attachment,
    CaseInterview,
    InterviewAttachment,
)
from app.services import interview_service
from app.services.ai_settings_service import (
    get_ai_settings,
    get_decrypted_key,
    is_consent_required,
)

logger = logging.getLogger(__name__)

# Audio/video MIME types that can be transcribed
TRANSCRIBABLE_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/wav",
    "audio/webm",
    "audio/ogg",
    "video/mp4",
    "video/webm",
    "video/mpeg",
    "video/quicktime",
}

# Max file size for transcription (25MB - Whisper limit)
MAX_TRANSCRIPTION_SIZE_BYTES = 25 * 1024 * 1024


class TranscriptionError(Exception):
    """Error during transcription process."""

    pass


def is_transcribable(content_type: str) -> bool:
    """Check if the content type can be transcribed."""
    return content_type in TRANSCRIBABLE_MIME_TYPES


def _get_s3_client():
    """Get boto3 S3 client."""
    return boto3.client(
        "s3",
        region_name=getattr(settings, "S3_REGION", "us-east-1"),
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
    )


def _download_file(storage_key: str) -> bytes:
    """Download file from storage backend."""
    backend = getattr(settings, "STORAGE_BACKEND", "local")

    if backend == "s3":
        s3 = _get_s3_client()
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
        response = s3.get_object(Bucket=bucket, Key=storage_key)
        return response["Body"].read()
    else:
        # Local storage
        local_path = getattr(settings, "LOCAL_STORAGE_PATH", None)
        if not local_path:
            local_path = os.path.join(tempfile.gettempdir(), "crm-attachments")
        path = os.path.join(local_path, storage_key)
        with open(path, "rb") as f:
            return f.read()


async def transcribe_audio(
    file_bytes: bytes,
    filename: str,
    api_key: str,
    language: str = "en",
    prompt: str | None = None,
) -> str:
    """
    Transcribe audio/video using OpenAI Whisper API.

    Args:
        file_bytes: The audio/video file content
        filename: Original filename (for format detection)
        api_key: OpenAI API key
        language: ISO 639-1 language code
        prompt: Optional context prompt for better accuracy

    Returns:
        Transcription text
    """
    if len(file_bytes) > MAX_TRANSCRIPTION_SIZE_BYTES:
        raise TranscriptionError(
            f"File too large for transcription. Max size is {MAX_TRANSCRIPTION_SIZE_BYTES / (1024 * 1024):.0f}MB"
        )

    # Build form data for multipart upload
    files = {"file": (filename, io.BytesIO(file_bytes))}
    data = {
        "model": "whisper-1",
        "language": language,
        "response_format": "text",
    }
    if prompt:
        data["prompt"] = prompt

    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min timeout
        try:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                data=data,
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.error(f"Whisper API error: {e.response.status_code} - {e.response.text}")
            raise TranscriptionError(f"Transcription failed: {e.response.text}")
        except httpx.TimeoutException:
            raise TranscriptionError("Transcription timed out. The file may be too long.")
        except Exception as e:
            logger.exception("Unexpected error during transcription")
            raise TranscriptionError(f"Transcription failed: {str(e)}")


def _format_transcript_doc(text: str, filename: str) -> dict:
    """Format transcription text as TipTap JSON."""
    paragraphs = [paragraph.strip() for paragraph in text.strip().split("\n\n") if paragraph.strip()]

    header = [
        {"type": "text", "text": "AI Transcription", "marks": [{"type": "bold"}]},
        {"type": "text", "text": f" \u2014 {filename}"},
    ]

    content = [
        {"type": "paragraph", "content": header},
        {"type": "horizontalRule"},
    ]
    for paragraph in paragraphs:
        content.append(
            {"type": "paragraph", "content": [{"type": "text", "text": paragraph}]}
        )

    return {"type": "doc", "content": content}


def _append_transcript_doc(current_doc: dict | None, new_doc: dict) -> dict:
    """Append transcription content to an existing TipTap document."""
    if not current_doc or current_doc.get("type") != "doc":
        return new_doc
    return {
        "type": "doc",
        "content": [
            *(current_doc.get("content") or []),
            *(new_doc.get("content") or []),
        ],
    }


async def request_transcription(
    db: Session,
    interview_attachment: InterviewAttachment,
    language: str = "en",
    prompt: str | None = None,
    requested_by_user_id: UUID | None = None,
) -> dict:
    """
    Request transcription for an interview attachment.

    Args:
        db: Database session
        interview_attachment: The InterviewAttachment record
        language: ISO 639-1 language code
        prompt: Optional context prompt

    Returns:
        dict with status and result
    """
    # Get related records
    attachment = db.scalar(
        select(Attachment).where(
            Attachment.id == interview_attachment.attachment_id,
            Attachment.organization_id == interview_attachment.organization_id,
        )
    )
    if not attachment:
        raise TranscriptionError("Attachment not found")

    interview = db.scalar(
        select(CaseInterview).where(
            CaseInterview.id == interview_attachment.interview_id,
            CaseInterview.organization_id == interview_attachment.organization_id,
        )
    )
    if not interview:
        raise TranscriptionError("Interview not found")

    # Check if transcribable
    if not is_transcribable(attachment.content_type):
        raise TranscriptionError(
            f"File type '{attachment.content_type}' cannot be transcribed"
        )

    # Check file size
    if attachment.file_size > MAX_TRANSCRIPTION_SIZE_BYTES:
        raise TranscriptionError(
            f"File too large. Max size is {MAX_TRANSCRIPTION_SIZE_BYTES / (1024 * 1024):.0f}MB"
        )

    # Require a clean attachment (if virus scanning is enabled)
    if getattr(attachment, "quarantined", False):
        raise TranscriptionError("Attachment is quarantined pending virus scan")

    # Get AI settings
    ai_settings = get_ai_settings(db, interview.organization_id)
    if not ai_settings or not ai_settings.is_enabled:
        raise TranscriptionError("AI features are not enabled for this organization")
    if is_consent_required(ai_settings):
        raise TranscriptionError("AI consent has not been accepted for this organization")

    # Only OpenAI supports Whisper
    if ai_settings.provider != "openai":
        raise TranscriptionError("Transcription requires OpenAI API key")

    api_key = get_decrypted_key(ai_settings)
    if not api_key:
        raise TranscriptionError("AI API key not configured")

    # Update status to processing
    interview_attachment.transcription_status = "processing"
    db.flush()

    try:
        # Download file
        file_bytes = _download_file(attachment.storage_key)

        # Transcribe
        transcription = await transcribe_audio(
            file_bytes=file_bytes,
            filename=attachment.filename,
            api_key=api_key,
            language=language,
            prompt=prompt,
        )

        # Format as TipTap JSON
        transcription_doc = _format_transcript_doc(transcription, attachment.filename)

        # Append to interview transcript (or set if empty)
        new_doc = _append_transcript_doc(interview.transcript_json, transcription_doc)

        # Update interview with new transcript version
        await interview_service.update_transcript(
            db=db,
            interview=interview,
            new_transcript_json=new_doc,
            user_id=requested_by_user_id or interview.conducted_by_user_id,
            source="ai_transcription",
        )

        # Mark transcription as completed
        interview_attachment.transcription_status = "completed"
        from datetime import datetime, timezone

        interview_attachment.transcription_completed_at = datetime.now(timezone.utc)
        db.flush()

        return {
            "status": "completed",
            "result": transcription,
        }

    except TranscriptionError as e:
        interview_attachment.transcription_status = "failed"
        interview_attachment.transcription_error = str(e)[:500]
        db.flush()
        # Create system alert for transcription failure
        _create_transcription_alert(db, interview.organization_id, str(e), type(e).__name__)
        raise

    except Exception as e:
        logger.exception("Unexpected error during transcription")
        interview_attachment.transcription_status = "failed"
        interview_attachment.transcription_error = f"Unexpected error: {str(e)}"[:500]
        db.flush()
        # Create system alert for transcription failure
        _create_transcription_alert(db, interview.organization_id, str(e), type(e).__name__)
        raise TranscriptionError(f"Transcription failed: {str(e)}")


def get_transcription_status(
    db: Session,
    interview_attachment: InterviewAttachment,
) -> dict:
    """
    Get current transcription status for an attachment.

    Returns:
        dict with status, progress, result, error
    """
    return {
        "status": interview_attachment.transcription_status or "not_started",
        "progress": None,  # Whisper doesn't provide progress
        "result": None,  # Result is written to interview transcript
        "error": interview_attachment.transcription_error,
    }


def _create_transcription_alert(
    db: Session, org_id: UUID, error_msg: str, error_class: str
) -> None:
    """Create system alert for transcription failure."""
    try:
        from app.services import alert_service
        from app.db.enums import AlertType, AlertSeverity

        alert_service.create_or_update_alert(
            db=db,
            org_id=org_id,
            alert_type=AlertType.TRANSCRIPTION_FAILED,
            severity=AlertSeverity.ERROR,
            title="Interview transcription failed",
            message=error_msg[:500],
            integration_key="openai_whisper",
            error_class=error_class,
        )
    except Exception as alert_err:
        logger.warning(f"Failed to create transcription alert: {alert_err}")
