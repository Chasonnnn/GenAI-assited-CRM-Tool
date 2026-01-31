"""AI Transcription service using Gemini/Vertex AI."""

import logging
import os
import tempfile
from uuid import UUID

from botocore.client import BaseClient
from google.genai import types
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Attachment,
    SurrogateInterview,
    InterviewAttachment,
)
from app.services import interview_service, storage_client
from app.services.ai_settings_service import (
    get_ai_settings,
    get_decrypted_key,
    get_effective_model,
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

# Max file size for inline audio (20MB Gemini/Vertex inline limit)
MAX_TRANSCRIPTION_SIZE_BYTES = 20 * 1024 * 1024


class TranscriptionError(Exception):
    """Error during transcription process."""

    pass


def is_transcribable(content_type: str) -> bool:
    """Check if the content type can be transcribed."""
    return content_type in TRANSCRIBABLE_MIME_TYPES


def _get_s3_client() -> BaseClient:
    """Get boto3 S3 client."""
    return storage_client.get_s3_client()


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


def _build_transcription_instruction(language: str, prompt: str | None) -> str:
    instruction = (
        "Transcribe the audio as plain text."
        if not language
        else f"Transcribe the audio in {language} as plain text."
    )
    if prompt:
        instruction = f"{instruction} Use this context: {prompt}"
    return instruction


def _build_transcription_parts(
    file_bytes: bytes,
    content_type: str,
    language: str,
    prompt: str | None,
) -> list[types.Part]:
    instruction = _build_transcription_instruction(language, prompt)
    return [
        types.Part.from_text(instruction),
        types.Part.from_bytes(data=file_bytes, mime_type=content_type),
    ]


async def _transcribe_with_provider(
    provider_instance: "GoogleGenAIProvider",
    file_bytes: bytes,
    content_type: str,
    language: str,
    prompt: str | None,
    model: str,
) -> str:
    parts = _build_transcription_parts(file_bytes, content_type, language, prompt)
    try:
        return await provider_instance.generate_text_with_parts(
            parts=parts,
            model=model,
            temperature=0,
            max_tokens=4096,
        )
    except Exception as exc:
        logger.exception("Transcription provider error")
        message = str(exc).lower()
        if "timeout" in message:
            raise TranscriptionError("Transcription timed out. The file may be too long.") from exc
        raise TranscriptionError("Transcription failed: provider error") from exc


async def transcribe_audio(
    file_bytes: bytes,
    content_type: str,
    *,
    provider: str,
    model: str,
    api_key: str | None = None,
    vertex_project_id: str | None = None,
    vertex_location: str | None = None,
    vertex_audience: str | None = None,
    vertex_service_account_email: str | None = None,
    organization_id: UUID | None = None,
    user_id: UUID | None = None,
    language: str = "en",
    prompt: str | None = None,
) -> str:
    """
    Transcribe audio/video using Gemini or Vertex AI.

    Args:
        file_bytes: The audio/video file content
        content_type: MIME type
        provider: gemini | vertex_api_key | vertex_wif
        model: Gemini model name
        api_key: Gemini/Vertex API key (if applicable)
        vertex_project_id: Vertex project (if applicable)
        vertex_location: Vertex location (if applicable)
        vertex_audience: WIF audience (if applicable)
        vertex_service_account_email: WIF service account email (if applicable)
        language: ISO 639-1 language code
        prompt: Optional context prompt for better accuracy

    Returns:
        Transcription text
    """
    if len(file_bytes) > MAX_TRANSCRIPTION_SIZE_BYTES:
        raise TranscriptionError(
            f"File too large for transcription. Max size is {MAX_TRANSCRIPTION_SIZE_BYTES / (1024 * 1024):.0f}MB"
        )

    if provider == "gemini":
        if not api_key:
            raise TranscriptionError("AI API key not configured")
        from app.services.ai_provider import GeminiProvider

        provider_instance = GeminiProvider(api_key, default_model=model)
        return await _transcribe_with_provider(
            provider_instance,
            file_bytes,
            content_type,
            language,
            prompt,
            model,
        )

    if provider == "vertex_api_key":
        if not api_key:
            raise TranscriptionError("AI API key not configured")
        from app.services.ai_provider import VertexAPIKeyConfig, VertexAPIKeyProvider

        config = VertexAPIKeyConfig(
            api_key=api_key,
            project_id=vertex_project_id,
            location=vertex_location,
        )
        provider_instance = VertexAPIKeyProvider(config, default_model=model)
        return await _transcribe_with_provider(
            provider_instance,
            file_bytes,
            content_type,
            language,
            prompt,
            model,
        )

    if provider == "vertex_wif":
        if not (
            vertex_project_id
            and vertex_location
            and vertex_audience
            and vertex_service_account_email
        ):
            raise TranscriptionError("Vertex AI configuration is incomplete")
        if not settings.WIF_OIDC_PRIVATE_KEY:
            raise TranscriptionError("Vertex WIF is not configured")
        if not organization_id:
            raise TranscriptionError("Organization is required for Vertex WIF")
        from app.services.ai_provider import VertexWIFConfig, VertexWIFProvider

        config = VertexWIFConfig(
            project_id=vertex_project_id,
            location=vertex_location,
            audience=vertex_audience,
            service_account_email=vertex_service_account_email,
            organization_id=organization_id,
            user_id=user_id,
        )
        provider_instance = VertexWIFProvider(config, default_model=model)
        return await _transcribe_with_provider(
            provider_instance,
            file_bytes,
            content_type,
            language,
            prompt,
            model,
        )

    raise TranscriptionError("Transcription provider not supported")


def _format_transcript_doc(text: str, filename: str) -> dict:
    """Format transcription text as TipTap JSON."""
    paragraphs = [
        paragraph.strip() for paragraph in text.strip().split("\n\n") if paragraph.strip()
    ]

    header = [
        {"type": "text", "text": "AI Transcription", "marks": [{"type": "bold"}]},
        {"type": "text", "text": f" \u2014 {filename}"},
    ]

    content = [
        {"type": "paragraph", "content": header},
        {"type": "horizontalRule"},
    ]
    for paragraph in paragraphs:
        content.append({"type": "paragraph", "content": [{"type": "text", "text": paragraph}]})

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
        select(SurrogateInterview).where(
            SurrogateInterview.id == interview_attachment.interview_id,
            SurrogateInterview.organization_id == interview_attachment.organization_id,
        )
    )
    if not interview:
        raise TranscriptionError("Interview not found")

    # Check if transcribable
    if not is_transcribable(attachment.content_type):
        raise TranscriptionError(f"File type '{attachment.content_type}' cannot be transcribed")

    # Check file size
    if attachment.file_size > MAX_TRANSCRIPTION_SIZE_BYTES:
        raise TranscriptionError(
            f"File too large. Max size is {MAX_TRANSCRIPTION_SIZE_BYTES / (1024 * 1024):.0f}MB"
        )

    # Require a clean attachment (if virus scanning is enabled)
    if attachment.scan_status in ("infected", "error"):
        raise TranscriptionError("Attachment failed virus scan")

    # Get AI settings
    ai_settings = get_ai_settings(db, interview.organization_id)
    if not ai_settings or not ai_settings.is_enabled:
        raise TranscriptionError("AI features are not enabled for this organization")
    if is_consent_required(ai_settings):
        raise TranscriptionError("AI consent has not been accepted for this organization")

    provider = ai_settings.provider
    if provider not in {"gemini", "vertex_api_key", "vertex_wif"}:
        raise TranscriptionError("Transcription provider not supported")

    model = get_effective_model(ai_settings) or "gemini-3-flash-preview"
    if model not in {"gemini-3-flash-preview", "gemini-3-pro-preview"}:
        raise TranscriptionError("Unsupported transcription model configured")

    api_key = get_decrypted_key(ai_settings) if provider in {"gemini", "vertex_api_key"} else None

    # Update status to processing
    interview_attachment.transcription_status = "processing"
    db.flush()

    try:
        # Download file
        file_bytes = _download_file(attachment.storage_key)

        # Transcribe
        transcription = await transcribe_audio(
            file_bytes=file_bytes,
            content_type=attachment.content_type,
            provider=provider,
            model=model,
            api_key=api_key,
            vertex_project_id=ai_settings.vertex_project_id,
            vertex_location=ai_settings.vertex_location,
            vertex_audience=ai_settings.vertex_audience,
            vertex_service_account_email=ai_settings.vertex_service_account_email,
            organization_id=interview.organization_id,
            user_id=requested_by_user_id,
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
