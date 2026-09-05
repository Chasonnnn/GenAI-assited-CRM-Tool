"""Note service - unified EntityNote for all entity types.

Per "No Backward Compatibility" rule, SurrogateNote has been removed.
All notes use the polymorphic EntityNote model with entity_type field.
"""

import logging
from uuid import UUID

import nh3
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, joinedload

from app.db.enums import EntityType
from app.db.models import Donor, EntityNote, IntendedParent, Surrogate
from app.schemas.note import NoteRead

logger = logging.getLogger(__name__)

# Allowed HTML tags for TipTap rich text
ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "a",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "code",
    "pre",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "target"}}


def sanitize_html(html: str) -> str:
    """Sanitize HTML to prevent XSS, allowing only safe rich text tags."""
    return nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)


# =============================================================================
# Unified EntityNote functions (for all entity types)
# =============================================================================


def _record_note_activity(
    db: Session,
    note: EntityNote,
    *,
    deleted: bool,
    actor_user_id: UUID | None,
) -> None:
    if note.entity_type == EntityType.SURROGATE.value:
        from app.services import activity_service

        if deleted:
            activity_service.log_note_deleted(
                db=db,
                surrogate_id=note.entity_id,
                organization_id=note.organization_id,
                actor_user_id=actor_user_id,
                note_id=note.id,
                content_preview=note.content[:200] if note.content else "",
            )
        else:
            activity_service.log_note_added(
                db=db,
                surrogate_id=note.entity_id,
                organization_id=note.organization_id,
                actor_user_id=actor_user_id,
                note_id=note.id,
                content=note.content,
            )
    elif note.entity_type in {EntityType.INTENDED_PARENT.value, EntityType.DONOR.value}:
        from app.services import entity_activity_service

        entity_activity_service.record_activity(
            db,
            org_id=note.organization_id,
            entity_type=note.entity_type,
            entity_id=note.entity_id,
            activity_type="note_deleted" if deleted else "note_added",
            actor_user_id=actor_user_id,
            details={"note_id": str(note.id)},
        )


def _dispatch_note_added(db: Session, note: EntityNote) -> None:
    """Isolate post-commit automation failures from the saved note."""
    from app.db.session import SessionLocal
    from app.services.workflow_triggers import trigger_note_added

    bind = db.get_bind()
    side_effect_db = (
        Session(bind=bind, autoflush=False, join_transaction_mode="create_savepoint")
        if isinstance(bind, Connection)
        else SessionLocal()
    )
    try:
        persisted_note = get_note(side_effect_db, note.id, note.organization_id)
        if persisted_note is None:
            raise ValueError("Saved note unavailable for workflow dispatch")
        trigger_note_added(side_effect_db, persisted_note)
    except Exception as exc:
        side_effect_db.rollback()
        logger.error(
            "Note workflow trigger failed",
            extra={"note_id": str(note.id), "error_class": type(exc).__name__},
        )
    finally:
        side_effect_db.close()


def create_note(
    db: Session,
    org_id: UUID,
    entity_type: EntityType | str,
    entity_id: UUID,
    author_id: UUID,
    content: str,
    *,
    commit: bool = True,
    emit_events: bool = True,
) -> EntityNote:
    """Persist a sanitized note and its activity in one transaction.

    Composed callers use commit=False and emit_events=False, then own both the
    transaction and any later workflow dispatch.
    """
    if emit_events and not commit:
        raise ValueError("Uncommitted notes cannot dispatch workflow events")
    type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
    subject_models = {
        EntityType.SURROGATE.value: Surrogate,
        EntityType.INTENDED_PARENT.value: IntendedParent,
        EntityType.DONOR.value: Donor,
    }
    subject_model = subject_models.get(type_str)
    if subject_model is None:
        raise ValueError("Unsupported note entity type")
    try:
        subject = (
            db.query(subject_model)
            .filter(subject_model.id == entity_id, subject_model.organization_id == org_id)
            .first()
        )
        if subject is None:
            raise ValueError("Note subject not found in organization")
        note = EntityNote(
            organization_id=org_id,
            entity_type=type_str,
            entity_id=entity_id,
            author_id=author_id,
            content=sanitize_html(content),
        )
        db.add(note)
        db.flush()
        _record_note_activity(db, note, deleted=False, actor_user_id=author_id)
        if isinstance(subject, IntendedParent):
            subject.last_activity = note.created_at
        if commit:
            db.commit()
            db.refresh(note)
        else:
            db.flush()
    except Exception:
        if commit:
            db.rollback()
        raise

    if emit_events:
        _dispatch_note_added(db, note)

    return note


def list_notes(
    db: Session,
    org_id: UUID,
    entity_type: EntityType | str,
    entity_id: UUID,
) -> list[EntityNote]:
    """List notes for an entity, newest first."""
    type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type

    return (
        db.query(EntityNote)
        .options(joinedload(EntityNote.author))
        .filter(
            EntityNote.organization_id == org_id,
            EntityNote.entity_type == type_str,
            EntityNote.entity_id == entity_id,
        )
        .order_by(EntityNote.created_at.desc())
        .all()
    )


def list_notes_limited(
    db: Session,
    org_id: UUID,
    entity_type: EntityType | str,
    entity_id: UUID,
    limit: int,
) -> list[EntityNote]:
    """List most recent notes for an entity with a limit."""
    type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type

    return (
        db.query(EntityNote)
        .options(joinedload(EntityNote.author))
        .filter(
            EntityNote.organization_id == org_id,
            EntityNote.entity_type == type_str,
            EntityNote.entity_id == entity_id,
        )
        .order_by(EntityNote.created_at.desc())
        .limit(limit)
        .all()
    )


def get_note(db: Session, note_id: UUID, org_id: UUID) -> EntityNote | None:
    """Get a note by ID (org-scoped)."""
    return (
        db.query(EntityNote)
        .options(joinedload(EntityNote.author))
        .filter(
            EntityNote.id == note_id,
            EntityNote.organization_id == org_id,
        )
        .first()
    )


def to_note_read(note: EntityNote) -> NoteRead:
    """Convert EntityNote model to NoteRead schema."""
    author_name = note.author.display_name if note.author else None
    return NoteRead(
        id=note.id,
        surrogate_id=note.entity_id,
        author_id=note.author_id,
        author_name=author_name,
        body=note.content,
        created_at=note.created_at,
    )


def delete_note(
    db: Session,
    note: EntityNote,
    *,
    actor_user_id: UUID | None = None,
    commit: bool = True,
) -> None:
    """Delete a note and retain its activity in the same transaction."""
    try:
        _record_note_activity(db, note, deleted=True, actor_user_id=actor_user_id)
        db.delete(note)
        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        if commit:
            db.rollback()
        raise
