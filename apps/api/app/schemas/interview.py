"""Pydantic schemas for case interviews."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import nh3
from pydantic import BaseModel, Field, field_validator, model_validator

# Allowed HTML tags for transcript/notes (same as note_service)
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
    "div",
    "span",
    "hr",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "target"}, "div": {"class"}, "span": {"class"}}


def sanitize_html(html: str) -> str:
    """Sanitize HTML to prevent XSS."""
    return nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)


# ============================================================================
# Interview Request Schemas
# ============================================================================


class InterviewCreate(BaseModel):
    """Request to create an interview."""

    interview_type: Literal["phone", "video", "in_person"]
    conducted_at: datetime
    duration_minutes: int | None = Field(None, ge=1, le=480)
    transcript_json: dict[str, Any] | None = None  # TipTap JSON (preferred)
    transcript_html: str | None = Field(None, max_length=2_000_000)  # 2MB limit (legacy)
    status: Literal["draft", "completed"] = "completed"

    @field_validator("transcript_html")
    @classmethod
    def sanitize_transcript(cls, v: str | None) -> str | None:
        if v:
            return sanitize_html(v)
        return v


class InterviewUpdate(BaseModel):
    """Request to update an interview."""

    interview_type: Literal["phone", "video", "in_person"] | None = None
    conducted_at: datetime | None = None
    duration_minutes: int | None = Field(None, ge=1, le=480)
    transcript_json: dict[str, Any] | None = None  # TipTap JSON (preferred)
    transcript_html: str | None = Field(None, max_length=2_000_000)  # Legacy
    status: Literal["draft", "completed"] | None = None
    expected_version: int | None = None  # Optimistic concurrency control

    @field_validator("transcript_html")
    @classmethod
    def sanitize_transcript(cls, v: str | None) -> str | None:
        if v:
            return sanitize_html(v)
        return v


# ============================================================================
# Interview Note Request Schemas
# ============================================================================


class InterviewNoteCreate(BaseModel):
    """Request to create a note on an interview."""

    content: str = Field(..., min_length=1, max_length=50_000)
    transcript_version: int | None = Field(None, ge=1)  # Defaults to current

    # TipTap comment mark ID (preferred - stable anchor)
    comment_id: str | None = Field(None, max_length=36)

    # Legacy: text offset anchoring (for backward compatibility)
    anchor_start: int | None = Field(None, ge=0)
    anchor_end: int | None = Field(None, ge=0)
    anchor_text: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_anchor(self) -> "InterviewNoteCreate":
        """Validate anchor fields: comment_id OR offset anchoring (all-or-nothing)."""
        has_start = self.anchor_start is not None
        has_end = self.anchor_end is not None
        has_text = self.anchor_text is not None
        has_comment = self.comment_id is not None

        # If using legacy offset anchoring (start/end), all offset fields required
        if has_start or has_end:
            if not (has_start and has_end and has_text):
                raise ValueError("Offset anchor requires start, end, and text together")
            if self.anchor_end < self.anchor_start:
                raise ValueError("anchor_end must be >= anchor_start")

        # comment_id with anchor_text (no offsets) is valid - text is for display fallback
        # anchor_text alone without comment_id or offsets is also valid (informational only)
        return self

    @field_validator("content")
    @classmethod
    def sanitize_note(cls, v: str) -> str:
        return sanitize_html(v)


class InterviewNoteUpdate(BaseModel):
    """Request to update a note."""

    content: str = Field(..., min_length=1, max_length=50_000)

    @field_validator("content")
    @classmethod
    def sanitize_note(cls, v: str) -> str:
        return sanitize_html(v)


# ============================================================================
# Transcription Request Schema
# ============================================================================


class TranscriptionRequest(BaseModel):
    """Request to transcribe an audio/video attachment."""

    language: str = Field("en", pattern=r"^[a-z]{2}$")  # ISO 639-1
    prompt: str | None = Field(None, max_length=500)  # Context for Whisper


# ============================================================================
# Interview Response Schemas
# ============================================================================


class InterviewListItem(BaseModel):
    """Interview summary for list views."""

    id: UUID
    interview_type: str
    conducted_at: datetime
    conducted_by_user_id: UUID
    conducted_by_name: str
    duration_minutes: int | None
    status: str
    has_transcript: bool
    transcript_version: int
    notes_count: int
    attachments_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewRead(BaseModel):
    """Full interview detail response."""

    id: UUID
    case_id: UUID
    interview_type: str
    conducted_at: datetime
    conducted_by_user_id: UUID
    conducted_by_name: str
    duration_minutes: int | None

    # Transcript
    transcript_json: dict[str, Any] | None  # TipTap JSON (canonical)
    transcript_html: str | None  # Sanitized HTML for display
    transcript_version: int
    transcript_size_bytes: int
    is_transcript_offloaded: bool  # True if content in S3

    status: str

    # Counts
    notes_count: int
    attachments_count: int
    versions_count: int

    # Retention
    expires_at: datetime | None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Version Response Schemas
# ============================================================================


class InterviewVersionListItem(BaseModel):
    """Version summary for list views."""

    version: int
    author_user_id: UUID
    author_name: str
    source: str
    content_size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewVersionRead(BaseModel):
    """Full version content response."""

    version: int
    content_html: str | None
    content_text: str | None
    author_user_id: UUID
    author_name: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewVersionDiff(BaseModel):
    """Diff between two versions."""

    version_from: int
    version_to: int
    diff_html: str  # Unified diff with HTML markup
    additions: int
    deletions: int


# ============================================================================
# Note Response Schemas
# ============================================================================


class InterviewNoteRead(BaseModel):
    """Interview note response."""

    id: UUID
    content: str
    transcript_version: int

    # TipTap comment mark ID (stable anchor)
    comment_id: str | None

    # Original anchor (legacy: text offsets)
    anchor_start: int | None
    anchor_end: int | None
    anchor_text: str | None

    # Current position (recalculated)
    current_anchor_start: int | None
    current_anchor_end: int | None
    anchor_status: str | None  # 'valid', 'approximate', 'lost'

    author_user_id: UUID
    author_name: str
    is_own: bool

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Attachment Response Schemas
# ============================================================================


class InterviewAttachmentRead(BaseModel):
    """Interview attachment response."""

    id: UUID
    attachment_id: UUID
    filename: str
    content_type: str
    file_size: int
    is_audio_video: bool

    transcription_status: str | None
    transcription_error: str | None

    uploaded_by_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptionStatusRead(BaseModel):
    """Transcription job status response."""

    status: str  # 'pending', 'processing', 'completed', 'failed'
    progress: int | None  # 0-100 if available
    result: str | None  # Transcription text if completed
    error: str | None


# ============================================================================
# AI Summary Response Schemas
# ============================================================================


class InterviewSummaryResponse(BaseModel):
    """AI summary of a single interview."""

    interview_id: UUID
    summary: str
    key_points: list[str]
    concerns: list[str]
    sentiment: Literal["positive", "neutral", "mixed", "concerning"]
    follow_up_items: list[str]


class AllInterviewsSummaryResponse(BaseModel):
    """AI summary of all interviews for a case."""

    case_id: UUID
    interview_count: int
    overall_summary: str
    timeline: list[dict]  # [{date, type, key_point}]
    recurring_themes: list[str]
    candidate_strengths: list[str]
    areas_of_concern: list[str]
    recommended_actions: list[str]


# ============================================================================
# Export Response Schemas
# ============================================================================


class InterviewExportResponse(BaseModel):
    """Export download response."""

    download_url: str
    expires_at: datetime
    format: str
    file_size: int
