"""Note service - unified EntityNote for all entity types.

Per "No Backward Compatibility" rule, CaseNote has been removed.
All notes use the polymorphic EntityNote model with entity_type field.
"""

from uuid import UUID

import nh3
from sqlalchemy.orm import Session, joinedload

from app.db.enums import EntityType
from app.db.models import EntityNote
from app.schemas.note import NoteRead

# Allowed HTML tags for TipTap rich text
ALLOWED_TAGS = {"p", "br", "strong", "em", "ul", "ol", "li", "a", "blockquote", "h1", "h2", "h3", "code", "pre"}
ALLOWED_ATTRIBUTES = {"a": {"href", "target"}}


def sanitize_html(html: str) -> str:
    """Sanitize HTML to prevent XSS, allowing only safe rich text tags."""
    return nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)


# =============================================================================
# Unified EntityNote functions (for all entity types)
# =============================================================================

def create_note(
    db: Session,
    org_id: UUID,
    entity_type: EntityType | str,
    entity_id: UUID,
    author_id: UUID,
    content: str,
) -> EntityNote:
    """Create a note on any entity type."""
    clean_content = sanitize_html(content)
    
    # Convert enum to string if needed
    type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
    
    note = EntityNote(
        organization_id=org_id,
        entity_type=type_str,
        entity_id=entity_id,
        author_id=author_id,
        content=clean_content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    
    # Trigger workflow automation after successful commit
    from app.services.workflow_triggers import trigger_note_added
    trigger_note_added(db, note)
    
    return note


def list_notes(
    db: Session,
    org_id: UUID,
    entity_type: EntityType | str,
    entity_id: UUID,
) -> list[EntityNote]:
    """List notes for an entity, newest first."""
    type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
    
    return db.query(EntityNote).options(joinedload(EntityNote.author)).filter(
        EntityNote.organization_id == org_id,
        EntityNote.entity_type == type_str,
        EntityNote.entity_id == entity_id,
    ).order_by(EntityNote.created_at.desc()).all()


def list_notes_limited(
    db: Session,
    org_id: UUID,
    entity_type: EntityType | str,
    entity_id: UUID,
    limit: int,
) -> list[EntityNote]:
    """List most recent notes for an entity with a limit."""
    type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type

    return db.query(EntityNote).options(joinedload(EntityNote.author)).filter(
        EntityNote.organization_id == org_id,
        EntityNote.entity_type == type_str,
        EntityNote.entity_id == entity_id,
    ).order_by(EntityNote.created_at.desc()).limit(limit).all()


def get_note(db: Session, note_id: UUID, org_id: UUID) -> EntityNote | None:
    """Get a note by ID (org-scoped)."""
    return db.query(EntityNote).options(joinedload(EntityNote.author)).filter(
        EntityNote.id == note_id,
        EntityNote.organization_id == org_id,
    ).first()


def to_note_read(note: EntityNote) -> NoteRead:
    """Convert EntityNote model to NoteRead schema."""
    author_name = note.author.display_name if note.author else None
    return NoteRead(
        id=note.id,
        case_id=note.entity_id,
        author_id=note.author_id,
        author_name=author_name,
        body=note.content,
        created_at=note.created_at,
    )


def delete_note(db: Session, note: EntityNote) -> None:
    """Delete a note."""
    db.delete(note)
    db.commit()
