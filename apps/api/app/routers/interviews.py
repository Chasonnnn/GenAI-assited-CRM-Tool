"""Interviews router - API endpoints for case interviews.

Endpoints:
- Interview CRUD
- Version management (list, get, diff, restore)
- Notes CRUD with anchoring
- Attachment linking
- AI features (transcription, summary)
- Export (PDF, JSON)
"""

from typing import BinaryIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.case_access import can_modify_case, check_case_access
from app.core.deps import (
    get_current_session,
    get_db,
    is_owner_or_can_manage,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.core.permissions import PermissionKey as P
from app.db.enums import Role
from app.schemas.auth import UserSession
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
from app.db.enums import JobType
from app.services import (
    attachment_service,
    ai_interview_service,
    case_service,
    interview_attachment_service,
    interview_note_service,
    interview_service,
    job_service,
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
    """Get interview and verify case access."""
    interview = interview_service.get_interview(db, org_id, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Check case access
    case = interview.case
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    check_case_access(
        case, session.role, session.user_id, db=db, org_id=session.org_id
    )

    return interview, case


def _check_can_modify_interview(case, session: UserSession):
    """Check if user can create/edit interviews on this case."""
    if not can_modify_case(case, session.user_id, session.role):
        raise HTTPException(
            status_code=403, detail="You don't have permission to modify this case"
        )


def _check_admin_only(session: UserSession):
    """Check if user has admin+ role."""
    role_str = session.role.value if hasattr(session.role, "value") else session.role
    if role_str not in [Role.ADMIN.value, Role.DEVELOPER.value]:
        raise HTTPException(status_code=403, detail="Admin access required")


# =============================================================================
# Interview CRUD
# =============================================================================


@router.get("/cases/{case_id}/interviews", response_model=list[InterviewListItem])
def list_interviews(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List all interviews for a case."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    check_case_access(
        case, session.role, session.user_id, db=db, org_id=session.org_id
    )

    return interview_service.list_interviews_with_counts(db, session.org_id, case_id)


@router.post(
    "/cases/{case_id}/interviews",
    response_model=InterviewRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_interview(
    case_id: UUID,
    data: InterviewCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a new interview for a case."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    check_case_access(
        case, session.role, session.user_id, db=db, org_id=session.org_id
    )
    _check_can_modify_interview(case, session)

    try:
        interview = interview_service.create_interview(
            db=db,
            org_id=session.org_id,
            case_id=case_id,
            user_id=session.user_id,
            data=data,
        )
        db.commit()
        return interview_service.to_interview_read(db, interview)
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
    interview, case = _check_interview_access(
        db, session.org_id, interview_id, session
    )
    _check_can_modify_interview(case, session)

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

    version_obj = interview_service.get_version(
        db, session.org_id, interview_id, version
    )
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
        diff = interview_service.get_version_diff(
            db, session.org_id, interview_id, v1, v2
        )
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
    interview, case = _check_interview_access(
        db, session.org_id, interview_id, session
    )
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
    """Update a note (author only)."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    note = interview_note_service.get_note(db, session.org_id, note_id)
    if not note or note.interview_id != interview_id:
        raise HTTPException(status_code=404, detail="Note not found")

    # Only author can update
    if note.author_user_id != session.user_id:
        raise HTTPException(status_code=403, detail="Only the author can edit this note")

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
    """Delete a note (author or admin+)."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    note = interview_note_service.get_note(db, session.org_id, note_id)
    if not note or note.interview_id != interview_id:
        raise HTTPException(status_code=404, detail="Note not found")

    # Author or admin+ can delete
    if not is_owner_or_can_manage(session, note.author_user_id):
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this note"
        )

    interview_note_service.delete_note(db, note)
    db.commit()
    return None


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
    file: UploadFile = File(...),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Upload a new attachment and link it to the interview."""
    interview, case = _check_interview_access(
        db, session.org_id, interview_id, session
    )
    _check_can_modify_interview(case, session)

    # Read file content
    content = await file.read()
    from io import BytesIO

    file_obj = BytesIO(content)

    try:
        # Upload attachment
        attachment = attachment_service.upload_attachment(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            filename=file.filename or "unknown",
            content_type=file.content_type or "application/octet-stream",
            file=file_obj,
            file_size=len(content),
            case_id=case.id,
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
    interview, case = _check_interview_access(
        db, session.org_id, interview_id, session
    )
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
    interview, case = _check_interview_access(
        db, session.org_id, interview_id, session
    )

    role_str = session.role.value if hasattr(session.role, "value") else session.role
    if role_str not in [
        Role.CASE_MANAGER.value,
        Role.ADMIN.value,
        Role.DEVELOPER.value,
    ]:
        raise HTTPException(
            status_code=403, detail="Case manager or higher required"
        )

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
    dependencies=[Depends(require_csrf_header)],
)
def request_transcription(
    interview_id: UUID,
    attachment_id: UUID,
    data: TranscriptionRequest | None = None,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Request AI transcription for an audio/video attachment."""
    interview, case = _check_interview_access(
        db, session.org_id, interview_id, session
    )
    _check_can_modify_interview(case, session)

    link = interview_attachment_service.get_interview_attachment(
        db, session.org_id, interview_id, attachment_id
    )
    if not link:
        raise HTTPException(status_code=404, detail="Attachment not linked to interview")

    # Check if audio/video
    if not interview_attachment_service.is_audio_video(link.attachment.content_type):
        raise HTTPException(
            status_code=400, detail="Only audio/video files can be transcribed"
        )

    # Check if already processing
    if link.transcription_status in ["pending", "processing"]:
        raise HTTPException(
            status_code=400, detail="Transcription already in progress"
        )

    # Update status to pending
    interview_attachment_service.update_transcription_status(
        db, link, status="pending"
    )
    job_service.schedule_job(
        db=db,
        org_id=session.org_id,
        job_type=JobType.INTERVIEW_TRANSCRIPTION,
        payload={
            "interview_attachment_id": str(link.id),
            "interview_id": str(interview_id),
            "attachment_id": str(attachment_id),
            "language": data.language if data else "en",
            "prompt": data.prompt if data else None,
            "requested_by_user_id": str(session.user_id),
        },
    )

    return TranscriptionStatusRead(
        status="pending",
        progress=None,
        result=None,
        error=None,
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
    dependencies=[Depends(require_csrf_header)],
)
def summarize_interview(
    interview_id: UUID,
    session: UserSession = Depends(require_permission(P.AI_USE)),
    db: Session = Depends(get_db),
):
    """Generate AI summary of a single interview."""
    interview, _ = _check_interview_access(db, session.org_id, interview_id, session)

    import asyncio

    try:
        return asyncio.get_event_loop().run_until_complete(
            ai_interview_service.summarize_interview(
                db=db,
                interview=interview,
                org_id=session.org_id,
                user_id=session.user_id,
            )
        )
    except ai_interview_service.AIInterviewError as e:
        detail = str(e)
        status_code = 403 if "not enabled" in detail or "consent" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)


@router.post(
    "/cases/{case_id}/interviews/ai/summarize-all",
    response_model=AllInterviewsSummaryResponse,
    dependencies=[Depends(require_csrf_header)],
)
def summarize_all_interviews(
    case_id: UUID,
    session: UserSession = Depends(require_permission(P.AI_USE)),
    db: Session = Depends(get_db),
):
    """Generate AI summary of all interviews for a case."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    check_case_access(
        case, session.role, session.user_id, db=db, org_id=session.org_id
    )

    import asyncio

    try:
        return asyncio.get_event_loop().run_until_complete(
            ai_interview_service.summarize_all_interviews(
                db=db,
                case_id=case_id,
                org_id=session.org_id,
                user_id=session.user_id,
            )
        )
    except ai_interview_service.AIInterviewError as e:
        detail = str(e)
        status_code = 403 if "not enabled" in detail or "consent" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)


# =============================================================================
# Export (Placeholder - full implementation in interview_export_service)
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

    # TODO: Implement export
    raise HTTPException(status_code=501, detail="Export not yet implemented")


@router.get("/cases/{case_id}/interviews/export")
def export_all_interviews(
    case_id: UUID,
    format: str = Query("pdf", pattern="^(pdf|json)$"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Export all interviews for a case as PDF or JSON."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    check_case_access(
        case, session.role, session.user_id, db=db, org_id=session.org_id
    )

    # TODO: Implement export
    raise HTTPException(status_code=501, detail="Export not yet implemented")
