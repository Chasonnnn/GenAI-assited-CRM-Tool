"""Notes router - API endpoints for case notes.

Uses unified EntityNote model with entity_type='case'.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    is_owner_or_can_manage,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.core.case_access import check_case_access
from app.schemas.auth import UserSession
from app.schemas.note import NoteCreate, NoteRead
from app.services import case_service, note_service

router = APIRouter(
    dependencies=[Depends(require_permission(POLICIES["cases"].actions["notes_view"]))]
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

    # Access control: checks ownership + post-approval permission
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    notes = note_service.list_notes(db, session.org_id, "case", case_id)
    return [note_service.to_note_read(n) for n in notes]


@router.post(
    "/cases/{case_id}/notes",
    response_model=NoteRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_note(
    case_id: UUID,
    data: NoteCreate,
    session: UserSession = Depends(
        require_permission(POLICIES["cases"].actions["notes_edit"])
    ),
    db: Session = Depends(get_db),
):
    """Add a note to a case (respects role-based access)."""
    # Verify case exists and belongs to org
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Access control: checks ownership + post-approval permission
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    note = note_service.create_note(
        db=db,
        org_id=session.org_id,
        entity_type="case",
        entity_id=case_id,
        author_id=session.user_id,
        content=data.body,
    )

    # Log to case activity
    from app.services import activity_service

    activity_service.log_note_added(
        db=db,
        case_id=case_id,
        organization_id=session.org_id,
        actor_user_id=session.user_id,
        note_id=note.id,
        content=note.content,
    )
    db.commit()

    return note_service.to_note_read(note)


@router.delete(
    "/notes/{note_id}", status_code=204, dependencies=[Depends(require_csrf_header)]
)
def delete_note(
    note_id: UUID,
    session: UserSession = Depends(
        require_permission(POLICIES["cases"].actions["notes_edit"])
    ),
    db: Session = Depends(get_db),
):
    """
    Delete a note.

    Requires: author or manager+
    Access: Respects role-based case access (intake can't delete on handed-off cases)
    """
    note = note_service.get_note(db, note_id, session.org_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Access control: check case access if note is linked to a case
    if note.entity_type == "case":
        case = case_service.get_case(db, session.org_id, note.entity_id)
        if case:
            check_case_access(
                case, session.role, session.user_id, db=db, org_id=session.org_id
            )

    # Permission: author or manager+
    if not is_owner_or_can_manage(session, note.author_id):
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this note"
        )

    # Log to case activity before delete (only for case notes)
    if note.entity_type == "case":
        from app.services import activity_service

        activity_service.log_note_deleted(
            db=db,
            case_id=note.entity_id,
            organization_id=session.org_id,
            actor_user_id=session.user_id,
            note_id=note.id,
            content_preview=note.content[:200] if note.content else "",
        )
        db.commit()

    note_service.delete_note(db, note)
    return None
