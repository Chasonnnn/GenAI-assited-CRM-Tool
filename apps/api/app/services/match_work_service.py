"""Work attached to one match occurrence, without inferring links from participants."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import String, and_, cast, exists, func, literal, or_, select, union_all
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import PermissionKey as P
from app.db.models import (
    Attachment,
    AuditLog,
    EntityActivityLog,
    EntityNote,
    IntendedParentStatusHistory,
    Match,
    Membership,
    SurrogateActivityLog,
    Task,
    User,
)
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
        from app.core.match_rollout import require_match_expansion

        require_match_expansion()
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


def record_history_filter(model, match: Match):
    """Participant work without case context; explicit other parties are excluded."""
    belongs = []
    consistent = []
    for field in ("surrogate_id", "intended_parent_id", "donor_id"):
        column, expected = getattr(model, field), getattr(match, field)
        if expected:
            belongs.append(column == expected)
            consistent.append(or_(column.is_(None), column == expected))
        else:
            consistent.append(column.is_(None))
    return and_(model.match_id.is_(None), or_(*belongs), *consistent)


def work_source(item) -> str:
    return getattr(item, "work_source", None) or (
        "donor" if item.donor_id else "surrogate" if item.surrogate_id else "ip"
    )


def _record_activity_filter(model, org_id):
    """Exclude case events, including old events with only a linked work ID."""
    predicates = [model.details["match_id"].astext.is_(None)]
    for key, work_model in (
        ("task_id", Task),
        ("note_id", EntityNote),
        ("attachment_id", Attachment),
    ):
        reference = model.details[key].astext
        predicates.append(
            ~exists(
                select(work_model.id).where(
                    work_model.organization_id == org_id,
                    cast(work_model.id, String) == reference,
                    work_model.match_id.is_not(None),
                )
            )
        )
        # Deleted case work still has durable case audit provenance.
        predicates.append(
            ~exists(
                select(AuditLog.id).where(
                    AuditLog.organization_id == org_id,
                    AuditLog.target_type == "match",
                    AuditLog.details[key].astext == reference,
                )
            )
        )
    return and_(*predicates)


def _list_activity(db, session, match, attempt_id, page):
    def fields(model, event_type, actor, timestamp, source, scope):
        return select(
            model.id.label("id"),
            event_type.label("event_type"),
            actor.label("actor_user_id"),
            timestamp.label("created_at"),
            literal(source).label("source"),
            literal(scope).label("scope"),
        )

    case_query = fields(
        AuditLog, AuditLog.event_type, AuditLog.actor_user_id, AuditLog.created_at, "match", "case"
    ).where(
        AuditLog.organization_id == session.org_id,
        AuditLog.target_type == "match",
        AuditLog.target_id == match.id,
    )
    if attempt_id:
        case_query = case_query.where(AuditLog.details["attempt_id"].astext == str(attempt_id))
    queries = [case_query]
    if not attempt_id:
        if match.surrogate_id:
            model = SurrogateActivityLog
            queries.append(
                fields(
                    model,
                    model.activity_type,
                    model.actor_user_id,
                    model.created_at,
                    "surrogate",
                    "record",
                ).where(
                    model.organization_id == session.org_id,
                    model.surrogate_id == match.surrogate_id,
                    _record_activity_filter(model, session.org_id),
                )
            )
        for source, field in (("ip", "intended_parent_id"), ("donor", "donor_id")):
            if getattr(match, field):
                model = EntityActivityLog
                queries.append(
                    fields(
                        model,
                        model.activity_type,
                        model.actor_user_id,
                        model.occurred_at,
                        source,
                        "record",
                    ).where(
                        model.organization_id == session.org_id,
                        getattr(model, field) == getattr(match, field),
                        _record_activity_filter(model, session.org_id),
                    )
                )
        history = IntendedParentStatusHistory
        queries.append(
            fields(
                history,
                literal("status_changed"),
                history.changed_by_user_id,
                func.coalesce(history.effective_at, history.changed_at),
                "ip",
                "record",
            ).where(
                history.organization_id == session.org_id,
                history.intended_parent_id == match.intended_parent_id,
            )
        )
    activity = union_all(*queries).subquery()
    rows = (
        db.execute(
            select(activity, User.display_name.label("actor_name"))
            .outerjoin(
                Membership,
                and_(
                    Membership.user_id == activity.c.actor_user_id,
                    Membership.organization_id == session.org_id,
                ),
            )
            .outerjoin(User, User.id == Membership.user_id)
            .order_by(activity.c.created_at.desc(), activity.c.id)
            .offset((page - 1) * 200)
            .limit(201)
        )
        .mappings()
        .all()
    )
    return [
        {
            "id": str(row["id"]),
            "event_type": row["event_type"].replace("_", " ").title(),
            "description": row["event_type"].replace("_", " ").capitalize(),
            "actor_name": row["actor_name"],
            "created_at": row["created_at"],
            "source": row["source"],
            "scope": row["scope"],
        }
        for row in rows
    ]


def list_work(
    db: Session, session: UserSession, match_id: UUID, attempt_id: UUID | None, *, page: int = 1
) -> dict:
    match = match_service.get_match_with_access(db, session, match_id, allow_archived=True)
    validate_context(db, session.org_id, match_id, attempt_id)
    can_case_notes = not match.surrogate_id or has_permission(db, session, P.SURROGATES_VIEW_NOTES)
    can_notes = can_case_notes or not attempt_id
    can_tasks = has_permission(db, session, P.TASKS_VIEW)
    note_scopes = [EntityNote.match_id == match_id] if can_case_notes else []
    file_scope = Attachment.match_id == match_id
    if not attempt_id:
        participants = [("intended_parent", match.intended_parent_id)]
        if match.donor_id:
            participants.append(("donor", match.donor_id))
        elif can_case_notes:
            participants.append(("surrogate", match.surrogate_id))
        note_scopes.append(
            and_(
                EntityNote.match_id.is_(None),
                or_(
                    *[
                        and_(EntityNote.entity_type == kind, EntityNote.entity_id == record_id)
                        for kind, record_id in participants
                    ]
                ),
            )
        )
        file_scope = or_(file_scope, record_history_filter(Attachment, match))
    notes_query = (
        db.query(EntityNote)
        .options(joinedload(EntityNote.author))
        .filter(
            EntityNote.organization_id == session.org_id,
            or_(*note_scopes) if note_scopes else literal(False),
        )
    )
    files_query = db.query(Attachment).filter(
        Attachment.organization_id == session.org_id,
        file_scope,
        Attachment.deleted_at.is_(None),
        Attachment.scan_status.notin_(["infected", "error"]),
    )
    if attempt_id:
        notes_query = notes_query.filter(EntityNote.attempt_id == attempt_id)
        files_query = files_query.filter(Attachment.attempt_id == attempt_id)
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
    activities = _list_activity(db, session, match, attempt_id, page)
    task_result = (
        task_service.list_tasks_for_session(
            db,
            None,
            session,
            match_id=match_id,
            attempt_id=attempt_id,
            include_record_history=not attempt_id,
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
            "source": n.work_source
            or (
                "match"
                if n.match_id
                else "ip"
                if n.entity_type == "intended_parent"
                else n.entity_type
            ),
            "scope": "case" if n.match_id else "record",
        }
        for n in notes[:200]
    ]
    if match.notes and not attempt_id and can_case_notes and page == 1:
        note_items.append(
            {
                "id": "match-notes",
                "content": match.notes,
                "created_at": match.updated_at,
                "author_name": None,
                "source": "match",
                "scope": "case",
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
                "scope": "case" if f.match_id else "record",
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
                "source": t.work_source or ("match" if t.match_id else work_source(t)),
                "scope": "case" if t.match_id else "record",
            }
            for t in task_result.items
        ]
        if task_result
        else [],
        "activity": activities[:200],
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
