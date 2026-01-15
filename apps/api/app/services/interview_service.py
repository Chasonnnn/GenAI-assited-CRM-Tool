"""Interview service - CRUD operations with versioning support."""

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Attachment,
    SurrogateInterview,
    InterviewAttachment,
    InterviewNote,
    InterviewTranscriptVersion,
    User,
)
from app.schemas.interview import InterviewCreate, InterviewUpdate
from app.services import tiptap_service
from app.types import JsonObject

if TYPE_CHECKING:
    from app.db.models import DataRetentionPolicy


# =============================================================================
# Constants
# =============================================================================

# Size threshold for S3 offloading (100KB JSON)
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


def _compute_transcript_size_bytes(transcript_json: JsonObject | None) -> int:
    """Compute size of TipTap JSON payload (bytes)."""
    if not transcript_json:
        return 0
    return len(
        json.dumps(transcript_json, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def _build_transcript_content(
    transcript_json: JsonObject | None,
) -> tuple[JsonObject | None, str | None, str | None, int]:
    """Sanitize and derive HTML/text/size from TipTap JSON."""
    if transcript_json is None:
        return None, None, None, 0

    sanitized = tiptap_service.sanitize_tiptap_json(transcript_json)
    if not sanitized:
        return None, None, None, 0

    transcript_html = tiptap_service.tiptap_to_html(sanitized)
    transcript_text = tiptap_service.tiptap_to_text(sanitized)
    transcript_size = _compute_transcript_size_bytes(sanitized)
    return sanitized, transcript_html, transcript_text, transcript_size


def _tiptap_doc_from_text(text: str) -> JsonObject:
    """Convert plain text into a minimal TipTap doc."""
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    content = [
        {"type": "paragraph", "content": [{"type": "text", "text": paragraph}]}
        for paragraph in paragraphs
    ]
    return {"type": "doc", "content": content}


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
    surrogate_id: UUID,
    user_id: UUID,
    data: InterviewCreate,
) -> SurrogateInterview:
    """
    Create a new interview.

    Validates case access and creates initial version if transcript provided.
    Supports TipTap JSON transcript input.
    """
    transcript_json: JsonObject | None = None
    transcript_html: str | None = None
    transcript_text: str | None = None
    transcript_size = 0

    if data.transcript_json is not None:
        transcript_json, transcript_html, transcript_text, transcript_size = (
            _build_transcript_content(data.transcript_json)
        )
        if transcript_json is None:
            raise ValueError("Invalid transcript JSON")

    transcript_hash = _compute_hash(transcript_text)

    # Check size limit
    if transcript_size > MAX_TRANSCRIPT_SIZE_BYTES:
        raise ValueError("Transcript exceeds 2MB limit")

    # Determine if offloading needed (will be handled by storage service)
    # For now, store inline - offloading will be handled separately
    storage_key = None
    has_transcript = bool(transcript_json or storage_key)

    # Get retention policy
    retention_policy = _get_retention_policy(db, org_id)
    expires_at = None
    if retention_policy and retention_policy.retention_days:
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(days=retention_policy.retention_days)

    interview = SurrogateInterview(
        surrogate_id=surrogate_id,
        organization_id=org_id,
        interview_type=data.interview_type,
        conducted_at=data.conducted_at,
        conducted_by_user_id=user_id,
        duration_minutes=data.duration_minutes,
        transcript_json=transcript_json,
        transcript_text=transcript_text,
        transcript_storage_key=storage_key,
        transcript_version=1 if has_transcript else 0,
        transcript_hash=transcript_hash,
        transcript_size_bytes=transcript_size,
        status=data.status,
        retention_policy_id=retention_policy.id if retention_policy else None,
        expires_at=expires_at,
    )
    db.add(interview)
    db.flush()

    # Create initial version if transcript provided
    if has_transcript:
        version = InterviewTranscriptVersion(
            interview_id=interview.id,
            organization_id=org_id,
            version=1,
            content_html=transcript_html,
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
) -> SurrogateInterview | None:
    """Get interview by ID with relationships loaded."""
    return db.scalar(
        select(SurrogateInterview)
        .options(
            joinedload(SurrogateInterview.conducted_by),
            joinedload(SurrogateInterview.surrogate),
        )
        .where(
            SurrogateInterview.id == interview_id,
            SurrogateInterview.organization_id == org_id,
        )
    )


def list_interviews(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
) -> list[SurrogateInterview]:
    """List all interviews for a case, newest first."""
    return list(
        db.scalars(
            select(SurrogateInterview)
            .options(joinedload(SurrogateInterview.conducted_by))
            .where(
                SurrogateInterview.surrogate_id == surrogate_id,
                SurrogateInterview.organization_id == org_id,
            )
            .order_by(SurrogateInterview.conducted_at.desc())
        ).all()
    )


def list_interviews_with_counts(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
) -> list[dict]:
    """List interviews with aggregated note/attachment counts (optimized for list views)."""
    rows = db.execute(
        select(
            SurrogateInterview.id,
            SurrogateInterview.interview_type,
            SurrogateInterview.conducted_at,
            SurrogateInterview.conducted_by_user_id,
            SurrogateInterview.duration_minutes,
            SurrogateInterview.status,
            SurrogateInterview.transcript_version,
            SurrogateInterview.transcript_storage_key,
            SurrogateInterview.created_at,
            User.display_name.label("conducted_by_name"),
            User.email.label("conducted_by_email"),
        )
        .select_from(SurrogateInterview)
        .outerjoin(User, User.id == SurrogateInterview.conducted_by_user_id)
        .where(
            SurrogateInterview.surrogate_id == surrogate_id,
            SurrogateInterview.organization_id == org_id,
        )
        .order_by(SurrogateInterview.conducted_at.desc())
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
    interview: SurrogateInterview,
    user_id: UUID,
    data: InterviewUpdate,
) -> SurrogateInterview:
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

    # Handle transcript update with versioning (TipTap JSON only)
    transcript_json: JsonObject | None = None
    transcript_html: str | None = None
    transcript_text: str | None = None
    transcript_size = 0

    if data.transcript_json is not None:
        transcript_json, transcript_html, transcript_text, transcript_size = (
            _build_transcript_content(data.transcript_json)
        )
        if transcript_json is None:
            raise ValueError("Invalid transcript JSON")

    if transcript_json is not None:
        new_hash = _compute_hash(transcript_text)
        new_size = transcript_size

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
                content_html=transcript_html,
                content_text=transcript_text,
                content_storage_key=None,  # Offloading handled separately
                content_hash=new_hash,
                content_size_bytes=new_size,
                author_user_id=user_id,
                source="manual",
            )
            db.add(version)

            # Update interview with new transcript
            interview.transcript_json = transcript_json
            interview.transcript_text = transcript_text
            interview.transcript_storage_key = None
            interview.transcript_version = new_version
            interview.transcript_hash = new_hash
            interview.transcript_size_bytes = new_size

    interview.updated_at = datetime.now(timezone.utc)
    db.flush()
    return interview


def delete_interview(
    db: Session,
    interview: SurrogateInterview,
) -> None:
    """Delete interview and all related data (cascade)."""
    db.delete(interview)
    db.flush()


async def update_transcript(
    db: Session,
    interview: SurrogateInterview,
    new_transcript_json: JsonObject,
    user_id: UUID,
    source: str = "manual",
) -> SurrogateInterview:
    """
    Update interview transcript with automatic versioning.

    Used by AI transcription and other services.
    Creates a new version if content changed.

    Args:
        db: Database session
        interview: Interview to update
        new_transcript_json: New TipTap JSON content
        user_id: User ID for version authorship
        source: Source of change ('manual', 'ai_transcription', 'restore')

    Returns:
        Updated interview
    """
    transcript_json, transcript_html, transcript_text, transcript_size = _build_transcript_content(
        new_transcript_json
    )
    if transcript_json is None:
        raise ValueError("Invalid transcript JSON")

    new_hash = _compute_hash(transcript_text)
    new_size = transcript_size

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
            content_html=transcript_html,
            content_text=transcript_text,
            content_storage_key=None,
            content_hash=new_hash,
            content_size_bytes=new_size,
            author_user_id=user_id,
            source=source,
        )
        db.add(version)

        # Update interview with new transcript
        interview.transcript_json = transcript_json
        interview.transcript_text = transcript_text
        interview.transcript_storage_key = None
        interview.transcript_version = new_version
        interview.transcript_hash = new_hash
        interview.transcript_size_bytes = new_size
        interview.updated_at = datetime.now(timezone.utc)

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
    interview: SurrogateInterview,
    target_version: int,
    user_id: UUID,
) -> SurrogateInterview:
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

    transcript_json: JsonObject | None = None
    if version.content_html:
        transcript_json = tiptap_service.html_to_tiptap(version.content_html)
    elif version.content_text:
        transcript_json = _tiptap_doc_from_text(version.content_text)
    if transcript_json is not None:
        transcript_json = tiptap_service.sanitize_tiptap_json(transcript_json)

    # Update interview
    interview.transcript_json = transcript_json
    interview.transcript_text = version.content_text
    interview.transcript_storage_key = version.content_storage_key
    interview.transcript_version = new_version
    interview.transcript_hash = new_hash
    interview.transcript_size_bytes = version.content_size_bytes
    interview.updated_at = datetime.now(timezone.utc)

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
# Count Helpers
# =============================================================================


def get_notes_count(db: Session, interview_id: UUID) -> int:
    """Get count of notes for an interview."""
    return (
        db.scalar(
            select(func.count())
            .select_from(InterviewNote)
            .where(InterviewNote.interview_id == interview_id)
        )
        or 0
    )


def get_attachments_count(db: Session, interview_id: UUID) -> int:
    """Get count of attachments for an interview."""
    return (
        db.scalar(
            select(func.count())
            .select_from(InterviewAttachment)
            .where(InterviewAttachment.interview_id == interview_id)
        )
        or 0
    )


def get_versions_count(db: Session, interview_id: UUID) -> int:
    """Get count of versions for an interview."""
    return (
        db.scalar(
            select(func.count())
            .select_from(InterviewTranscriptVersion)
            .where(InterviewTranscriptVersion.interview_id == interview_id)
        )
        or 0
    )


# =============================================================================
# Export Helpers
# =============================================================================


def build_interview_exports(
    db: Session,
    org_id: UUID,
    interviews: list[SurrogateInterview],
    current_user_id: UUID,
) -> dict[UUID, dict]:
    """Build export payloads for interviews with notes, attachments, and versions."""
    if not interviews:
        return {}

    from app.services import interview_attachment_service, interview_note_service

    interview_ids = [interview.id for interview in interviews]

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
    versions_counts = dict(
        db.execute(
            select(
                InterviewTranscriptVersion.interview_id,
                func.count(InterviewTranscriptVersion.id).label("versions_count"),
            )
            .where(
                InterviewTranscriptVersion.organization_id == org_id,
                InterviewTranscriptVersion.interview_id.in_(interview_ids),
            )
            .group_by(InterviewTranscriptVersion.interview_id)
        ).all()
    )

    notes_by_interview: dict[UUID, list[InterviewNote]] = defaultdict(list)
    notes = (
        db.scalars(
            select(InterviewNote)
            .options(
                joinedload(InterviewNote.author),
                joinedload(InterviewNote.resolved_by),
                joinedload(InterviewNote.replies).joinedload(InterviewNote.author),
                joinedload(InterviewNote.replies).joinedload(InterviewNote.resolved_by),
            )
            .where(
                InterviewNote.organization_id == org_id,
                InterviewNote.interview_id.in_(interview_ids),
                InterviewNote.parent_id.is_(None),
            )
            .order_by(InterviewNote.created_at.desc())
        )
        .unique()
        .all()
    )
    for note in notes:
        notes_by_interview[note.interview_id].append(note)

    attachments_by_interview: dict[UUID, list[InterviewAttachment]] = defaultdict(list)
    attachments = db.scalars(
        select(InterviewAttachment)
        .options(joinedload(InterviewAttachment.attachment).joinedload(Attachment.uploaded_by))
        .where(
            InterviewAttachment.organization_id == org_id,
            InterviewAttachment.interview_id.in_(interview_ids),
        )
        .order_by(InterviewAttachment.created_at.desc())
    ).all()
    for link in attachments:
        attachments_by_interview[link.interview_id].append(link)

    versions_by_interview: dict[UUID, list[InterviewTranscriptVersion]] = defaultdict(list)
    versions = db.scalars(
        select(InterviewTranscriptVersion)
        .options(joinedload(InterviewTranscriptVersion.author))
        .where(
            InterviewTranscriptVersion.organization_id == org_id,
            InterviewTranscriptVersion.interview_id.in_(interview_ids),
        )
        .order_by(InterviewTranscriptVersion.version.desc())
    ).all()
    for version in versions:
        versions_by_interview[version.interview_id].append(version)

    exports: dict[UUID, dict] = {}
    for interview in interviews:
        conducted_by_name = "Unknown"
        if interview.conducted_by:
            conducted_by_name = interview.conducted_by.display_name or interview.conducted_by.email

        interview_payload = {
            "id": interview.id,
            "surrogate_id": interview.surrogate_id,
            "interview_type": interview.interview_type,
            "conducted_at": interview.conducted_at,
            "conducted_by_user_id": interview.conducted_by_user_id,
            "conducted_by_name": conducted_by_name,
            "duration_minutes": interview.duration_minutes,
            "transcript_json": interview.transcript_json,
            "transcript_version": interview.transcript_version,
            "transcript_size_bytes": interview.transcript_size_bytes,
            "is_transcript_offloaded": interview.transcript_storage_key is not None,
            "status": interview.status,
            "notes_count": int(notes_counts.get(interview.id, 0)),
            "attachments_count": int(attachments_counts.get(interview.id, 0)),
            "versions_count": int(versions_counts.get(interview.id, 0)),
            "expires_at": interview.expires_at,
            "created_at": interview.created_at,
            "updated_at": interview.updated_at,
        }

        attachments_payload = [
            interview_attachment_service.to_attachment_read(link)
            for link in attachments_by_interview.get(interview.id, [])
            if link.attachment and not link.attachment.quarantined
        ]

        exports[interview.id] = {
            "interview": interview_payload,
            "notes": [
                interview_note_service.to_note_read(note, current_user_id)
                for note in notes_by_interview.get(interview.id, [])
            ],
            "attachments": attachments_payload,
            "versions": [
                to_version_list_item(version)
                for version in versions_by_interview.get(interview.id, [])
            ],
        }

    return exports


# =============================================================================
# Response Builders
# =============================================================================


def to_interview_list_item(db: Session, interview: SurrogateInterview) -> dict:
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
        "has_transcript": interview.transcript_version > 0
        or bool(interview.transcript_storage_key),
        "transcript_version": interview.transcript_version,
        "notes_count": get_notes_count(db, interview.id),
        "attachments_count": get_attachments_count(db, interview.id),
        "created_at": interview.created_at,
    }


def to_interview_read(db: Session, interview: SurrogateInterview) -> dict:
    """Convert interview to full response."""
    conducted_by_name = "Unknown"
    if interview.conducted_by:
        conducted_by_name = interview.conducted_by.display_name or interview.conducted_by.email

    return {
        "id": interview.id,
        "surrogate_id": interview.surrogate_id,
        "interview_type": interview.interview_type,
        "conducted_at": interview.conducted_at,
        "conducted_by_user_id": interview.conducted_by_user_id,
        "conducted_by_name": conducted_by_name,
        "duration_minutes": interview.duration_minutes,
        "transcript_json": interview.transcript_json,
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
