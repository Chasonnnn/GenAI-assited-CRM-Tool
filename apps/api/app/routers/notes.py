"""Notes router - API endpoints for surrogate notes.

Uses unified EntityNote model with entity_type='surrogate'.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    is_owner_or_can_manage,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.core.surrogate_access import check_surrogate_access
from app.schemas.auth import UserSession
from app.db.enums import AuditEventType
from app.schemas.note import NoteCreate, NoteRead
from app.services import surrogate_service, note_service

router = APIRouter(
    dependencies=[Depends(require_permission(POLICIES["surrogates"].actions["notes_view"]))]
)


@router.get("/surrogates/{surrogate_id}/notes", response_model=list[NoteRead])
def list_notes(
    surrogate_id: UUID,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List notes for a surrogate (respects role-based access)."""
    # Verify surrogate exists and belongs to org
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    # Access control: checks ownership + post-approval permission
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    notes = note_service.list_notes(db, session.org_id, "surrogate", surrogate_id)

    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_VIEW_NOTE,
        actor_user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate_id,
        details={"notes_count": len(notes)},
        request=request,
    )
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate_id,
        request=request,
        details={"view": "notes", "notes_count": len(notes)},
    )
    db.commit()

    return [note_service.to_note_read(n) for n in notes]


@router.post(
    "/surrogates/{surrogate_id}/notes",
    response_model=NoteRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_note(
    surrogate_id: UUID,
    data: NoteCreate,
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["notes_edit"])
    ),
    db: Session = Depends(get_db),
):
    """Add a note to a surrogate (respects role-based access)."""
    # Verify surrogate exists and belongs to org
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    # Access control: checks ownership + post-approval permission
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    note = note_service.create_note(
        db=db,
        org_id=session.org_id,
        entity_type="surrogate",
        entity_id=surrogate_id,
        author_id=session.user_id,
        content=data.body,
    )

    # Log to surrogate activity
    from app.services import activity_service

    activity_service.log_note_added(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=session.org_id,
        actor_user_id=session.user_id,
        note_id=note.id,
        content=note.content,
    )
    db.commit()

    return note_service.to_note_read(note)


@router.delete("/notes/{note_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
def delete_note(
    note_id: UUID,
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["notes_edit"])
    ),
    db: Session = Depends(get_db),
):
    """
    Delete a note.

    Requires: author or admin+
    Access: Respects role-based surrogate access (intake can't delete on handed-off surrogates)
    """
    note = note_service.get_note(db, note_id, session.org_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Access control: check surrogate access if note is linked to a surrogate
    if note.entity_type == "surrogate":
        surrogate = surrogate_service.get_surrogate(db, session.org_id, note.entity_id)
        if surrogate:
            check_surrogate_access(
                surrogate, session.role, session.user_id, db=db, org_id=session.org_id
            )

    # Permission: author or admin+
    if not is_owner_or_can_manage(session, note.author_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")

    # Log to surrogate activity before delete (only for surrogate notes)
    if note.entity_type == "surrogate":
        from app.services import activity_service

        activity_service.log_note_deleted(
            db=db,
            surrogate_id=note.entity_id,
            organization_id=session.org_id,
            actor_user_id=session.user_id,
            note_id=note.id,
            content_preview=note.content[:200] if note.content else "",
        )
        db.commit()

    note_service.delete_note(db, note)
    return None
