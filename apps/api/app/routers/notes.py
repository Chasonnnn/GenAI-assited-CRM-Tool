"""Notes router - API endpoints for case notes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    is_owner_or_can_manage,
    require_csrf_header,
)
from app.core.case_access import check_case_access
from app.db.models import User
from app.schemas.auth import UserSession
from app.schemas.note import NoteCreate, NoteRead
from app.services import case_service, note_service

router = APIRouter()


def _note_to_read(note, db: Session) -> NoteRead:
    """Convert Note model to NoteRead schema."""
    author_name = None
    if note.author_id:
        user = db.query(User).filter(User.id == note.author_id).first()
        author_name = user.display_name if user else None
    
    return NoteRead(
        id=note.id,
        case_id=note.case_id,
        author_id=note.author_id,
        author_name=author_name,
        body=note.body,
        created_at=note.created_at,
    )


@router.get("/cases/{case_id}/notes", response_model=list[NoteRead])
def list_notes(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List notes for a case (respects role-based access)."""
    # Verify case exists and belongs to org
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control: intake can't access handed-off cases
    check_case_access(case, session.role)
    
    notes = note_service.list_notes(db, case_id, session.org_id)
    return [_note_to_read(n, db) for n in notes]


@router.post("/cases/{case_id}/notes", response_model=NoteRead, status_code=201, dependencies=[Depends(require_csrf_header)])
def create_note(
    case_id: UUID,
    data: NoteCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Add a note to a case (respects role-based access)."""
    # Verify case exists and belongs to org
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control: intake can't access handed-off cases
    check_case_access(case, session.role)
    
    note = note_service.create_note(
        db=db,
        case_id=case_id,
        org_id=session.org_id,
        author_id=session.user_id,
        body=data.body,
    )
    return _note_to_read(note, db)


@router.delete("/notes/{note_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
def delete_note(
    note_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Delete a note.
    
    Requires: author or manager+
    """
    note = note_service.get_note(db, note_id, session.org_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Permission: author or manager+
    if not is_owner_or_can_manage(session, note.author_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")
    
    note_service.delete_note(db, note)
    return None
