"""Note service - business logic for case notes."""

from uuid import UUID

import nh3
from sqlalchemy.orm import Session

from app.db.models import CaseNote

# Allowed HTML tags for TipTap rich text
ALLOWED_TAGS = {"p", "br", "strong", "em", "ul", "ol", "li", "a", "blockquote"}


def sanitize_html(html: str) -> str:
    """Sanitize HTML to prevent XSS, allowing only safe rich text tags."""
    return nh3.clean(html, tags=ALLOWED_TAGS)


def create_note(
    db: Session,
    case_id: UUID,
    org_id: UUID,
    author_id: UUID,
    body: str,
) -> CaseNote:
    """Create a new note on a case."""
    # Sanitize HTML to prevent XSS
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
