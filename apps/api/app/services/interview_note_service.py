"""Interview note service - CRUD for interview notes with anchoring support."""

from datetime import datetime, timezone
from uuid import UUID

import nh3
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import SurrogateInterview, InterviewNote
from app.schemas.interview import InterviewNoteCreate, InterviewNoteUpdate

# Allowed HTML tags for note content (same as note_service)
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
    """Sanitize HTML to prevent XSS."""
    return nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)


# =============================================================================
# CRUD Operations
# =============================================================================


def create_note(
    db: Session,
    org_id: UUID,
    interview: SurrogateInterview,
    user_id: UUID,
    data: InterviewNoteCreate,
) -> InterviewNote:
    """
    Create a new note on an interview.

    Defaults transcript_version to current interview version.
    """
    if data.parent_id:
        if data.comment_id or data.anchor_text:
            raise ValueError("Replies cannot be anchored")
        parent_note = db.scalar(
            select(InterviewNote).where(
                InterviewNote.id == data.parent_id,
                InterviewNote.organization_id == org_id,
            )
        )
        if not parent_note or parent_note.interview_id != interview.id:
            raise ValueError("Parent note not found")
        if parent_note.parent_id is not None:
            raise ValueError("Replies must target a top-level note")
    # Determine transcript version
    transcript_version = data.transcript_version or interview.transcript_version

    # Anchor text is stored for comment display
    anchor_text = data.anchor_text

    # Sanitize content
    clean_content = sanitize_html(data.content)

    note = InterviewNote(
        interview_id=interview.id,
        organization_id=org_id,
        content=clean_content,
        transcript_version=transcript_version,
        comment_id=data.comment_id,  # TipTap comment mark ID
        anchor_text=anchor_text,
        author_user_id=user_id,
        parent_id=data.parent_id,  # Thread support
    )
    db.add(note)
    db.flush()
    return note


def get_note(
    db: Session,
    org_id: UUID,
    note_id: UUID,
) -> InterviewNote | None:
    """Get note by ID."""
    return db.scalar(
        select(InterviewNote)
        .options(joinedload(InterviewNote.author))
        .where(
            InterviewNote.id == note_id,
            InterviewNote.organization_id == org_id,
        )
    )


def list_notes(
    db: Session,
    org_id: UUID,
    interview_id: UUID,
) -> list[InterviewNote]:
    """
    List top-level notes for an interview with replies eagerly loaded.

    Returns only top-level notes (parent_id=None). Replies are nested
    under their parent via the `replies` relationship.
    """
    return list(
        db.scalars(
            select(InterviewNote)
            .options(
                joinedload(InterviewNote.author),
                joinedload(InterviewNote.resolved_by),
                joinedload(InterviewNote.replies).joinedload(InterviewNote.author),
                joinedload(InterviewNote.replies).joinedload(InterviewNote.resolved_by),
            )
            .where(
                InterviewNote.interview_id == interview_id,
                InterviewNote.organization_id == org_id,
                InterviewNote.parent_id.is_(None),  # Only top-level notes
            )
            .order_by(InterviewNote.created_at.desc())
        )
        .unique()
        .all()
    )


def update_note(
    db: Session,
    note: InterviewNote,
    data: InterviewNoteUpdate,
) -> InterviewNote:
    """
    Update note content.

    Note: Anchor cannot be changed after creation.
    """
    # Sanitize content
    note.content = sanitize_html(data.content)
    note.updated_at = datetime.now(timezone.utc)
    db.flush()
    return note


def delete_note(
    db: Session,
    note: InterviewNote,
) -> None:
    """Delete a note."""
    db.delete(note)
    db.flush()


def _load_thread_root(db: Session, note: InterviewNote) -> InterviewNote:
    """Load the top-level note with replies for thread-level operations."""
    root_id = note.parent_id or note.id
    root = db.scalar(
        select(InterviewNote)
        .options(
            joinedload(InterviewNote.author),
            joinedload(InterviewNote.resolved_by),
            joinedload(InterviewNote.replies).joinedload(InterviewNote.author),
            joinedload(InterviewNote.replies).joinedload(InterviewNote.resolved_by),
        )
        .where(InterviewNote.id == root_id)
    )
    return root or note


def resolve_note(
    db: Session,
    note: InterviewNote,
    user_id: UUID,
) -> InterviewNote:
    """Mark a note thread as resolved."""
    root = _load_thread_root(db, note)
    now = datetime.now(timezone.utc)
    for item in [root, *(root.replies or [])]:
        item.resolved_at = now
        item.resolved_by_user_id = user_id
        item.updated_at = now
    db.flush()
    return root


def unresolve_note(
    db: Session,
    note: InterviewNote,
) -> InterviewNote:
    """Re-open a resolved note thread."""
    root = _load_thread_root(db, note)
    now = datetime.now(timezone.utc)
    for item in [root, *(root.replies or [])]:
        item.resolved_at = None
        item.resolved_by_user_id = None
        item.updated_at = now
    db.flush()
    return root


# =============================================================================
# Response Builders
# =============================================================================


def to_note_read(note: InterviewNote, current_user_id: UUID) -> dict:
    """Convert note to response dict with nested replies."""
    author_name = "Unknown"
    if note.author:
        author_name = note.author.display_name or note.author.email

    resolved_by_name = None
    if note.resolved_by:
        resolved_by_name = note.resolved_by.display_name or note.resolved_by.email

    # Recursively convert replies
    replies = []
    if hasattr(note, "replies") and note.replies:
        replies = [to_note_read(reply, current_user_id) for reply in note.replies]

    return {
        "id": note.id,
        "content": note.content,
        "transcript_version": note.transcript_version,
        "comment_id": note.comment_id,  # TipTap comment mark ID
        "anchor_text": note.anchor_text,
        "parent_id": note.parent_id,
        "replies": replies,
        "resolved_at": note.resolved_at,
        "resolved_by_user_id": note.resolved_by_user_id,
        "resolved_by_name": resolved_by_name,
        "author_user_id": note.author_user_id,
        "author_name": author_name,
        "is_own": note.author_user_id == current_user_id,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }
