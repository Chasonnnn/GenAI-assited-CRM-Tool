"""Work attached to one match occurrence, without inferring links from participants."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import PermissionKey as P
from app.db.models import Attachment, AuditLog, EntityNote, Match, Membership, User
from app.schemas.auth import UserSession
from app.services import (
    attachment_service,
    audit_service,
    match_service,
    note_service,
    permission_service,
    record_access_service,
    task_service,
)


def validate_context(
    db: Session,
    org_id: UUID,
    match_id: UUID,
    attempt_id: UUID | None = None,
    *,
    write: bool = False,
) -> Match:
    from app.db.models.matches import MatchAttempt

    query = db.query(Match).filter(Match.organization_id == org_id, Match.id == match_id)
    match = query.one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    if write:
        match = match_service.lock_match(db, match, org_id)
    if write and match.status in {"completed", "cancelled", "rejected", "cancel_pending"}:
        raise HTTPException(status_code=409, detail="This match is not open for new work")
    if attempt_id:
        attempt = (
            db.query(MatchAttempt)
            .filter(
                MatchAttempt.id == attempt_id,
                MatchAttempt.match_id == match_id,
                MatchAttempt.organization_id == org_id,
            )
            .one_or_none()
        )
        if attempt is None:
            raise HTTPException(status_code=404, detail="Attempt not found in this match")
    return match


def has_permission(db: Session, session: UserSession, permission: P) -> bool:
    return permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        session.role.value,
        permission.value,
    )


def require_permission(db: Session, session: UserSession, permission: P) -> None:
    if not has_permission(db, session, permission):
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission.value}")


def source_fields(db: Session, session: UserSession, match: Match, source: str) -> dict:
    if source == "match":
        return {}
    kind = {"surrogate": "surrogate", "ip": "intended_parent", "donor": "donor"}.get(source)
    record_id = getattr(match, f"{kind}_id", None) if kind else None
    if not record_id:
        raise HTTPException(status_code=400, detail="Source is not a party in this match")
    record = record_access_service.get_record_with_access(
        db, session, kind, record_id, action="edit"
    )
    if record.is_archived:
        raise HTTPException(status_code=409, detail="Cannot add work for an archived record")
    return {f"{kind}_id": record_id}


def list_work(
    db: Session, session: UserSession, match_id: UUID, attempt_id: UUID | None, *, page: int = 1
) -> dict:
    match = match_service.get_match_with_access(db, session, match_id)
    validate_context(db, session.org_id, match_id, attempt_id)
    can_notes = not match.surrogate_id or has_permission(db, session, P.SURROGATES_VIEW_NOTES)
    can_tasks = has_permission(db, session, P.TASKS_VIEW)
    notes_query = (
        db.query(EntityNote)
        .options(joinedload(EntityNote.author))
        .filter(
            EntityNote.organization_id == session.org_id,
            EntityNote.match_id == match_id,
        )
    )
    files_query = db.query(Attachment).filter(
        Attachment.organization_id == session.org_id,
        Attachment.match_id == match_id,
        Attachment.deleted_at.is_(None),
        Attachment.scan_status.notin_(["infected", "error"]),
    )
    activity_query = (
        db.query(AuditLog, User.display_name)
        .outerjoin(
            Membership,
            (Membership.user_id == AuditLog.actor_user_id)
            & (Membership.organization_id == AuditLog.organization_id),
        )
        .outerjoin(User, User.id == Membership.user_id)
        .filter(
            AuditLog.organization_id == session.org_id,
            AuditLog.target_type == "match",
            AuditLog.target_id == match_id,
        )
    )
    if attempt_id:
        notes_query = notes_query.filter(EntityNote.attempt_id == attempt_id)
        files_query = files_query.filter(Attachment.attempt_id == attempt_id)
        activity_query = activity_query.filter(
            AuditLog.details["attempt_id"].astext == str(attempt_id)
        )
    offset = (page - 1) * 200
    notes = (
        notes_query.order_by(EntityNote.created_at.desc(), EntityNote.id)
        .offset(offset)
        .limit(201)
        .all()
        if can_notes
        else []
    )
    files = (
        files_query.order_by(Attachment.created_at.desc(), Attachment.id)
        .offset(offset)
        .limit(201)
        .all()
    )
    activities = (
        activity_query.order_by(AuditLog.created_at.desc(), AuditLog.id)
        .offset(offset)
        .limit(201)
        .all()
    )
    task_result = (
        task_service.list_tasks_for_session(
            db,
            None,
            session,
            match_id=match_id,
            attempt_id=attempt_id,
            per_page=200,
            page=page,
            exclude_approvals=True,
        )
        if can_tasks
        else None
    )
    note_items = [
        {
            "id": str(n.id),
            "content": n.content,
            "created_at": n.created_at,
            "author_name": n.author.display_name if n.author else None,
            "source": n.work_source or "match",
        }
        for n in notes[:200]
    ]
    if match.notes and not attempt_id and can_notes and page == 1:
        note_items.append(
            {
                "id": "match-notes",
                "content": match.notes,
                "created_at": match.updated_at,
                "author_name": None,
                "source": "match",
            }
        )
    return {
        "notes": note_items,
        "files": [
            {
                "id": str(f.id),
                "filename": f.filename,
                "file_size": f.file_size,
                "created_at": f.created_at,
                "source": "donor"
                if f.donor_id
                else "surrogate"
                if f.surrogate_id
                else "ip"
                if f.intended_parent_id
                else "match",
            }
            for f in files[:200]
        ],
        "tasks": [
            {
                "id": str(t.id),
                "title": t.title,
                "due_date": t.due_date,
                "is_completed": t.is_completed,
                "source": t.work_source or "match",
            }
            for t in task_result.items
        ]
        if task_result
        else [],
        "activity": [
            {
                "id": str(a.id),
                "event_type": a.event_type.replace("_", " ").title(),
                "description": a.event_type.replace("_", " ").capitalize(),
                "actor_name": actor,
                "created_at": a.created_at,
                "source": "match",
            }
            for a, actor in activities[:200]
        ],
        "has_more": len(notes) > 200
        or len(files) > 200
        or len(activities) > 200
        or (task_result is not None and task_result.total > page * 200),
        "can_view_notes": can_notes,
        "can_view_tasks": can_tasks,
    }


def create_note(db: Session, session: UserSession, match_id: UUID, data) -> EntityNote:
    match = match_service.get_match_with_access(db, session, match_id)
    require_permission(db, session, P.MATCHES_PROPOSE)
    validate_context(db, session.org_id, match_id, data.attempt_id, write=True)
    source_fields(db, session, match, data.source)
    if match.surrogate_id:
        require_permission(db, session, P.SURROGATES_EDIT_NOTES)
    try:
        note = note_service.create_note(
            db,
            session.org_id,
            "match",
            match_id,
            session.user_id,
            data.content,
            commit=False,
            emit_events=False,
            match_id=match_id,
            attempt_id=data.attempt_id,
        )
        note.work_source = data.source
        db.commit()
        db.refresh(note)
        return note
    except Exception:
        db.rollback()
        raise


def upload_file(
    db: Session,
    session: UserSession,
    match_id: UUID,
    attempt_id: UUID | None,
    source: str,
    file,
    file_size: int,
) -> Attachment:
    from app.db.enums import AuditEventType

    match = match_service.get_match_with_access(db, session, match_id)
    require_permission(db, session, P.MATCHES_PROPOSE)
    validate_context(db, session.org_id, match_id, attempt_id, write=True)
    fields = source_fields(db, session, match, source)
    try:
        attachment = attachment_service.upload_attachment(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            filename=file.filename or "untitled",
            content_type=file.content_type or "application/octet-stream",
            file=file.file,
            file_size=file_size,
            match_id=match_id,
            attempt_id=attempt_id,
            **fields,
        )
        audit_service.log_event(
            db,
            session.org_id,
            AuditEventType.ATTACHMENT_UPLOADED,
            actor_user_id=session.user_id,
            target_type="match",
            target_id=match_id,
            details={
                "attachment_id": str(attachment.id),
                "attempt_id": str(attempt_id) if attempt_id else None,
            },
        )
        db.commit()
        if attachment.scan_status != "clean":
            attachment_service.dispatch_attachment_scan_if_needed(db, session.org_id, attachment.id)
        return attachment
    except Exception:
        db.rollback()
        raise
