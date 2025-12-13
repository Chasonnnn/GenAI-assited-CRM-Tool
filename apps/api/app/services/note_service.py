"""Note service - business logic for case notes."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import CaseNote


def create_note(
    db: Session,
    case_id: UUID,
    org_id: UUID,
    author_id: UUID,
    body: str,
) -> CaseNote:
    """Create a new note on a case."""
    note = CaseNote(
        case_id=case_id,
        organization_id=org_id,
        author_id=author_id,
        body=body,
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
