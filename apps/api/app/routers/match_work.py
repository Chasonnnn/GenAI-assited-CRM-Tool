"""Case-scoped notes, files, tasks, and activity."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.deps import get_db, is_owner_or_can_manage, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession
from app.services import attachment_service, match_service, match_work_service, note_service
from app.utils.file_upload import content_length_exceeds_limit, get_upload_file_size

router = APIRouter(prefix="/matches", tags=["matches"])
SessionDep = Annotated[UserSession, Depends(require_permission(P.MATCHES_VIEW))]
DatabaseDep = Annotated[Session, Depends(get_db)]
Source = Literal["match", "surrogate", "ip", "donor"]


class WorkNoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=50000)
    source: Source = "match"
    attempt_id: UUID | None = None


class WorkNoteRead(BaseModel):
    id: str
    content: str
    created_at: datetime
    author_name: str | None = None
    source: Source
    scope: Literal["case", "record"] = "case"


class WorkFileRead(BaseModel):
    id: UUID
    filename: str
    file_size: int
    created_at: datetime
    source: Source = "match"
    scope: Literal["case", "record"] = "case"


class WorkTaskRead(BaseModel):
    id: UUID
    title: str
    due_date: date | None
    is_completed: bool
    source: Source = "match"
    scope: Literal["case", "record"] = "case"


class WorkActivityRead(BaseModel):
    id: UUID
    event_type: str
    description: str
    actor_name: str | None
    created_at: datetime
    source: Source = "match"
    scope: Literal["case", "record"] = "case"


class WorkRead(BaseModel):
    notes: list[WorkNoteRead]
    files: list[WorkFileRead]
    tasks: list[WorkTaskRead]
    activity: list[WorkActivityRead]
    has_more: bool
    can_view_notes: bool
    can_view_tasks: bool


@router.get("/{match_id}/work", response_model=WorkRead)
def get_work(
    match_id: UUID,
    session: SessionDep,
    db: DatabaseDep,
    attempt_id: UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
):
    return match_work_service.list_work(db, session, match_id, attempt_id, page=page)


@router.post(
    "/{match_id}/notes",
    response_model=WorkNoteRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def add_note(match_id: UUID, data: WorkNoteCreate, session: SessionDep, db: DatabaseDep):
    note = match_work_service.create_note(db, session, match_id, data)
    return WorkNoteRead(
        id=str(note.id),
        content=note.content,
        created_at=note.created_at,
        source=note.work_source,
        author_name=note.author.display_name if note.author else None,
    )


@router.delete(
    "/{match_id}/notes/{note_id}", status_code=204, dependencies=[Depends(require_csrf_header)]
)
def delete_note(match_id: UUID, note_id: UUID, session: SessionDep, db: DatabaseDep) -> Response:
    match = match_service.get_match_with_access(db, session, match_id)
    if match.surrogate_id:
        match_work_service.require_permission(db, session, P.SURROGATES_EDIT_NOTES)
    match_work_service.require_permission(db, session, P.MATCHES_PROPOSE)
    note = note_service.get_note(db, note_id, session.org_id)
    if note is None or note.match_id != match_id:
        raise HTTPException(status_code=404, detail="Note not found")
    match_work_service.source_fields(db, session, match, note.work_source or "match")
    if not is_owner_or_can_manage(session, note.author_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")
    note_service.delete_note(db, note, actor_user_id=session.user_id)
    return Response(status_code=204)


@router.post(
    "/{match_id}/attachments",
    response_model=WorkFileRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
async def upload_file(
    match_id: UUID,
    request: Request,
    session: SessionDep,
    db: DatabaseDep,
    file: Annotated[UploadFile, File()],
    source: Source = "match",
    attempt_id: UUID | None = None,
):
    limit = attachment_service.MAX_FILE_SIZE_BYTES
    if content_length_exceeds_limit(request.headers.get("content-length"), max_size_bytes=limit):
        raise HTTPException(status_code=400, detail="File size exceeds upload limit")
    size = await get_upload_file_size(file)
    if size > limit:
        raise HTTPException(status_code=400, detail="File size exceeds upload limit")
    file.file.seek(0)
    try:
        attachment = await run_in_threadpool(
            match_work_service.upload_file, db, session, match_id, attempt_id, source, file, size
        )
    except attachment_service.AttachmentStorageError as exc:
        raise HTTPException(status_code=503, detail="File storage is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkFileRead(
        id=attachment.id,
        filename=attachment.filename,
        file_size=attachment.file_size,
        created_at=attachment.created_at,
        source=source,
    )
