"""Interview service - CRUD operations with versioning support."""

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Case,
    CaseInterview,
    InterviewAttachment,
    InterviewNote,
    InterviewTranscriptVersion,
    User,
)
from app.schemas.interview import InterviewCreate, InterviewUpdate

if TYPE_CHECKING:
    from app.db.models import DataRetentionPolicy


# =============================================================================
# Constants
# =============================================================================

# Size threshold for S3 offloading (100KB HTML)
OFFLOAD_THRESHOLD_BYTES = 100 * 1024

# Maximum transcript size (2MB)
MAX_TRANSCRIPT_SIZE_BYTES = 2 * 1024 * 1024


# =============================================================================
# Helpers
# =============================================================================


def _compute_hash(text: str | None) -> str | None:
    """Compute SHA-256 hash for change detection."""
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_plaintext(html: str | None) -> str | None:
    """Extract plaintext from HTML for search/diff."""
    if not html:
        return None

    # Use a simple regex-based approach for now
    # In production, consider using lxml or beautifulsoup
    import re

    # Remove script/style tags and their contents
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.I)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Decode HTML entities
    import html as html_module

    text = html_module.unescape(text)
    return text


def _get_retention_policy(
    db: Session, org_id: UUID, entity_type: str = "interview"
) -> "DataRetentionPolicy | None":
    """Get retention policy for interviews."""
    from app.db.models import DataRetentionPolicy

    return db.scalar(
        select(DataRetentionPolicy).where(
            DataRetentionPolicy.organization_id == org_id,
            DataRetentionPolicy.entity_type == entity_type,
            DataRetentionPolicy.is_active == True,  # noqa: E712
        )
    )


# =============================================================================
# CRUD Operations
# =============================================================================


def create_interview(
    db: Session,
    org_id: UUID,
    case_id: UUID,
    user_id: UUID,
    data: InterviewCreate,
) -> CaseInterview:
    """
    Create a new interview.

    Validates case access and creates initial version if transcript provided.
    """
    # Extract plaintext for search
    transcript_text = _extract_plaintext(data.transcript_html)
    transcript_hash = _compute_hash(transcript_text)
    transcript_size = len(data.transcript_html.encode("utf-8")) if data.transcript_html else 0

    # Check size limit
    if transcript_size > MAX_TRANSCRIPT_SIZE_BYTES:
        raise ValueError("Transcript exceeds 2MB limit")

    # Determine if offloading needed (will be handled by storage service)
    # For now, store inline - offloading will be handled separately
    storage_key = None
    html_content = data.transcript_html

    # Get retention policy
    retention_policy = _get_retention_policy(db, org_id)
    expires_at = None
    if retention_policy and retention_policy.retention_days:
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=retention_policy.retention_days
        )

    interview = CaseInterview(
        case_id=case_id,
        organization_id=org_id,
        interview_type=data.interview_type,
        conducted_at=data.conducted_at,
        conducted_by_user_id=user_id,
        duration_minutes=data.duration_minutes,
        transcript_html=html_content,
        transcript_text=transcript_text,
        transcript_storage_key=storage_key,
        transcript_version=1 if data.transcript_html else 0,
        transcript_hash=transcript_hash,
        transcript_size_bytes=transcript_size,
        status=data.status,
        retention_policy_id=retention_policy.id if retention_policy else None,
        expires_at=expires_at,
    )
    db.add(interview)
    db.flush()

    # Create initial version if transcript provided
    if data.transcript_html:
        version = InterviewTranscriptVersion(
            interview_id=interview.id,
            organization_id=org_id,
            version=1,
            content_html=html_content,
            content_text=transcript_text,
            content_storage_key=storage_key,
            content_hash=transcript_hash,
            content_size_bytes=transcript_size,
            author_user_id=user_id,
            source="manual",
        )
        db.add(version)

    db.flush()
    return interview


def get_interview(
    db: Session,
    org_id: UUID,
    interview_id: UUID,
) -> CaseInterview | None:
    """Get interview by ID with relationships loaded."""
    return db.scalar(
        select(CaseInterview)
        .options(
            joinedload(CaseInterview.conducted_by),
            joinedload(CaseInterview.case),
        )
        .where(
            CaseInterview.id == interview_id,
            CaseInterview.organization_id == org_id,
        )
    )


def list_interviews(
    db: Session,
    org_id: UUID,
    case_id: UUID,
) -> list[CaseInterview]:
    """List all interviews for a case, newest first."""
    return list(
        db.scalars(
            select(CaseInterview)
            .options(joinedload(CaseInterview.conducted_by))
            .where(
                CaseInterview.case_id == case_id,
                CaseInterview.organization_id == org_id,
            )
            .order_by(CaseInterview.conducted_at.desc())
        ).all()
    )


def list_interviews_with_counts(
    db: Session,
    org_id: UUID,
    case_id: UUID,
) -> list[dict]:
    """List interviews with aggregated note/attachment counts (optimized for list views)."""
    rows = db.execute(
        select(
            CaseInterview.id,
            CaseInterview.interview_type,
            CaseInterview.conducted_at,
            CaseInterview.conducted_by_user_id,
            CaseInterview.duration_minutes,
            CaseInterview.status,
            CaseInterview.transcript_version,
            CaseInterview.transcript_storage_key,
            CaseInterview.created_at,
            User.display_name.label("conducted_by_name"),
            User.email.label("conducted_by_email"),
        )
        .select_from(CaseInterview)
        .outerjoin(User, User.id == CaseInterview.conducted_by_user_id)
        .where(
            CaseInterview.case_id == case_id,
            CaseInterview.organization_id == org_id,
        )
        .order_by(CaseInterview.conducted_at.desc())
    ).all()

    if not rows:
        return []

    interview_ids = [row.id for row in rows]

    notes_counts = dict(
        db.execute(
            select(
                InterviewNote.interview_id,
                func.count(InterviewNote.id).label("notes_count"),
            )
            .where(
                InterviewNote.organization_id == org_id,
                InterviewNote.interview_id.in_(interview_ids),
            )
            .group_by(InterviewNote.interview_id)
        ).all()
    )

    attachments_counts = dict(
        db.execute(
            select(
                InterviewAttachment.interview_id,
                func.count(InterviewAttachment.id).label("attachments_count"),
            )
            .where(
                InterviewAttachment.organization_id == org_id,
                InterviewAttachment.interview_id.in_(interview_ids),
            )
            .group_by(InterviewAttachment.interview_id)
        ).all()
    )

    items: list[dict] = []
    for row in rows:
        conducted_by_name = row.conducted_by_name or row.conducted_by_email or "Unknown"
        has_transcript = row.transcript_version > 0 or bool(row.transcript_storage_key)
        items.append(
            {
                "id": row.id,
                "interview_type": row.interview_type,
                "conducted_at": row.conducted_at,
                "conducted_by_user_id": row.conducted_by_user_id,
                "conducted_by_name": conducted_by_name,
                "duration_minutes": row.duration_minutes,
                "status": row.status,
                "has_transcript": has_transcript,
                "transcript_version": row.transcript_version,
                "notes_count": int(notes_counts.get(row.id, 0)),
                "attachments_count": int(attachments_counts.get(row.id, 0)),
                "created_at": row.created_at,
            }
        )

    return items


def update_interview(
    db: Session,
    org_id: UUID,
    interview: CaseInterview,
    user_id: UUID,
    data: InterviewUpdate,
) -> CaseInterview:
    """
    Update interview with automatic versioning.

    Supports optimistic concurrency via expected_version.
    Only creates new version if transcript content actually changed.
    """
    # Optimistic concurrency check
    if data.expected_version is not None:
        if interview.transcript_version != data.expected_version:
            raise ValueError(
                f"Version conflict: expected {data.expected_version}, "
                f"current is {interview.transcript_version}"
            )

    # Update basic fields
    if data.interview_type is not None:
        interview.interview_type = data.interview_type
    if data.conducted_at is not None:
        interview.conducted_at = data.conducted_at
    if data.duration_minutes is not None:
        interview.duration_minutes = data.duration_minutes
    if data.status is not None:
        interview.status = data.status

    # Handle transcript update with versioning
    if data.transcript_html is not None:
        new_text = _extract_plaintext(data.transcript_html)
        new_hash = _compute_hash(new_text)
        new_size = len(data.transcript_html.encode("utf-8"))

        # Check size limit
        if new_size > MAX_TRANSCRIPT_SIZE_BYTES:
            raise ValueError("Transcript exceeds 2MB limit")

        # No-change guard: only create version if content changed
        if new_hash != interview.transcript_hash:
            new_version = interview.transcript_version + 1

            # Create version record
            version = InterviewTranscriptVersion(
                interview_id=interview.id,
                organization_id=org_id,
                version=new_version,
                content_html=data.transcript_html,
                content_text=new_text,
                content_storage_key=None,  # Offloading handled separately
                content_hash=new_hash,
                content_size_bytes=new_size,
                author_user_id=user_id,
                source="manual",
            )
            db.add(version)

            # Update interview with new transcript
            interview.transcript_html = data.transcript_html
            interview.transcript_text = new_text
            interview.transcript_storage_key = None
            interview.transcript_version = new_version
            interview.transcript_hash = new_hash
            interview.transcript_size_bytes = new_size

            # Recalculate note anchors after version change
            _recalculate_note_anchors(db, interview)

    interview.updated_at = datetime.now(timezone.utc)
    db.flush()
    return interview


def delete_interview(
    db: Session,
    interview: CaseInterview,
) -> None:
    """Delete interview and all related data (cascade)."""
    db.delete(interview)
    db.flush()


async def update_transcript(
    db: Session,
    interview: CaseInterview,
    new_html: str,
    user_id: UUID,
    source: str = "manual",
) -> CaseInterview:
    """
    Update interview transcript with automatic versioning.

    Used by AI transcription and other services.
    Creates a new version if content changed.

    Args:
        db: Database session
        interview: Interview to update
        new_html: New HTML content
        user_id: User ID for version authorship
        source: Source of change ('manual', 'ai_transcription', 'restore')

    Returns:
        Updated interview
    """
    new_text = _extract_plaintext(new_html)
    new_hash = _compute_hash(new_text)
    new_size = len(new_html.encode("utf-8"))

    # Check size limit
    if new_size > MAX_TRANSCRIPT_SIZE_BYTES:
        raise ValueError("Transcript exceeds 2MB limit")

    # No-change guard: only create version if content changed
    if new_hash != interview.transcript_hash:
        new_version = interview.transcript_version + 1

        # Create version record
        version = InterviewTranscriptVersion(
            interview_id=interview.id,
            organization_id=interview.organization_id,
            version=new_version,
            content_html=new_html,
            content_text=new_text,
            content_storage_key=None,
            content_hash=new_hash,
            content_size_bytes=new_size,
            author_user_id=user_id,
            source=source,
        )
        db.add(version)

        # Update interview with new transcript
        interview.transcript_html = new_html
        interview.transcript_text = new_text
        interview.transcript_storage_key = None
        interview.transcript_version = new_version
        interview.transcript_hash = new_hash
        interview.transcript_size_bytes = new_size
        interview.updated_at = datetime.now(timezone.utc)

        # Recalculate note anchors after version change
        _recalculate_note_anchors(db, interview)

    db.flush()
    return interview


# =============================================================================
# Version Operations
# =============================================================================


def list_versions(
    db: Session,
    org_id: UUID,
    interview_id: UUID,
) -> list[InterviewTranscriptVersion]:
    """List all versions for an interview, newest first."""
    return list(
        db.scalars(
            select(InterviewTranscriptVersion)
            .options(joinedload(InterviewTranscriptVersion.author))
            .where(
                InterviewTranscriptVersion.interview_id == interview_id,
                InterviewTranscriptVersion.organization_id == org_id,
            )
            .order_by(InterviewTranscriptVersion.version.desc())
        ).all()
    )


def get_version(
    db: Session,
    org_id: UUID,
    interview_id: UUID,
    version: int,
) -> InterviewTranscriptVersion | None:
    """Get specific version content."""
    return db.scalar(
        select(InterviewTranscriptVersion)
        .options(joinedload(InterviewTranscriptVersion.author))
        .where(
            InterviewTranscriptVersion.interview_id == interview_id,
            InterviewTranscriptVersion.organization_id == org_id,
            InterviewTranscriptVersion.version == version,
        )
    )


def restore_version(
    db: Session,
    org_id: UUID,
    interview: CaseInterview,
    target_version: int,
    user_id: UUID,
) -> CaseInterview:
    """
    Restore interview transcript to a previous version.

    Creates a new version with source='restore'.
    """
    # Get target version
    version = get_version(db, org_id, interview.id, target_version)
    if not version:
        raise ValueError(f"Version {target_version} not found")

    # Create new version as restore
    new_version = interview.transcript_version + 1
    new_hash = version.content_hash

    restore_version_record = InterviewTranscriptVersion(
        interview_id=interview.id,
        organization_id=org_id,
        version=new_version,
        content_html=version.content_html,
        content_text=version.content_text,
        content_storage_key=version.content_storage_key,
        content_hash=new_hash,
        content_size_bytes=version.content_size_bytes,
        author_user_id=user_id,
        source="restore",
    )
    db.add(restore_version_record)

    # Update interview
    interview.transcript_html = version.content_html
    interview.transcript_text = version.content_text
    interview.transcript_storage_key = version.content_storage_key
    interview.transcript_version = new_version
    interview.transcript_hash = new_hash
    interview.transcript_size_bytes = version.content_size_bytes
    interview.updated_at = datetime.now(timezone.utc)

    # Recalculate note anchors
    _recalculate_note_anchors(db, interview)

    db.flush()
    return interview


def get_version_diff(
    db: Session,
    org_id: UUID,
    interview_id: UUID,
    version_from: int,
    version_to: int,
) -> dict:
    """
    Generate diff between two versions.

    Returns HTML-formatted unified diff.
    """
    v_from = get_version(db, org_id, interview_id, version_from)
    v_to = get_version(db, org_id, interview_id, version_to)

    if not v_from or not v_to:
        raise ValueError("One or both versions not found")

    import difflib

    # Generate unified diff on plaintext
    from_lines = (v_from.content_text or "").splitlines(keepends=True)
    to_lines = (v_to.content_text or "").splitlines(keepends=True)

    diff = difflib.unified_diff(
        from_lines,
        to_lines,
        fromfile=f"Version {version_from}",
        tofile=f"Version {version_to}",
        lineterm="",
    )

    # Convert to HTML
    diff_lines = list(diff)
    additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

    # Format diff as HTML
    import html

    diff_html_lines = []
    for line in diff_lines:
        escaped = html.escape(line)
        if line.startswith("+++") or line.startswith("---"):
            diff_html_lines.append(f'<div class="diff-header">{escaped}</div>')
        elif line.startswith("@@"):
            diff_html_lines.append(f'<div class="diff-range">{escaped}</div>')
        elif line.startswith("+"):
            diff_html_lines.append(f'<div class="diff-add">{escaped}</div>')
        elif line.startswith("-"):
            diff_html_lines.append(f'<div class="diff-del">{escaped}</div>')
        else:
            diff_html_lines.append(f"<div>{escaped}</div>")

    return {
        "version_from": version_from,
        "version_to": version_to,
        "diff_html": "\n".join(diff_html_lines),
        "additions": additions,
        "deletions": deletions,
    }


# =============================================================================
# Anchor Recalculation (simplified - full logic in anchor_service.py)
# =============================================================================


def _recalculate_note_anchors(db: Session, interview: CaseInterview) -> None:
    """
    Recalculate note anchor positions after transcript change.

    Called internally after transcript updates or restores.
    """
    from app.services.anchor_service import recalculate_anchor_positions

    current_text = interview.transcript_text or ""
    current_version = interview.transcript_version

    # Get all notes with anchors
    notes = db.scalars(
        select(InterviewNote).where(
            InterviewNote.interview_id == interview.id,
            InterviewNote.anchor_text.isnot(None),
        )
    ).all()

    for note in notes:
        if note.transcript_version == current_version:
            # Note created on current version, anchor is valid
            note.current_anchor_start = note.anchor_start
            note.current_anchor_end = note.anchor_end
            note.anchor_status = "valid"
        else:
            # Get original version text
            original_version = db.scalar(
                select(InterviewTranscriptVersion).where(
                    InterviewTranscriptVersion.interview_id == interview.id,
                    InterviewTranscriptVersion.version == note.transcript_version,
                )
            )

            if original_version:
                original_text = original_version.content_text or ""
                new_start, new_end, status = recalculate_anchor_positions(
                    note=note,
                    original_text=original_text,
                    current_text=current_text,
                )
                note.current_anchor_start = new_start
                note.current_anchor_end = new_end
                note.anchor_status = status
            else:
                note.anchor_status = "lost"

        db.add(note)


# =============================================================================
# Count Helpers
# =============================================================================


def get_notes_count(db: Session, interview_id: UUID) -> int:
    """Get count of notes for an interview."""
    return db.scalar(
        select(func.count())
        .select_from(InterviewNote)
        .where(InterviewNote.interview_id == interview_id)
    ) or 0


def get_attachments_count(db: Session, interview_id: UUID) -> int:
    """Get count of attachments for an interview."""
    return db.scalar(
        select(func.count())
        .select_from(InterviewAttachment)
        .where(InterviewAttachment.interview_id == interview_id)
    ) or 0


def get_versions_count(db: Session, interview_id: UUID) -> int:
    """Get count of versions for an interview."""
    return db.scalar(
        select(func.count())
        .select_from(InterviewTranscriptVersion)
        .where(InterviewTranscriptVersion.interview_id == interview_id)
    ) or 0


# =============================================================================
# Response Builders
# =============================================================================


def to_interview_list_item(
    db: Session, interview: CaseInterview
) -> dict:
    """Convert interview to list item response."""
    conducted_by_name = "Unknown"
    if interview.conducted_by:
        conducted_by_name = interview.conducted_by.display_name or interview.conducted_by.email

    return {
        "id": interview.id,
        "interview_type": interview.interview_type,
        "conducted_at": interview.conducted_at,
        "conducted_by_user_id": interview.conducted_by_user_id,
        "conducted_by_name": conducted_by_name,
        "duration_minutes": interview.duration_minutes,
        "status": interview.status,
        "has_transcript": bool(interview.transcript_html or interview.transcript_storage_key),
        "transcript_version": interview.transcript_version,
        "notes_count": get_notes_count(db, interview.id),
        "attachments_count": get_attachments_count(db, interview.id),
        "created_at": interview.created_at,
    }


def to_interview_read(
    db: Session, interview: CaseInterview
) -> dict:
    """Convert interview to full response."""
    conducted_by_name = "Unknown"
    if interview.conducted_by:
        conducted_by_name = interview.conducted_by.display_name or interview.conducted_by.email

    return {
        "id": interview.id,
        "case_id": interview.case_id,
        "interview_type": interview.interview_type,
        "conducted_at": interview.conducted_at,
        "conducted_by_user_id": interview.conducted_by_user_id,
        "conducted_by_name": conducted_by_name,
        "duration_minutes": interview.duration_minutes,
        "transcript_html": interview.transcript_html,
        "transcript_version": interview.transcript_version,
        "transcript_size_bytes": interview.transcript_size_bytes,
        "is_transcript_offloaded": interview.transcript_storage_key is not None,
        "status": interview.status,
        "notes_count": get_notes_count(db, interview.id),
        "attachments_count": get_attachments_count(db, interview.id),
        "versions_count": get_versions_count(db, interview.id),
        "expires_at": interview.expires_at,
        "created_at": interview.created_at,
        "updated_at": interview.updated_at,
    }


def to_version_list_item(version: InterviewTranscriptVersion) -> dict:
    """Convert version to list item response."""
    author_name = "Unknown"
    if version.author:
        author_name = version.author.display_name or version.author.email

    return {
        "version": version.version,
        "author_user_id": version.author_user_id,
        "author_name": author_name,
        "source": version.source,
        "content_size_bytes": version.content_size_bytes,
        "created_at": version.created_at,
    }


def to_version_read(version: InterviewTranscriptVersion) -> dict:
    """Convert version to full response."""
    author_name = "Unknown"
    if version.author:
        author_name = version.author.display_name or version.author.email

    return {
        "version": version.version,
        "content_html": version.content_html,
        "content_text": version.content_text,
        "author_user_id": version.author_user_id,
        "author_name": author_name,
        "source": version.source,
        "created_at": version.created_at,
    }
