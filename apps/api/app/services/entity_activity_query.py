"""Select activity identities before hydrating their permission-controlled content."""

from uuid import UUID

from sqlalchemy import String, cast, exists, func, literal, select, union_all
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from app.db.models import (
    Attachment,
    DonorStatusHistory,
    EntityActivityLog,
    EntityNote,
    IntendedParent,
    IntendedParentStatusHistory,
    Task,
)


def _synthetic_event_id_sql(source_id, activity_type: str):
    """Match uuid.uuid5(source_id, activity_type) using baseline pgcrypto."""
    digest = func.digest(
        func.uuid_send(source_id).op("||")(func.convert_to(literal(activity_type), "UTF8")),
        "sha1",
    )
    versioned = func.set_byte(
        func.substring(digest, 1, 16), 6, func.get_byte(digest, 6).op("&")(15).op("|")(80)
    )
    variant = func.set_byte(versioned, 8, func.get_byte(digest, 8).op("&")(63).op("|")(128))
    return cast(func.encode(variant, "hex"), PGUUID(as_uuid=True))


def select_activity_page(
    db: Session,
    *,
    org_id: UUID,
    entity_type: str,
    entity_id: UUID,
    page: int,
    per_page: int,
):
    """Count and page durable, status and missing legacy events in PostgreSQL."""
    is_ip = entity_type == "intended_parent"
    activity_subject = EntityActivityLog.intended_parent_id if is_ip else EntityActivityLog.donor_id
    task_subject = Task.intended_parent_id if is_ip else Task.donor_id
    attachment_subject = Attachment.intended_parent_id if is_ip else Attachment.donor_id
    activity_scope = (
        EntityActivityLog.organization_id == org_id,
        activity_subject == entity_id,
    )
    logged_sources = union_all(
        *(
            select(
                EntityActivityLog.activity_type,
                EntityActivityLog.details[key].astext.label("source_id"),
            ).where(*activity_scope, EntityActivityLog.details[key].astext.is_not(None))
            for key in ("note_id", "task_id", "attachment_id")
        )
    ).cte("logged_sources")

    def identity(source, source_id, event_id, activity_type, occurred_at):
        return select(
            literal(source).label("source"),
            source_id.label("source_id"),
            event_id.label("id"),
            activity_type.label("activity_type"),
            occurred_at.label("occurred_at"),
        )

    queries = [
        identity(
            "activity",
            EntityActivityLog.id,
            EntityActivityLog.id,
            EntityActivityLog.activity_type,
            EntityActivityLog.occurred_at,
        ).where(*activity_scope)
    ]
    if is_ip:
        history = IntendedParentStatusHistory
        queries.append(
            identity(
                "status",
                history.id,
                history.id,
                literal("status_changed"),
                func.coalesce(history.effective_at, history.changed_at),
            )
            .join(IntendedParent, IntendedParent.id == history.intended_parent_id)
            .where(
                history.organization_id == org_id,
                history.intended_parent_id == entity_id,
                IntendedParent.organization_id == org_id,
            )
        )
    else:
        history = DonorStatusHistory
        queries.append(
            identity(
                "status",
                history.id,
                history.id,
                literal("status_changed"),
                history.effective_at,
            ).where(history.organization_id == org_id, history.donor_id == entity_id)
        )

    def legacy(source, model, event_type, occurred_at, *scope):
        # Existing feeds deduplicate matching IDs across these three detail keys.
        logged = exists(
            select(logged_sources.c.source_id)
            .where(
                logged_sources.c.activity_type == event_type,
                logged_sources.c.source_id == cast(model.id, String),
            )
            .correlate(model)
        )
        return identity(
            source,
            model.id,
            _synthetic_event_id_sql(model.id, event_type),
            literal(event_type),
            occurred_at,
        ).where(model.organization_id == org_id, *scope, ~logged)

    queries.extend(
        [
            legacy(
                "note",
                EntityNote,
                "note_added",
                EntityNote.created_at,
                EntityNote.entity_type == entity_type,
                EntityNote.entity_id == entity_id,
            ),
            legacy("task", Task, "task_created", Task.created_at, task_subject == entity_id),
            legacy(
                "task",
                Task,
                "task_completed",
                Task.completed_at,
                task_subject == entity_id,
                Task.completed_at.is_not(None),
            ),
            legacy(
                "attachment",
                Attachment,
                "attachment_added",
                Attachment.created_at,
                attachment_subject == entity_id,
            ),
            legacy(
                "attachment",
                Attachment,
                "attachment_deleted",
                Attachment.deleted_at,
                attachment_subject == entity_id,
                Attachment.deleted_at.is_not(None),
            ),
        ]
    )
    candidates = union_all(*queries).subquery()
    total = db.scalar(select(func.count()).select_from(candidates)) or 0
    if (page - 1) * per_page >= total:
        return [], total
    rows = (
        db.execute(
            select(candidates)
            .order_by(candidates.c.occurred_at.desc(), candidates.c.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        .mappings()
        .all()
    )
    return rows, total
