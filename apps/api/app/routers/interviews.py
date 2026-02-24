"""Interviews router - API endpoints for surrogate interviews.

Endpoints:
- Interview CRUD
- Version management (list, get, diff, restore)
- Notes CRUD with anchoring
- Attachment linking
- AI features (transcription, summary)
- Export (PDF, JSON)
"""

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.surrogate_access import can_modify_surrogate, check_surrogate_access
from app.core.deps import (
    get_current_session,
    get_db,
    require_ai_enabled,
    require_csrf_header,
    require_permission,
)
from app.core.permissions import PermissionKey as P
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.utils.file_upload import content_length_exceeds_limit, get_upload_file_size
from app.utils.sse import format_sse, sse_preamble, STREAM_HEADERS
from app.schemas.interview import (
    InterviewAttachmentRead,
    InterviewCreate,
    InterviewListItem,
    InterviewNoteCreate,
    InterviewNoteRead,
    InterviewNoteUpdate,
    InterviewRead,
    InterviewUpdate,
    InterviewVersionDiff,
    InterviewVersionListItem,
    InterviewVersionRead,
    InterviewSummaryResponse,
    AllInterviewsSummaryResponse,
    TranscriptionRequest,
    TranscriptionStatusRead,
)
from app.services import (
    attachment_service,
    ai_interview_service,
    surrogate_service,
    interview_attachment_service,
    interview_note_service,
    interview_service,
    org_service,
    pdf_export_service,
)

router = APIRouter(tags=["interviews"])


# =============================================================================
# Permission Helpers
# =============================================================================


def _check_interview_access(
    db: Session,
    org_id: UUID,
    interview_id: UUID,
    session: UserSession,
):
    """Get interview and verify surrogate access."""
    interview = interview_service.get_interview(db, org_id, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Check surrogate access
    surrogate = interview.surrogate
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    return interview, surrogate


def _check_can_modify_interview(surrogate, session: UserSession, db: Session):
    """Check if user can create/edit interviews on this surrogate."""
    if not can_modify_surrogate(
        surrogate,
        session.user_id,
        session.role,
        db=db,
        org_id=session.org_id,
    ):
        raise HTTPException(
            status_code=403, detail="You don't have permission to modify this surrogate"
        )


def _check_admin_only(session: UserSession):
    """Check if user has admin+ role."""
    role_str = session.role.value if hasattr(session.role, "value") else session.role
    if role_str not in [Role.ADMIN.value, Role.DEVELOPER.value]:
        raise HTTPException(status_code=403, detail="Admin access required")


# =============================================================================
# Interview CRUD
# =============================================================================


@router.get("/surrogates/{surrogate_id}/interviews", response_model=list[InterviewListItem])
def list_interviews(
    surrogate_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List all interviews for a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    return interview_service.list_interviews_with_counts(db, session.org_id, surrogate_id)


@router.post(
    "/surrogates/{surrogate_id}/interviews",
    response_model=InterviewRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_interview(
    surrogate_id: UUID,
    data: InterviewCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a new interview for a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)
    _check_can_modify_interview(surrogate, session, db)

    try:
        interview = interview_service.create_interview(
            db=db,
            org_id=session.org_id,
            surrogate_id=surrogate_id,
            user_id=session.user_id,
            data=data,
        )
        db.commit()
        return interview_service.to_interview_read(db, interview)
    except attachment_service.AttachmentStorageError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/interviews/{interview_id}", response_model=InterviewRead)
def get_interview(
    interview_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get interview details."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)
    return interview_service.to_interview_read(db, interview)


@router.patch(
    "/interviews/{interview_id}",
    response_model=InterviewRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_interview(
    interview_id: UUID,
    data: InterviewUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update an interview (with auto-versioning for transcript changes)."""
    interview, case = _check_interview_access(db, session.org_id, interview_id, session)
    _check_can_modify_interview(case, session, db)

    try:
        interview = interview_service.update_interview(
            db=db,
            org_id=session.org_id,
            interview=interview,
            user_id=session.user_id,
            data=data,
        )
        db.commit()
        return interview_service.to_interview_read(db, interview)
    except ValueError as e:
        if "conflict" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/interviews/{interview_id}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_interview(
    interview_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Delete an interview (admin+ only)."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)
    _check_admin_only(session)

    interview_service.delete_interview(db, interview)
    db.commit()
    return None


# =============================================================================
# Version Management
# =============================================================================


@router.get(
    "/interviews/{interview_id}/versions",
    response_model=list[InterviewVersionListItem],
)
def list_versions(
    interview_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List all versions of an interview transcript."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    versions = interview_service.list_versions(db, session.org_id, interview_id)
    return [interview_service.to_version_list_item(v) for v in versions]


@router.get(
    "/interviews/{interview_id}/versions/{version}",
    response_model=InterviewVersionRead,
)
def get_version(
    interview_id: UUID,
    version: int,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get specific version content."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    version_obj = interview_service.get_version(db, session.org_id, interview_id, version)
    if not version_obj:
        raise HTTPException(status_code=404, detail="Version not found")

    return interview_service.to_version_read(version_obj)


@router.get(
    "/interviews/{interview_id}/versions/diff",
    response_model=InterviewVersionDiff,
)
def get_version_diff(
    interview_id: UUID,
    v1: int = Query(..., ge=1),
    v2: int = Query(..., ge=1),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get diff between two versions."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    if v1 == v2:
        raise HTTPException(status_code=400, detail="Versions must be different")

    try:
        diff = interview_service.get_version_diff(db, session.org_id, interview_id, v1, v2)
        return diff
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/interviews/{interview_id}/versions/{version}/restore",
    response_model=InterviewRead,
    dependencies=[Depends(require_csrf_header)],
)
def restore_version(
    interview_id: UUID,
    version: int,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Restore interview transcript to a previous version."""
    interview, case = _check_interview_access(db, session.org_id, interview_id, session)
    _check_can_modify_interview(case, session)

    try:
        interview = interview_service.restore_version(
            db=db,
            org_id=session.org_id,
            interview=interview,
            target_version=version,
            user_id=session.user_id,
        )
        db.commit()
        return interview_service.to_interview_read(db, interview)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# Notes
# =============================================================================


@router.get("/interviews/{interview_id}/notes", response_model=list[InterviewNoteRead])
def list_notes(
    interview_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List all notes for an interview."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    notes = interview_note_service.list_notes(db, session.org_id, interview_id)
    return [interview_note_service.to_note_read(n, session.user_id) for n in notes]


@router.post(
    "/interviews/{interview_id}/notes",
    response_model=InterviewNoteRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_note(
    interview_id: UUID,
    data: InterviewNoteCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a note on an interview (with optional anchor)."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    try:
        note = interview_note_service.create_note(
            db=db,
            org_id=session.org_id,
            interview=interview,
            user_id=session.user_id,
            data=data,
        )
        db.commit()
        return interview_note_service.to_note_read(note, session.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/interviews/{interview_id}/notes/{note_id}",
    response_model=InterviewNoteRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_note(
    interview_id: UUID,
    note_id: UUID,
    data: InterviewNoteUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update a note."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    note = interview_note_service.get_note(db, session.org_id, note_id)
    if not note or note.interview_id != interview_id:
        raise HTTPException(status_code=404, detail="Note not found")

    note = interview_note_service.update_note(db, note, data)
    db.commit()
    return interview_note_service.to_note_read(note, session.user_id)


@router.delete(
    "/interviews/{interview_id}/notes/{note_id}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_note(
    interview_id: UUID,
    note_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Delete a note."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    note = interview_note_service.get_note(db, session.org_id, note_id)
    if not note or note.interview_id != interview_id:
        raise HTTPException(status_code=404, detail="Note not found")

    interview_note_service.delete_note(db, note)
    db.commit()
    return None


@router.post(
    "/interviews/{interview_id}/notes/{note_id}/resolve",
    response_model=InterviewNoteRead,
    dependencies=[Depends(require_csrf_header)],
)
def resolve_note(
    interview_id: UUID,
    note_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Mark a note as resolved."""
    _check_interview_access(db, session.org_id, interview_id, session)

    note = interview_note_service.get_note(db, session.org_id, note_id)
    if not note or note.interview_id != interview_id:
        raise HTTPException(status_code=404, detail="Note not found")

    note = interview_note_service.resolve_note(db, note, session.user_id)
    db.commit()
    return interview_note_service.to_note_read(note, session.user_id)


@router.post(
    "/interviews/{interview_id}/notes/{note_id}/unresolve",
    response_model=InterviewNoteRead,
    dependencies=[Depends(require_csrf_header)],
)
def unresolve_note(
    interview_id: UUID,
    note_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Re-open a resolved note."""
    _check_interview_access(db, session.org_id, interview_id, session)

    note = interview_note_service.get_note(db, session.org_id, note_id)
    if not note or note.interview_id != interview_id:
        raise HTTPException(status_code=404, detail="Note not found")

    note = interview_note_service.unresolve_note(db, note)
    db.commit()
    return interview_note_service.to_note_read(note, session.user_id)


# =============================================================================
# Attachments
# =============================================================================


@router.get(
    "/interviews/{interview_id}/attachments",
    response_model=list[InterviewAttachmentRead],
)
def list_attachments(
    interview_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List all attachments linked to an interview."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    links = interview_attachment_service.list_interview_attachments(
        db, session.org_id, interview_id
    )
    return [interview_attachment_service.to_attachment_read(link) for link in links]


@router.post(
    "/interviews/{interview_id}/attachments",
    response_model=InterviewAttachmentRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_attachment(
    interview_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Upload a new attachment and link it to the interview."""
    interview, case = _check_interview_access(db, session.org_id, interview_id, session)
    _check_can_modify_interview(case, session)

    if content_length_exceeds_limit(
        request.headers.get("content-length"),
        max_size_bytes=attachment_service.MAX_FILE_SIZE_BYTES,
    ):
        max_mb = attachment_service.MAX_FILE_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"File size exceeds {max_mb:.0f} MB limit")

    file_size = await get_upload_file_size(file)
    if file_size > attachment_service.MAX_FILE_SIZE_BYTES:
        max_mb = attachment_service.MAX_FILE_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"File size exceeds {max_mb:.0f} MB limit")
    file.file.seek(0)

    try:
        # Upload attachment
        attachment = attachment_service.upload_attachment(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            filename=file.filename or "unknown",
            content_type=file.content_type or "application/octet-stream",
            file=file.file,
            file_size=file_size,
            surrogate_id=case.id,
            allowed_extensions=interview_attachment_service.INTERVIEW_ALLOWED_EXTENSIONS,
            allowed_mime_types=interview_attachment_service.INTERVIEW_ALLOWED_MIME_TYPES,
        )

        # Link to interview
        link = interview_attachment_service.link_attachment(
            db=db,
            org_id=session.org_id,
            interview=interview,
            attachment_id=attachment.id,
        )
        db.commit()

        # Refresh to get attachment relationship
        db.refresh(link)
        return interview_attachment_service.to_attachment_read(link)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/interviews/{interview_id}/attachments/{attachment_id}/link",
    response_model=InterviewAttachmentRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def link_existing_attachment(
    interview_id: UUID,
    attachment_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Link an existing attachment to the interview."""
    interview, case = _check_interview_access(db, session.org_id, interview_id, session)
    _check_can_modify_interview(case, session)

    try:
        link = interview_attachment_service.link_attachment(
            db=db,
            org_id=session.org_id,
            interview=interview,
            attachment_id=attachment_id,
        )
        db.commit()
        db.refresh(link)
        return interview_attachment_service.to_attachment_read(link)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/interviews/{interview_id}/attachments/{attachment_id}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def unlink_attachment(
    interview_id: UUID,
    attachment_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Unlink an attachment from the interview (case_manager+ only)."""
    interview, case = _check_interview_access(db, session.org_id, interview_id, session)

    role_str = session.role.value if hasattr(session.role, "value") else session.role
    if role_str not in [
        Role.CASE_MANAGER.value,
        Role.ADMIN.value,
        Role.DEVELOPER.value,
    ]:
        raise HTTPException(status_code=403, detail="Case manager or higher required")

    success = interview_attachment_service.unlink_attachment(
        db, session.org_id, interview_id, attachment_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Attachment link not found")

    db.commit()
    return None


# =============================================================================
# Transcription (Placeholder - full implementation in transcription_service)
# =============================================================================


@router.post(
    "/interviews/{interview_id}/attachments/{attachment_id}/transcribe",
    response_model=TranscriptionStatusRead,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
async def request_transcription(
    interview_id: UUID,
    attachment_id: UUID,
    data: TranscriptionRequest | None = None,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Request AI transcription for an audio/video attachment (sync)."""
    from app.services import transcription_service

    interview, case = _check_interview_access(db, session.org_id, interview_id, session)
    _check_can_modify_interview(case, session)

    link = interview_attachment_service.get_interview_attachment(
        db, session.org_id, interview_id, attachment_id
    )
    if not link:
        raise HTTPException(status_code=404, detail="Attachment not linked to interview")

    # Check if audio/video
    if not interview_attachment_service.is_audio_video(link.attachment.content_type):
        raise HTTPException(status_code=400, detail="Only audio/video files can be transcribed")

    # Check if already processing
    if link.transcription_status in ["pending", "processing"]:
        raise HTTPException(status_code=400, detail="Transcription already in progress")

    try:
        result = await transcription_service.request_transcription(
            db=db,
            interview_attachment=link,
            language=data.language if data else "en",
            prompt=data.prompt if data else None,
            requested_by_user_id=session.user_id,
        )
        db.commit()
        return TranscriptionStatusRead(
            status="completed",
            progress=100,
            result=result.get("result"),
            error=None,
        )
    except transcription_service.TranscriptionError as e:
        db.commit()  # Commit the failed status
        return TranscriptionStatusRead(
            status="failed",
            progress=None,
            result=None,
            error=str(e),
        )


@router.get(
    "/interviews/{interview_id}/attachments/{attachment_id}/transcription",
    response_model=TranscriptionStatusRead,
)
def get_transcription_status(
    interview_id: UUID,
    attachment_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get transcription status for an attachment."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    link = interview_attachment_service.get_interview_attachment(
        db, session.org_id, interview_id, attachment_id
    )
    if not link:
        raise HTTPException(status_code=404, detail="Attachment not linked to interview")

    return TranscriptionStatusRead(
        status=link.transcription_status or "not_started",
        progress=None,
        result=None,  # Would be populated after completion
        error=link.transcription_error,
    )


# =============================================================================
# AI Summary (Placeholder - full implementation in ai_interview_service)
# =============================================================================


@router.post(
    "/interviews/{interview_id}/ai/summarize",
    response_model=InterviewSummaryResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
async def summarize_interview(
    interview_id: UUID,
    session: UserSession = Depends(require_permission(P.AI_USE)),
    db: Session = Depends(get_db),
):
    """Generate AI summary of a single interview."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    try:
        return await ai_interview_service.summarize_interview(
            db=db,
            interview=interview,
            org_id=session.org_id,
            user_id=session.user_id,
        )
    except ai_interview_service.AIInterviewError as e:
        detail = str(e)
        status_code = 403 if "not enabled" in detail or "consent" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)


@router.post(
    "/interviews/{interview_id}/ai/summarize/stream",
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
async def summarize_interview_stream(
    interview_id: UUID,
    session: UserSession = Depends(require_permission(P.AI_USE)),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream AI summary of a single interview via SSE."""
    from app.services import ai_interview_service
    from app.services.ai_provider import ChatMessage, ChatResponse
    from app.services.ai_usage_service import log_usage
    from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_data

    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    ai_settings = ai_interview_service.get_ai_settings(db, session.org_id)
    if not ai_settings or not ai_settings.is_enabled:
        raise HTTPException(
            status_code=403, detail="AI features are not enabled for this organization"
        )
    if ai_interview_service.is_consent_required(ai_settings):
        raise HTTPException(
            status_code=403, detail="AI consent has not been accepted for this organization"
        )

    provider = ai_interview_service.get_provider(ai_settings, session.org_id, session.user_id)
    if not provider:
        message = (
            "Vertex AI configuration is incomplete"
            if ai_settings.provider == "vertex_wif"
            else "AI API key not configured"
        )
        raise HTTPException(status_code=400, detail=message)

    transcript = interview.transcript_text or ""
    if not transcript:
        raise HTTPException(status_code=400, detail="Interview has no transcript to summarize")

    pii_mapping = None
    known_names: list[str] = []
    if ai_settings.anonymize_pii:
        pii_mapping = PIIMapping()
        surrogate = surrogate_service.get_surrogate(db, session.org_id, interview.surrogate_id)
        if surrogate and surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())
        ai_interview_service._extend_known_names_from_text(known_names, transcript)
        transcript = anonymize_text(transcript, pii_mapping, known_names)

    notes = interview_note_service.list_notes(db, session.org_id, interview.id)
    note_texts: list[str] = []
    for note in notes:
        note_texts.append(note.content)
        for reply in note.replies or []:
            note_texts.append(reply.content)
    notes_text = (
        "\n".join([ai_interview_service._strip_html(content) for content in note_texts])
        if note_texts
        else "No notes"
    )
    if ai_settings.anonymize_pii and pii_mapping:
        ai_interview_service._extend_known_names_from_text(known_names, notes_text)
        notes_text = anonymize_text(notes_text, pii_mapping, known_names)

    prompt = ai_interview_service.INTERVIEW_SUMMARY_PROMPT.format(
        transcript=ai_interview_service._truncate_text(transcript),
        notes=ai_interview_service._truncate_text(notes_text, 5000),
    )

    messages = [
        ChatMessage(role="system", content="You are an expert interview analyst."),
        ChatMessage(role="user", content=prompt),
    ]

    async def event_generator() -> AsyncIterator[str]:
        yield sse_preamble()
        yield format_sse("start", {"status": "thinking"})
        content = ""
        prompt_tokens = 0
        completion_tokens = 0
        model_name = ai_settings.model or ""

        try:
            async for chunk in provider.stream_chat(
                messages=messages, temperature=0.3, max_tokens=2000
            ):
                if chunk.text:
                    content += chunk.text
                    yield format_sse("delta", {"text": chunk.text})
                if chunk.is_final:
                    prompt_tokens = chunk.prompt_tokens
                    completion_tokens = chunk.completion_tokens
                    if chunk.model:
                        model_name = chunk.model
        except asyncio.CancelledError:
            return
        except Exception as exc:
            yield format_sse("error", {"message": f"AI error: {str(exc)}"})
            return

        try:
            result = ai_interview_service._parse_json_response(content)
        except Exception as exc:
            yield format_sse("error", {"message": f"Failed to parse AI response: {str(exc)}"})
            return

        if ai_settings.anonymize_pii and pii_mapping:
            result = rehydrate_data(result, pii_mapping)

        cost = ChatResponse(
            content="",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model_name or (ai_settings.model or "unknown"),
        ).estimated_cost_usd

        log_usage(
            db=db,
            organization_id=session.org_id,
            user_id=session.user_id,
            model=model_name or (ai_settings.model or "unknown"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=cost,
        )

        response = {
            "interview_id": str(interview.id),
            "summary": result.get("summary", ""),
            "key_points": result.get("key_points", []),
            "concerns": result.get("concerns", []),
            "sentiment": result.get("sentiment", "neutral"),
            "follow_up_items": result.get("follow_up_items", []),
        }
        yield format_sse("done", response)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )


@router.post(
    "/surrogates/{surrogate_id}/interviews/ai/summarize-all",
    response_model=AllInterviewsSummaryResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
async def summarize_all_interviews(
    surrogate_id: UUID,
    session: UserSession = Depends(require_permission(P.AI_USE)),
    db: Session = Depends(get_db),
):
    """Generate AI summary of all interviews for a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        return await ai_interview_service.summarize_all_interviews(
            db=db,
            surrogate_id=surrogate_id,
            org_id=session.org_id,
            user_id=session.user_id,
        )
    except ai_interview_service.AIInterviewError as e:
        detail = str(e)
        status_code = 403 if "not enabled" in detail or "consent" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)


@router.post(
    "/surrogates/{surrogate_id}/interviews/ai/summarize-all/stream",
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
async def summarize_all_interviews_stream(
    surrogate_id: UUID,
    session: UserSession = Depends(require_permission(P.AI_USE)),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream AI summary of all interviews via SSE."""
    from app.services import ai_interview_service
    from app.services.ai_provider import ChatMessage, ChatResponse
    from app.services.ai_usage_service import log_usage
    from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_data

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    ai_settings = ai_interview_service.get_ai_settings(db, session.org_id)
    if not ai_settings or not ai_settings.is_enabled:
        raise HTTPException(
            status_code=403, detail="AI features are not enabled for this organization"
        )
    if ai_interview_service.is_consent_required(ai_settings):
        raise HTTPException(
            status_code=403, detail="AI consent has not been accepted for this organization"
        )

    provider = ai_interview_service.get_provider(ai_settings, session.org_id, session.user_id)
    if not provider:
        message = (
            "Vertex AI configuration is incomplete"
            if ai_settings.provider == "vertex_wif"
            else "AI API key not configured"
        )
        raise HTTPException(status_code=400, detail=message)

    interviews = interview_service.list_interviews(db, session.org_id, surrogate_id)
    interviews = sorted(
        interviews, key=lambda interview: interview.conducted_at or interview.created_at
    )

    if not interviews:
        raise HTTPException(status_code=400, detail="No interviews found for this surrogate")

    pii_mapping = None
    known_names: list[str] = []
    if ai_settings.anonymize_pii:
        pii_mapping = PIIMapping()
        if surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())

    interviews_content = []
    for interview in interviews:
        transcript = interview.transcript_text or "No transcript"
        notes = interview_note_service.list_notes(db, session.org_id, interview.id)
        note_texts: list[str] = []
        for note in notes:
            note_texts.append(note.content)
            for reply in note.replies or []:
                note_texts.append(reply.content)
        notes_text = (
            "\n".join([ai_interview_service._strip_html(content) for content in note_texts])
            if note_texts
            else "No notes"
        )
        if ai_settings.anonymize_pii and pii_mapping:
            ai_interview_service._extend_known_names_from_text(known_names, transcript)
            ai_interview_service._extend_known_names_from_text(known_names, notes_text)
            transcript = anonymize_text(transcript, pii_mapping, known_names)
            notes_text = anonymize_text(notes_text, pii_mapping, known_names)

        interviews_content.append(
            f"""--- Interview {len(interviews_content) + 1} ---
Date: {interview.conducted_at.strftime("%Y-%m-%d")}
Type: {interview.interview_type}
Duration: {interview.duration_minutes or "unknown"} minutes

Transcript:
{ai_interview_service._truncate_text(transcript, 10000)}

Notes:
{ai_interview_service._truncate_text(notes_text, 2000)}
"""
        )

    combined_content = "\n\n".join(interviews_content)
    prompt = ai_interview_service.ALL_INTERVIEWS_SUMMARY_PROMPT.format(
        interviews_content=ai_interview_service._truncate_text(combined_content, 60000)
    )

    messages = [
        ChatMessage(
            role="system",
            content="You are an expert interview analyst specializing in candidate evaluation.",
        ),
        ChatMessage(role="user", content=prompt),
    ]

    async def event_generator() -> AsyncIterator[str]:
        yield sse_preamble()
        yield format_sse("start", {"status": "thinking"})
        content = ""
        prompt_tokens = 0
        completion_tokens = 0
        model_name = ai_settings.model or ""

        try:
            async for chunk in provider.stream_chat(
                messages=messages, temperature=0.3, max_tokens=3000
            ):
                if chunk.text:
                    content += chunk.text
                    yield format_sse("delta", {"text": chunk.text})
                if chunk.is_final:
                    prompt_tokens = chunk.prompt_tokens
                    completion_tokens = chunk.completion_tokens
                    if chunk.model:
                        model_name = chunk.model
        except asyncio.CancelledError:
            return
        except Exception as exc:
            yield format_sse("error", {"message": f"AI error: {str(exc)}"})
            return

        try:
            result = ai_interview_service._parse_json_response(content)
        except Exception as exc:
            yield format_sse("error", {"message": f"Failed to parse AI response: {str(exc)}"})
            return

        if ai_settings.anonymize_pii and pii_mapping:
            result = rehydrate_data(result, pii_mapping)

        cost = ChatResponse(
            content="",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model_name or (ai_settings.model or "unknown"),
        ).estimated_cost_usd

        log_usage(
            db=db,
            organization_id=session.org_id,
            user_id=session.user_id,
            model=model_name or (ai_settings.model or "unknown"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=cost,
        )

        response = {
            "surrogate_id": str(surrogate_id),
            "interview_count": len(interviews),
            "overall_summary": result.get("overall_summary", ""),
            "timeline": result.get("timeline", []),
            "recurring_themes": result.get("recurring_themes", []),
            "candidate_strengths": result.get("candidate_strengths", []),
            "areas_of_concern": result.get("areas_of_concern", []),
            "recommended_actions": result.get("recommended_actions", []),
        }
        yield format_sse("done", response)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )


# =============================================================================
# Export
# =============================================================================


@router.get("/interviews/{interview_id}/export")
def export_interview(
    interview_id: UUID,
    format: str = Query("pdf", pattern="^(pdf|json)$"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Export single interview as PDF or JSON."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    # JSON export requires case_manager+
    if format == "json":
        role_str = session.role.value if hasattr(session.role, "value") else session.role
        if role_str not in [
            Role.CASE_MANAGER.value,
            Role.ADMIN.value,
            Role.DEVELOPER.value,
        ]:
            raise HTTPException(
                status_code=403, detail="Case manager or higher required for JSON export"
            )

    surrogate = interview.surrogate
    surrogate_name = (
        surrogate.full_name or f"Surrogate #{surrogate.surrogate_number or surrogate.id}"
    )
    org = org_service.get_org_by_id(db, session.org_id)
    org_name = org.name if org else ""

    if format == "json":
        exports = interview_service.build_interview_exports(
            db=db,
            org_id=session.org_id,
            interviews=[interview],
            current_user_id=session.user_id,
        )
        payload = exports.get(interview.id)
        if not payload:
            raise HTTPException(status_code=404, detail="Interview not found")

        filename = f"interview_{surrogate.surrogate_number or interview.id}.json"
        return JSONResponse(
            content=jsonable_encoder(payload),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    pdf_bytes = pdf_export_service.export_interview_pdf(
        db=db,
        org_id=session.org_id,
        interview=interview,
        surrogate_name=surrogate_name,
        org_name=org_name,
        current_user_id=session.user_id,
    )
    filename = f"interview_{surrogate.surrogate_number or interview.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/surrogates/{surrogate_id}/interviews/export")
def export_all_interviews(
    surrogate_id: UUID,
    format: str = Query("pdf", pattern="^(pdf|json)$"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Export all interviews for a surrogate as PDF or JSON."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    surrogate_name = (
        surrogate.full_name or f"Surrogate #{surrogate.surrogate_number or surrogate.id}"
    )
    org = org_service.get_org_by_id(db, session.org_id)
    org_name = org.name if org else ""

    interviews = interview_service.list_interviews(db, session.org_id, surrogate_id)
    if not interviews:
        raise HTTPException(status_code=404, detail="No interviews found")

    if format == "json":
        exports = interview_service.build_interview_exports(
            db=db,
            org_id=session.org_id,
            interviews=interviews,
            current_user_id=session.user_id,
        )
        payload = {
            "surrogate_id": surrogate.id,
            "surrogate_number": surrogate.surrogate_number,
            "surrogate_name": surrogate_name,
            "interviews": [
                exports[interview.id] for interview in interviews if interview.id in exports
            ],
        }

        filename = f"interviews_{surrogate.surrogate_number or surrogate.id}.json"
        return JSONResponse(
            content=jsonable_encoder(payload),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    pdf_bytes = pdf_export_service.export_interviews_pdf(
        db=db,
        org_id=session.org_id,
        interviews=interviews,
        surrogate_name=surrogate_name,
        org_name=org_name,
        current_user_id=session.user_id,
    )
    filename = f"interviews_{surrogate.surrogate_number or surrogate.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
