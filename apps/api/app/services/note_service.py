"""Note service - business logic for notes (case notes + polymorphic entity notes)."""

from uuid import UUID

import nh3
from sqlalchemy.orm import Session

from app.db.enums import EntityType
from app.db.models import CaseNote, EntityNote

# Allowed HTML tags for TipTap rich text
ALLOWED_TAGS = {"p", "br", "strong", "em", "ul", "ol", "li", "a", "blockquote", "h1", "h2", "h3", "code", "pre"}
ALLOWED_ATTRIBUTES = {"a": {"href", "target"}}


def sanitize_html(html: str) -> str:
    """Sanitize HTML to prevent XSS, allowing only safe rich text tags."""
    return nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)


# =============================================================================
# CaseNote functions (backward compatible)
# =============================================================================

def create_note(
    db: Session,
    case_id: UUID,
    org_id: UUID,
    author_id: UUID,
    body: str,
) -> CaseNote:
    """Create a new note on a case."""
    clean_body = sanitize_html(body)
    
    note = CaseNote(
        case_id=case_id,
        organization_id=org_id,
        author_id=author_id,
        body=clean_body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_notes(db: Session, case_id: UUID, org_id: UUID) -> list[CaseNote]:
    """List notes for a case (org-scoped), newest first."""
    return db.query(CaseNote).filter(
        CaseNote.case_id == case_id,
        CaseNote.organization_id == org_id,
    ).order_by(CaseNote.created_at.desc()).all()


def get_note(db: Session, note_id: UUID, org_id: UUID) -> CaseNote | None:
    """Get a note by ID (org-scoped)."""
    return db.query(CaseNote).filter(
        CaseNote.id == note_id,
        CaseNote.organization_id == org_id,
    ).first()


def delete_note(db: Session, note: CaseNote) -> None:
    """Delete a note."""
    db.delete(note)
    db.commit()


# =============================================================================
# Polymorphic EntityNote functions (for intended_parents and future entities)
# =============================================================================

def create_entity_note(
    db: Session,
    org_id: UUID,
    entity_type: EntityType,
    entity_id: UUID,
    author_id: UUID,
    content: str,
) -> EntityNote:
    """Create a note on any entity type."""
    clean_content = sanitize_html(content)
    
    note = EntityNote(
        organization_id=org_id,
        entity_type=entity_type.value,
        entity_id=entity_id,
        author_id=author_id,
        content=clean_content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_entity_notes(
    db: Session,
    org_id: UUID,
    entity_type: EntityType,
    entity_id: UUID,
) -> list[EntityNote]:
    """List notes for an entity, newest first."""
    return db.query(EntityNote).filter(
        EntityNote.organization_id == org_id,
        EntityNote.entity_type == entity_type.value,
        EntityNote.entity_id == entity_id,
    ).order_by(EntityNote.created_at.desc()).all()


def get_entity_note(db: Session, note_id: UUID, org_id: UUID) -> EntityNote | None:
    """Get an entity note by ID (org-scoped)."""
    return db.query(EntityNote).filter(
        EntityNote.id == note_id,
        EntityNote.organization_id == org_id,
    ).first()


def delete_entity_note(db: Session, note: EntityNote) -> None:
    """Delete an entity note."""
    db.delete(note)
    db.commit()
