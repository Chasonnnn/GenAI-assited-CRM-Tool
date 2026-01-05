# Interview Tab - Implementation Workplan

> **Version:** 1.1
> **Last Updated:** January 4, 2026
> **Status:** Planning

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements Summary](#requirements-summary)
3. [Database Design](#database-design)
4. [API Design](#api-design)
5. [Frontend Design](#frontend-design)
6. [AI Integration](#ai-integration)
7. [Security & Compliance](#security--compliance)
8. [Implementation Phases](#implementation-phases)
9. [File Checklist](#file-checklist)
10. [Testing Strategy](#testing-strategy)

---

## Overview

Add an "Interview" tab to the case details page for documenting phone calls, video interviews, and in-person meetings with candidates.

### Key Capabilities

- **Multi-interview support** — Each case can have multiple interviews
- **Split-pane layout** — Transcript left, notes right (collapsible); mobile stacks
- **Versioned transcripts** — Full history with diff/compare and restore
- **Shared notes** — Multiple users can add notes; optional anchoring to transcript selections
- **File attachments** — Recordings, PDFs, images via existing attachment system
- **AI features** — Transcription from audio/video, summarize single or all interviews
- **Compliance** — Reuse existing retention policies, export support, audit logging

---

## Requirements Summary

| Requirement | Details |
|-------------|---------|
| **Layout** | Split view (transcript/notes), notes toggle show/hide, mobile stacks vertically |
| **Transcript input** | Rich text, plain text, or paste; upload audio/video with AI transcription option |
| **Versioning** | Auto-version on save (with no-change guard); history list with diff/compare; restore to any version |
| **Notes** | Shared across users with case access; anchored notes tied to specific transcript version; unanchored defaults to current version |
| **Files** | Reuse existing attachment system; link to interviews |
| **AI** | Whisper transcription; summarize single interview or all interviews |
| **Permissions** | Assignee and case_manager+ can create/edit; case must be user-owned (not in queue); delete requires admin+ |
| **Large content** | Transcripts > 100KB offloaded to S3 (HTML only); 2MB hard limit |
| **Retention** | Reuse existing compliance retention policies; export to PDF/JSON |

---

## Database Design

### New Tables

#### `case_interviews` — Main interview record

```sql
CREATE TABLE case_interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Metadata
    interview_type VARCHAR(20) NOT NULL,  -- 'phone', 'video', 'in_person'
    conducted_at TIMESTAMPTZ NOT NULL,
    conducted_by_user_id UUID NOT NULL REFERENCES users(id),
    duration_minutes INTEGER,

    -- Current transcript (denormalized for quick reads)
    transcript_html TEXT,                  -- Sanitized HTML (NULL if offloaded)
    transcript_text TEXT,                  -- Plaintext for search/diff (always stored)
    transcript_storage_key VARCHAR(500),   -- S3 key if HTML is offloaded (> 100KB)
    transcript_version INTEGER NOT NULL DEFAULT 1,
    transcript_hash VARCHAR(64),           -- SHA256 for no-change guard
    transcript_size_bytes INTEGER DEFAULT 0,

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'completed',  -- 'draft', 'completed'

    -- Retention
    retention_policy_id UUID REFERENCES data_retention_policies(id),
    expires_at TIMESTAMPTZ,                -- Set by retention policy

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

);

-- Full-text search
ALTER TABLE case_interviews ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (to_tsvector('english', COALESCE(transcript_text, ''))) STORED;
CREATE INDEX case_interviews_search_idx ON case_interviews USING GIN (search_vector);
CREATE INDEX case_interviews_case_id_idx ON case_interviews (case_id);
CREATE INDEX case_interviews_org_conducted_idx ON case_interviews (organization_id, conducted_at DESC);
```

#### `interview_transcript_versions` — Version history

```sql
CREATE TABLE interview_transcript_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES case_interviews(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    version INTEGER NOT NULL,

    -- Content
    content_html TEXT,                     -- NULL if offloaded
    content_text TEXT,                     -- Always stored for diff/search
    content_storage_key VARCHAR(500),      -- S3 key if HTML is offloaded
    content_hash VARCHAR(64) NOT NULL,
    content_size_bytes INTEGER NOT NULL,

    -- Metadata
    author_user_id UUID NOT NULL REFERENCES users(id),
    source VARCHAR(30) NOT NULL,           -- 'manual', 'ai_transcription', 'restore'

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (interview_id, version)
);

CREATE INDEX interview_versions_interview_idx ON interview_transcript_versions (interview_id, version DESC);
CREATE INDEX interview_versions_org_idx ON interview_transcript_versions (organization_id);
```

#### `interview_notes` — Shared notes with version-anchoring

```sql
CREATE TABLE interview_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES case_interviews(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Content
    content TEXT NOT NULL,                 -- Sanitized HTML

    -- Anchor to specific version (prevents drift)
    transcript_version INTEGER NOT NULL,
    anchor_start INTEGER,                  -- Character offset in transcript_text
    anchor_end INTEGER,
    anchor_text VARCHAR(500),              -- Snapshot of selected text

    -- Recalculated anchor for current version (nullable)
    current_anchor_start INTEGER,
    current_anchor_end INTEGER,
    anchor_status VARCHAR(20),             -- 'valid', 'approximate', 'lost'

    -- Metadata
    author_user_id UUID NOT NULL REFERENCES users(id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Constraints
    CONSTRAINT anchor_range_valid CHECK (anchor_end IS NULL OR anchor_end >= anchor_start),
    CONSTRAINT anchor_complete CHECK (
        (anchor_start IS NULL AND anchor_end IS NULL AND anchor_text IS NULL) OR
        (anchor_start IS NOT NULL AND anchor_end IS NOT NULL AND anchor_text IS NOT NULL)
    )
);

CREATE INDEX interview_notes_interview_idx ON interview_notes (interview_id);
CREATE INDEX interview_notes_org_idx ON interview_notes (organization_id);
```

#### `interview_attachments` — Link table to existing attachments

```sql
CREATE TABLE interview_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES case_interviews(id) ON DELETE CASCADE,
    attachment_id UUID NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- AI transcription (for audio/video only)
    transcription_status VARCHAR(20),      -- 'pending', 'processing', 'completed', 'failed'
    transcription_job_id VARCHAR(100),
    transcription_error TEXT,
    transcription_completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (interview_id, attachment_id)
);
```


### SQLAlchemy Models

```python
# app/db/models.py

class CaseInterview(Base):
    __tablename__ = "case_interviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)

    # Metadata
    interview_type: Mapped[str] = mapped_column(String(20))
    conducted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    conducted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    duration_minutes: Mapped[int | None]

    # Current transcript
    transcript_html: Mapped[str | None] = mapped_column(Text)
    transcript_text: Mapped[str | None] = mapped_column(Text)
    transcript_storage_key: Mapped[str | None] = mapped_column(String(500))
    transcript_version: Mapped[int] = mapped_column(default=1)
    transcript_hash: Mapped[str | None] = mapped_column(String(64))
    transcript_size_bytes: Mapped[int] = mapped_column(default=0)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="completed")

    # Retention
    retention_policy_id: Mapped[UUID | None] = mapped_column(ForeignKey("data_retention_policies.id"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    case: Mapped["Case"] = relationship(back_populates="interviews")
    conducted_by: Mapped["User"] = relationship()
    versions: Mapped[list["InterviewTranscriptVersion"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    notes: Mapped[list["InterviewNote"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    interview_attachments: Mapped[list["InterviewAttachment"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    retention_policy: Mapped["DataRetentionPolicy | None"] = relationship()


class InterviewTranscriptVersion(Base):
    __tablename__ = "interview_transcript_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    interview_id: Mapped[UUID] = mapped_column(ForeignKey("case_interviews.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    version: Mapped[int]

    content_html: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_storage_key: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64))
    content_size_bytes: Mapped[int]

    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(30))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    interview: Mapped["CaseInterview"] = relationship(back_populates="versions")
    author: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("interview_id", "version"),
    )


class InterviewNote(Base):
    __tablename__ = "interview_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    interview_id: Mapped[UUID] = mapped_column(ForeignKey("case_interviews.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)

    content: Mapped[str] = mapped_column(Text)

    # Version-specific anchor
    transcript_version: Mapped[int]
    anchor_start: Mapped[int | None]
    anchor_end: Mapped[int | None]
    anchor_text: Mapped[str | None] = mapped_column(String(500))

    # Recalculated anchor for current version
    current_anchor_start: Mapped[int | None]
    current_anchor_end: Mapped[int | None]
    anchor_status: Mapped[str | None] = mapped_column(String(20))  # 'valid', 'approximate', 'lost'

    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    interview: Mapped["CaseInterview"] = relationship(back_populates="notes")
    author: Mapped["User"] = relationship()

    __table_args__ = (
        CheckConstraint("anchor_end IS NULL OR anchor_end >= anchor_start", name="anchor_range_valid"),
    )


class InterviewAttachment(Base):
    __tablename__ = "interview_attachments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    interview_id: Mapped[UUID] = mapped_column(ForeignKey("case_interviews.id", ondelete="CASCADE"), index=True)
    attachment_id: Mapped[UUID] = mapped_column(ForeignKey("attachments.id", ondelete="CASCADE"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))

    transcription_status: Mapped[str | None] = mapped_column(String(20))
    transcription_job_id: Mapped[str | None] = mapped_column(String(100))
    transcription_error: Mapped[str | None] = mapped_column(Text)
    transcription_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    interview: Mapped["CaseInterview"] = relationship(back_populates="interview_attachments")
    attachment: Mapped["Attachment"] = relationship()

    __table_args__ = (
        UniqueConstraint("interview_id", "attachment_id"),
    )


```

---

## API Design

### Endpoints

#### Interview CRUD

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `GET` | `/cases/{case_id}/interviews` | List interviews | case access |
| `POST` | `/cases/{case_id}/interviews` | Create interview | assignee/admin + case user-owned |
| `GET` | `/interviews/{id}` | Get interview detail | case access |
| `PATCH` | `/interviews/{id}` | Update interview | assignee/admin + case user-owned |
| `DELETE` | `/interviews/{id}` | Delete interview | admin+ |

#### Version Management

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `GET` | `/interviews/{id}/versions` | List versions | case access |
| `GET` | `/interviews/{id}/versions/{v}` | Get version content | case access |
| `GET` | `/interviews/{id}/versions/diff?v1=X&v2=Y` | Get diff between versions | case access |
| `POST` | `/interviews/{id}/versions/{v}/restore` | Restore to version | assignee/admin + case user-owned |

#### Notes

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `GET` | `/interviews/{id}/notes` | List notes | case access |
| `POST` | `/interviews/{id}/notes` | Create note | case access |
| `PATCH` | `/interviews/{id}/notes/{note_id}` | Update note | author only |
| `DELETE` | `/interviews/{id}/notes/{note_id}` | Delete note | author or admin+ |

#### Attachments

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `GET` | `/interviews/{id}/attachments` | List attachments | case access |
| `POST` | `/interviews/{id}/attachments` | Upload file | assignee/admin + case user-owned |
| `DELETE` | `/interviews/{id}/attachments/{att_id}` | Remove attachment | case_manager+ |
| `POST` | `/interviews/{id}/attachments/{att_id}/transcribe` | Request transcription | assignee/admin |
| `GET` | `/interviews/{id}/attachments/{att_id}/transcription` | Get transcription status/result | case access |

#### AI Features

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `POST` | `/interviews/{id}/ai/summarize` | Summarize single interview | case access + AI enabled |
| `POST` | `/cases/{case_id}/interviews/ai/summarize-all` | Summarize all interviews | case access + AI enabled |

#### Export

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `GET` | `/interviews/{id}/export?format=pdf` | Export single interview | case access |
| `GET` | `/cases/{case_id}/interviews/export?format=pdf` | Export all interviews | case access |
| `GET` | `/interviews/{id}/export?format=json` | Export as JSON (compliance) | case_manager+ |

### Request/Response Schemas

```python
# app/schemas/interview.py

from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from uuid import UUID
from typing import Literal

# ============ Request Schemas ============

class InterviewCreate(BaseModel):
    interview_type: Literal["phone", "video", "in_person"]
    conducted_at: datetime
    duration_minutes: int | None = Field(None, ge=1, le=480)
    transcript_html: str | None = Field(None, max_length=2_000_000)  # 2MB limit
    status: Literal["draft", "completed"] = "completed"

    @field_validator("transcript_html")
    @classmethod
    def sanitize_transcript(cls, v):
        if v:
            return sanitize_html(v)
        return v


class InterviewUpdate(BaseModel):
    interview_type: Literal["phone", "video", "in_person"] | None = None
    conducted_at: datetime | None = None
    duration_minutes: int | None = Field(None, ge=1, le=480)
    transcript_html: str | None = Field(None, max_length=2_000_000)
    status: Literal["draft", "completed"] | None = None
    expected_version: int | None = None  # Optimistic concurrency

    @field_validator("transcript_html")
    @classmethod
    def sanitize_transcript(cls, v):
        if v:
            return sanitize_html(v)
        return v


class InterviewNoteCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=50_000)
    transcript_version: int | None = Field(None, ge=1)  # Defaults to current interview version
    anchor_start: int | None = Field(None, ge=0)
    anchor_end: int | None = Field(None, ge=0)
    anchor_text: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_anchor(self):
        has_start = self.anchor_start is not None
        has_end = self.anchor_end is not None
        has_text = self.anchor_text is not None

        # All or nothing
        if has_start or has_end or has_text:
            if not (has_start and has_end and has_text):
                raise ValueError("Anchor requires start, end, and text together")
            if self.anchor_end < self.anchor_start:
                raise ValueError("anchor_end must be >= anchor_start")
        return self

    @field_validator("content")
    @classmethod
    def sanitize_note(cls, v):
        return sanitize_html(v)


class InterviewNoteUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=50_000)

    @field_validator("content")
    @classmethod
    def sanitize_note(cls, v):
        return sanitize_html(v)


class TranscriptionRequest(BaseModel):
    language: str = "en"  # ISO 639-1 code
    prompt: str | None = None  # Optional context for Whisper


# ============ Response Schemas ============

class InterviewListItem(BaseModel):
    id: UUID
    interview_type: str
    conducted_at: datetime
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
    id: UUID
    case_id: UUID
    interview_type: str
    conducted_at: datetime
    conducted_by_user_id: UUID
    conducted_by_name: str
    duration_minutes: int | None

    # Transcript
    transcript_html: str | None
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


class InterviewVersionListItem(BaseModel):
    version: int
    author_user_id: UUID
    author_name: str
    source: str
    content_size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewVersionRead(BaseModel):
    version: int
    content_html: str
    content_text: str
    author_user_id: UUID
    author_name: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewVersionDiff(BaseModel):
    version_from: int
    version_to: int
    diff_html: str  # Unified diff with HTML markup
    additions: int
    deletions: int


class InterviewNoteRead(BaseModel):
    id: UUID
    content: str
    transcript_version: int

    # Original anchor
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


class InterviewAttachmentRead(BaseModel):
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
    status: str  # 'pending', 'processing', 'completed', 'failed'
    progress: int | None  # 0-100 if available
    result: str | None  # Transcription text if completed
    error: str | None


class InterviewSummaryResponse(BaseModel):
    interview_id: UUID
    summary: str
    key_points: list[str]
    concerns: list[str]
    sentiment: Literal["positive", "neutral", "mixed", "concerning"]
    follow_up_items: list[str]


class AllInterviewsSummaryResponse(BaseModel):
    case_id: UUID
    interview_count: int
    overall_summary: str
    timeline: list[dict]  # [{date, type, key_point}]
    recurring_themes: list[str]
    candidate_strengths: list[str]
    areas_of_concern: list[str]
    recommended_actions: list[str]


class InterviewExportResponse(BaseModel):
    download_url: str
    expires_at: datetime
    format: str
    file_size: int
```

---

## Frontend Design

### Component Architecture

```
components/cases/interviews/
├── CaseInterviewTab.tsx           # Main container, handles routing between list/detail
├── InterviewList.tsx              # Left panel list on desktop, full screen on mobile
├── InterviewListItem.tsx          # Single item in list
├── InterviewDetail.tsx            # Detail view with split pane
├── InterviewHeader.tsx            # Type badge, date, duration, actions
├── InterviewTranscript.tsx        # Transcript display with version indicator
├── InterviewTranscriptEditor.tsx  # Rich text editor for transcript
├── InterviewNotes.tsx             # Collapsible notes sidebar
├── InterviewNoteItem.tsx          # Single note with anchor highlight
├── InterviewNoteEditor.tsx        # Add/edit note with anchor selection
├── InterviewAttachments.tsx       # File list with upload
├── InterviewAttachmentItem.tsx    # Single file with transcription status
├── InterviewVersionHistory.tsx    # Version list modal
├── InterviewVersionDiff.tsx       # Diff view modal
├── InterviewAISummary.tsx         # AI summary panel
├── InterviewExportDialog.tsx      # Export options dialog
├── InterviewEditor.tsx            # Create/edit interview modal
└── InterviewDeleteDialog.tsx      # Delete confirmation
```

### Layout Implementation

#### Desktop Layout (lg+)

```tsx
// CaseInterviewTab.tsx
<div className="grid grid-cols-[320px_1fr] gap-4 h-[calc(100vh-200px)]">
    {/* Left: Interview List */}
    <div className="border rounded-lg overflow-hidden">
        <InterviewList
            interviews={interviews}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onAdd={() => setEditorOpen(true)}
        />
    </div>

    {/* Right: Detail View */}
    <div className="border rounded-lg overflow-hidden">
        {selectedInterview ? (
            <InterviewDetail
                interview={selectedInterview}
                notesCollapsed={notesCollapsed}
                onToggleNotes={() => setNotesCollapsed(!notesCollapsed)}
            />
        ) : (
            <EmptyState onAdd={() => setEditorOpen(true)} />
        )}
    </div>
</div>
```

#### Mobile Layout (< lg)

```tsx
// Uses sheet/drawer pattern
{!selectedId ? (
    <InterviewList
        interviews={interviews}
        onSelect={setSelectedId}
        onAdd={() => setEditorOpen(true)}
    />
) : (
    <div className="flex flex-col h-full">
        <Button variant="ghost" onClick={() => setSelectedId(null)}>
            <ArrowLeftIcon /> Back to list
        </Button>
        <Tabs defaultValue="transcript">
            <TabsList>
                <TabsTrigger value="transcript">Transcript</TabsTrigger>
                <TabsTrigger value="notes">Notes ({notesCount})</TabsTrigger>
                <TabsTrigger value="files">Files ({filesCount})</TabsTrigger>
            </TabsList>
            <TabsContent value="transcript">
                <InterviewTranscript ... />
            </TabsContent>
            <TabsContent value="notes">
                <InterviewNotes ... />
            </TabsContent>
            <TabsContent value="files">
                <InterviewAttachments ... />
            </TabsContent>
        </Tabs>
    </div>
)}
```

#### Split Pane Detail View

```tsx
// InterviewDetail.tsx
<div className="flex flex-col h-full">
    <InterviewHeader
        interview={interview}
        onEdit={...}
        onDelete={...}
        onExport={...}
    />

    <div className={cn(
        "flex-1 grid transition-all duration-200",
        notesCollapsed
            ? "grid-cols-1"
            : "grid-cols-[1fr_320px]"
    )}>
        {/* Transcript Section */}
        <div className="border-r overflow-auto p-4">
            <InterviewTranscript
                interview={interview}
                notes={notes}
                highlightAnchors={!notesCollapsed}
            />
        </div>

        {/* Notes Sidebar */}
        {!notesCollapsed && (
            <div className="bg-muted/30 overflow-auto">
                <InterviewNotes
                    interview={interview}
                    notes={notes}
                    onAddNote={...}
                />
            </div>
        )}
    </div>

    {/* Collapse Toggle */}
    <Button
        variant="ghost"
        size="icon"
        className="absolute right-2 top-16"
        onClick={onToggleNotes}
    >
        {notesCollapsed ? <PanelRightOpenIcon /> : <PanelRightCloseIcon />}
    </Button>
</div>
```

### Anchor Recalculation UI

```tsx
// InterviewNoteItem.tsx
function InterviewNoteItem({ note, currentVersion }) {
    const anchorStatus = note.anchor_status;
    const isOnOldVersion = note.transcript_version < currentVersion;

    return (
        <div className="p-3 rounded-lg border bg-card">
            {/* Anchor status indicator */}
            {note.anchor_text && (
                <div className="mb-2">
                    {anchorStatus === 'valid' && (
                        <Badge variant="outline" className="text-green-600">
                            <CheckIcon className="h-3 w-3 mr-1" />
                            Anchored
                        </Badge>
                    )}
                    {anchorStatus === 'approximate' && (
                        <Badge variant="outline" className="text-yellow-600">
                            <AlertTriangleIcon className="h-3 w-3 mr-1" />
                            Approximate position
                        </Badge>
                    )}
                    {anchorStatus === 'lost' && (
                        <Badge variant="outline" className="text-red-600">
                            <XIcon className="h-3 w-3 mr-1" />
                            Text no longer exists
                        </Badge>
                    )}
                    {isOnOldVersion && (
                        <span className="text-xs text-muted-foreground ml-2">
                            from v{note.transcript_version}
                        </span>
                    )}
                </div>
            )}

            {/* Note content */}
            <div dangerouslySetInnerHTML={{ __html: note.content }} />

            {/* Meta */}
            <div className="text-xs text-muted-foreground mt-2">
                {note.author_name} · {formatRelativeTime(note.created_at)}
            </div>
        </div>
    );
}
```

### React Query Hooks

```typescript
// lib/hooks/use-interviews.ts

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api/interviews";

// ============ Queries ============

export function useInterviews(caseId: string) {
    return useQuery({
        queryKey: ["interviews", caseId],
        queryFn: () => api.listInterviews(caseId),
        enabled: !!caseId,
    });
}

export function useInterview(interviewId: string) {
    return useQuery({
        queryKey: ["interview", interviewId],
        queryFn: () => api.getInterview(interviewId),
        enabled: !!interviewId,
    });
}

export function useInterviewVersions(interviewId: string) {
    return useQuery({
        queryKey: ["interview", interviewId, "versions"],
        queryFn: () => api.listVersions(interviewId),
        enabled: !!interviewId,
    });
}

export function useInterviewVersion(interviewId: string, version: number) {
    return useQuery({
        queryKey: ["interview", interviewId, "versions", version],
        queryFn: () => api.getVersion(interviewId, version),
        enabled: !!interviewId && version > 0,
    });
}

export function useInterviewVersionDiff(interviewId: string, v1: number, v2: number) {
    return useQuery({
        queryKey: ["interview", interviewId, "diff", v1, v2],
        queryFn: () => api.getVersionDiff(interviewId, v1, v2),
        enabled: !!interviewId && v1 > 0 && v2 > 0 && v1 !== v2,
    });
}

export function useInterviewNotes(interviewId: string) {
    return useQuery({
        queryKey: ["interview", interviewId, "notes"],
        queryFn: () => api.listNotes(interviewId),
        enabled: !!interviewId,
    });
}

export function useInterviewAttachments(interviewId: string) {
    return useQuery({
        queryKey: ["interview", interviewId, "attachments"],
        queryFn: () => api.listAttachments(interviewId),
        enabled: !!interviewId,
    });
}

export function useTranscriptionStatus(interviewId: string, attachmentId: string) {
    return useQuery({
        queryKey: ["interview", interviewId, "attachments", attachmentId, "transcription"],
        queryFn: () => api.getTranscriptionStatus(interviewId, attachmentId),
        enabled: !!interviewId && !!attachmentId,
        refetchInterval: (data) =>
            data?.status === "processing" ? 3000 : false,  // Poll while processing
    });
}

// ============ Mutations ============

export function useCreateInterview() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ caseId, data }: { caseId: string; data: InterviewCreate }) =>
            api.createInterview(caseId, data),
        onSuccess: (_, { caseId }) => {
            queryClient.invalidateQueries({ queryKey: ["interviews", caseId] });
        },
    });
}

export function useUpdateInterview() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ interviewId, data }: { interviewId: string; data: InterviewUpdate }) =>
            api.updateInterview(interviewId, data),
        onSuccess: (interview) => {
            queryClient.invalidateQueries({ queryKey: ["interview", interview.id] });
            queryClient.invalidateQueries({ queryKey: ["interviews", interview.case_id] });
            // Invalidate versions if transcript changed
            queryClient.invalidateQueries({ queryKey: ["interview", interview.id, "versions"] });
        },
    });
}

export function useDeleteInterview() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (interviewId: string) => api.deleteInterview(interviewId),
        onSuccess: (_, interviewId) => {
            queryClient.invalidateQueries({ queryKey: ["interviews"] });
            queryClient.removeQueries({ queryKey: ["interview", interviewId] });
        },
    });
}

export function useRestoreInterviewVersion() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ interviewId, version }: { interviewId: string; version: number }) =>
            api.restoreVersion(interviewId, version),
        onSuccess: (interview) => {
            queryClient.invalidateQueries({ queryKey: ["interview", interview.id] });
            queryClient.invalidateQueries({ queryKey: ["interview", interview.id, "versions"] });
            // Recalculate note anchors
            queryClient.invalidateQueries({ queryKey: ["interview", interview.id, "notes"] });
        },
    });
}

export function useCreateInterviewNote() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ interviewId, data }: { interviewId: string; data: InterviewNoteCreate }) =>
            api.createNote(interviewId, data),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: ["interview", interviewId, "notes"] });
            queryClient.invalidateQueries({ queryKey: ["interview", interviewId] });  // Update count
        },
    });
}

export function useUpdateInterviewNote() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ interviewId, noteId, data }: {
            interviewId: string;
            noteId: string;
            data: InterviewNoteUpdate
        }) => api.updateNote(interviewId, noteId, data),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: ["interview", interviewId, "notes"] });
        },
    });
}

export function useDeleteInterviewNote() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ interviewId, noteId }: { interviewId: string; noteId: string }) =>
            api.deleteNote(interviewId, noteId),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: ["interview", interviewId, "notes"] });
            queryClient.invalidateQueries({ queryKey: ["interview", interviewId] });
        },
    });
}

export function useUploadInterviewAttachment() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ interviewId, file }: { interviewId: string; file: File }) =>
            api.uploadAttachment(interviewId, file),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: ["interview", interviewId, "attachments"] });
            queryClient.invalidateQueries({ queryKey: ["interview", interviewId] });
        },
    });
}

export function useDeleteInterviewAttachment() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ interviewId, attachmentId }: { interviewId: string; attachmentId: string }) =>
            api.deleteAttachment(interviewId, attachmentId),
        onSuccess: (_, { interviewId }) => {
            queryClient.invalidateQueries({ queryKey: ["interview", interviewId, "attachments"] });
            queryClient.invalidateQueries({ queryKey: ["interview", interviewId] });
        },
    });
}

export function useRequestTranscription() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ interviewId, attachmentId, data }: {
            interviewId: string;
            attachmentId: string;
            data?: TranscriptionRequest;
        }) => api.requestTranscription(interviewId, attachmentId, data),
        onSuccess: (_, { interviewId, attachmentId }) => {
            queryClient.invalidateQueries({
                queryKey: ["interview", interviewId, "attachments", attachmentId, "transcription"]
            });
        },
    });
}

export function useSummarizeInterview() {
    return useMutation({
        mutationFn: (interviewId: string) => api.summarizeInterview(interviewId),
    });
}

export function useSummarizeAllInterviews() {
    return useMutation({
        mutationFn: (caseId: string) => api.summarizeAllInterviews(caseId),
    });
}

export function useExportInterview() {
    return useMutation({
        mutationFn: ({ interviewId, format }: { interviewId: string; format: "pdf" | "json" }) =>
            api.exportInterview(interviewId, format),
    });
}

export function useExportAllInterviews() {
    return useMutation({
        mutationFn: ({ caseId, format }: { caseId: string; format: "pdf" | "json" }) =>
            api.exportAllInterviews(caseId, format),
    });
}
```

---

## AI Integration

### Transcription Flow

```python
# app/services/transcription_service.py

import openai
from app.core.config import settings
from app.services.storage_service import download_file
from app.services.interview_service import update_interview_transcript

async def request_transcription(
    session: Session,
    interview_attachment: InterviewAttachment,
    language: str = "en",
    prompt: str | None = None,
) -> None:
    """Queue transcription job."""
    interview_attachment.transcription_status = "pending"
    session.add(interview_attachment)
    await session.commit()

    # Queue background job
    await transcription_queue.enqueue(
        process_transcription,
        interview_attachment_id=str(interview_attachment.id),
        language=language,
        prompt=prompt,
    )


async def process_transcription(
    interview_attachment_id: str,
    language: str,
    prompt: str | None,
) -> None:
    """Background job to process transcription."""
    async with get_session() as session:
        ia = await get_interview_attachment(session, interview_attachment_id)

        try:
            ia.transcription_status = "processing"
            await session.commit()

            # Download file from S3
            file_bytes = await download_file(ia.attachment.storage_key)

            # Call Whisper API
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.mp3", file_bytes),
                language=language,
                prompt=prompt,
                response_format="text",
            )

            # Get interview and create new version
            interview = await get_interview(session, ia.interview_id)

            # Format transcription
            filename = ia.attachment.filename
            transcription_html = f"""
<div class="ai-transcription">
<p><strong>AI Transcription</strong> — {filename}</p>
<hr />
{format_transcript_paragraphs(transcript)}
</div>
"""

            # Append or set transcript
            if interview.transcript_html:
                new_html = f"{interview.transcript_html}\n\n{transcription_html}"
            else:
                new_html = transcription_html

            # Create new version with source='ai_transcription'
            await update_interview_transcript(
                session=session,
                interview=interview,
                new_html=new_html,
                user=SystemUser(),  # Service account
                source="ai_transcription",
            )

            # Update attachment status
            ia.transcription_status = "completed"
            ia.transcription_completed_at = func.now()

            # Log activity (no PII)
            await log_activity(
                session=session,
                case_id=interview.case_id,
                activity_type="interview_transcribed",
                actor_user_id=None,
                details={
                    "interview_id": str(interview.id),
                    "attachment_id": str(ia.attachment_id),
                    "source": "whisper",
                    "language": language,
                },
            )

        except Exception as e:
            ia.transcription_status = "failed"
            ia.transcription_error = str(e)[:500]

        await session.commit()
```

### Summary Generation

```python
# app/services/ai_interview_service.py

INTERVIEW_SUMMARY_PROMPT = """
Analyze the following interview transcript and notes for a surrogacy candidate.

TRANSCRIPT:
{transcript}

INTERVIEWER NOTES:
{notes}

Provide a structured analysis with:
1. Summary (2-3 paragraphs)
2. Key points (bullet list)
3. Any concerns or red flags
4. Overall sentiment (positive/neutral/mixed/concerning)
5. Recommended follow-up items

Be objective and professional. Do not include PII in your response.
"""

async def summarize_interview(
    session: Session,
    interview: CaseInterview,
    ai_settings: AISettings,
) -> InterviewSummaryResponse:
    """Generate AI summary of a single interview."""

    # Gather content
    transcript = interview.transcript_text or ""
    notes = "\n".join([n.content for n in interview.notes]) or "No notes"

    # Call AI
    response = await call_ai(
        api_key=ai_settings.api_key,
        model=ai_settings.model,
        prompt=INTERVIEW_SUMMARY_PROMPT.format(
            transcript=transcript[:50000],  # Limit tokens
            notes=notes[:5000],
        ),
        response_schema=InterviewSummarySchema,
    )

    # Log without PII
    await log_activity(
        session=session,
        case_id=interview.case_id,
        activity_type="ai_interview_summarized",
        details={
            "interview_id": str(interview.id),
            "model": ai_settings.model,
        },
    )

    return InterviewSummaryResponse(
        interview_id=interview.id,
        **response,
    )
```

---

## Security & Compliance

### Retention Policy Implementation

Reuse the existing compliance retention system (`data_retention_policies` and
`compliance_service`), and add an `interview` entity type.

```python
# app/services/compliance_service.py (extend)

def _build_retention_query(entity_type: str, cutoff: datetime):
    if entity_type == "interview":
        return (
            select(CaseInterview)
            .where(CaseInterview.updated_at < cutoff)
        )
    # existing entity types...


# app/services/interview_service.py (on create/update)

def apply_retention_policy(db: Session, interview: CaseInterview) -> None:
    policy = get_retention_policy(db, interview.organization_id, "interview")
    if policy and policy.retention_days:
        interview.retention_policy_id = policy.id
        interview.expires_at = interview.created_at + timedelta(days=policy.retention_days)
```

### Export Implementation

```python
# app/services/interview_export_service.py

from weasyprint import HTML
from datetime import datetime, timedelta

async def export_interview_pdf(
    interview: CaseInterview,
    include_notes: bool = True,
    include_attachments: bool = False,
) -> bytes:
    """Generate PDF export of interview."""

    # Render HTML template
    html_content = render_template(
        "exports/interview.html",
        interview=interview,
        notes=interview.notes if include_notes else [],
        versions=[v for v in interview.versions[-5:]],  # Last 5 versions
        generated_at=datetime.utcnow(),
    )

    # Convert to PDF
    pdf_bytes = HTML(string=html_content).write_pdf()

    return pdf_bytes


async def export_interview_json(
    interview: CaseInterview,
    include_versions: bool = True,
) -> dict:
    """Generate JSON export for compliance/backup."""

    return {
        "export_version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "interview": {
            "id": str(interview.id),
            "case_id": str(interview.case_id),
            "interview_type": interview.interview_type,
            "conducted_at": interview.conducted_at.isoformat(),
            "conducted_by_user_id": str(interview.conducted_by_user_id),
            "duration_minutes": interview.duration_minutes,
            "transcript_html": interview.transcript_html,
            "transcript_text": interview.transcript_text,
            "status": interview.status,
            "created_at": interview.created_at.isoformat(),
            "updated_at": interview.updated_at.isoformat(),
        },
        "versions": [
            {
                "version": v.version,
                "content_text": v.content_text,
                "author_user_id": str(v.author_user_id),
                "source": v.source,
                "created_at": v.created_at.isoformat(),
            }
            for v in interview.versions
        ] if include_versions else [],
        "notes": [
            {
                "id": str(n.id),
                "content": n.content,
                "transcript_version": n.transcript_version,
                "anchor_text": n.anchor_text,
                "author_user_id": str(n.author_user_id),
                "created_at": n.created_at.isoformat(),
            }
            for n in interview.notes
        ],
        "attachments": [
            {
                "id": str(ia.attachment_id),
                "filename": ia.attachment.filename,
                "content_type": ia.attachment.content_type,
                "file_size": ia.attachment.file_size,
                "storage_key": ia.attachment.storage_key,
            }
            for ia in interview.interview_attachments
        ],
    }


async def create_export_download(
    session: Session,
    content: bytes,
    filename: str,
    content_type: str,
    expires_minutes: int = 60,
) -> str:
    """Upload export to S3 and return signed URL."""

    key = f"exports/{uuid4()}/{filename}"

    await upload_file(
        key=key,
        content=content,
        content_type=content_type,
    )

    url = await generate_presigned_url(
        key=key,
        expires_in=expires_minutes * 60,
    )

    return url
```

### Anchor Recalculation

```python
# app/services/anchor_service.py

import difflib

def recalculate_anchor_positions(
    note: InterviewNote,
    original_text: str,
    current_text: str,
) -> tuple[int | None, int | None, str]:
    """
    Recalculate anchor position after transcript changes.

    Returns: (new_start, new_end, status)
    Status: 'valid' | 'approximate' | 'lost'
    """
    if not note.anchor_text:
        return None, None, None

    anchor_text = note.anchor_text

    # Try exact match first
    idx = current_text.find(anchor_text)
    if idx != -1:
        return idx, idx + len(anchor_text), "valid"

    # Try fuzzy match
    matcher = difflib.SequenceMatcher(None, original_text, current_text)

    # Find where the original anchor maps to
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # Check if anchor falls within this equal block
            if note.anchor_start >= i1 and note.anchor_end <= i2:
                offset = j1 - i1
                new_start = note.anchor_start + offset
                new_end = note.anchor_end + offset

                # Verify the text still matches
                if current_text[new_start:new_end] == anchor_text:
                    return new_start, new_end, "valid"

    # Try to find similar text nearby
    best_ratio = 0
    best_match = None

    # Search in windows around the original position
    search_radius = 500  # characters
    search_start = max(0, note.anchor_start - search_radius)
    search_end = min(len(current_text), note.anchor_end + search_radius)
    search_area = current_text[search_start:search_end]

    for i in range(len(search_area) - len(anchor_text) + 1):
        candidate = search_area[i:i + len(anchor_text)]
        ratio = difflib.SequenceMatcher(None, anchor_text, candidate).ratio()
        if ratio > best_ratio and ratio > 0.6:  # 60% similarity threshold
            best_ratio = ratio
            best_match = (search_start + i, search_start + i + len(anchor_text))

    if best_match:
        return best_match[0], best_match[1], "approximate"

    # Anchor text is gone
    return None, None, "lost"


async def update_note_anchors_for_version(
    session: Session,
    interview: CaseInterview,
) -> None:
    """
    Recalculate all note anchors after transcript version change.
    Called when transcript is updated or restored.
    """
    current_text = interview.transcript_text or ""
    current_version = interview.transcript_version

    for note in interview.notes:
        if not note.anchor_text:
            continue

        # Get the original version's text
        if note.transcript_version == current_version:
            # Note was created on current version, anchor is valid
            note.current_anchor_start = note.anchor_start
            note.current_anchor_end = note.anchor_end
            note.anchor_status = "valid"
        else:
            # Get original version text
            original_version = await session.scalar(
                select(InterviewTranscriptVersion)
                .where(
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

        session.add(note)
```

### S3 Offloading

```python
# app/services/transcript_storage_service.py

OFFLOAD_THRESHOLD = 100 * 1024  # 100KB

async def should_offload(content: str) -> bool:
    """Check if content should be offloaded to S3."""
    return len(content.encode('utf-8')) > OFFLOAD_THRESHOLD


async def store_transcript_content(
    interview_id: UUID,
    version: int,
    html_content: str,
    text_content: str,
) -> tuple[str | None, str, str | None]:
    """
    Store transcript content, offloading to S3 if large.

    Returns: (html_in_db, text_in_db, storage_key)
    """
    size = len(html_content.encode('utf-8'))

    if await should_offload(html_content):
        # Store in S3
        storage_key = f"transcripts/{interview_id}/v{version}.json"

        content = {
            "html": html_content,
            "text": text_content,
            "version": version,
            "stored_at": datetime.utcnow().isoformat(),
        }

        await upload_file(
            key=storage_key,
            content=json.dumps(content).encode(),
            content_type="application/json",
        )

        return None, text_content, storage_key
    else:
        return html_content, text_content, None


async def load_transcript_content(
    interview: CaseInterview,
) -> tuple[str, str]:
    """Load transcript content, fetching from S3 if offloaded."""

    if interview.transcript_storage_key:
        content_bytes = await download_file(interview.transcript_storage_key)
        content = json.loads(content_bytes)
        return content["html"], interview.transcript_text or content.get("text", "")
    else:
        return interview.transcript_html or "", interview.transcript_text or ""
```

---

## Implementation Phases

### Phase 1: Database & Core Backend (5 days)

| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Create Alembic migration | `alembic/versions/xxx_add_interview_tables.py` |
| 1.2 | Add SQLAlchemy models | `app/db/models.py` |
| 1.3 | Create Pydantic schemas | `app/schemas/interview.py` |
| 1.4 | Implement interview service (CRUD) | `app/services/interview_service.py` |
| 1.5 | Implement version service | `app/services/interview_version_service.py` |
| 1.6 | Add permission checks | `app/core/permissions.py` |
| 1.7 | Create API router (interviews, versions) | `app/routers/interviews.py` |
| 1.8 | Write backend tests | `tests/test_interviews.py` |

### Phase 2: Notes & Anchoring (3 days)

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Implement note service | `app/services/interview_note_service.py` |
| 2.2 | Implement anchor recalculation | `app/services/anchor_service.py` |
| 2.3 | Add notes endpoints | `app/routers/interviews.py` |
| 2.4 | Write anchor tests | `tests/test_interview_anchors.py` |

### Phase 3: Attachments & Storage (3 days)

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Implement attachment linking | `app/services/interview_attachment_service.py` |
| 3.2 | Implement S3 offloading | `app/services/transcript_storage_service.py` |
| 3.3 | Add attachment endpoints | `app/routers/interviews.py` |
| 3.4 | Write storage tests | `tests/test_interview_storage.py` |

### Phase 4: Frontend - Core Components (5 days)

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Create API client | `lib/api/interviews.ts` |
| 4.2 | Create React Query hooks | `lib/hooks/use-interviews.ts` |
| 4.3 | Create TypeScript types | `lib/types/interview.ts` |
| 4.4 | Build CaseInterviewTab | `components/cases/interviews/CaseInterviewTab.tsx` |
| 4.5 | Build InterviewList | `components/cases/interviews/InterviewList.tsx` |
| 4.6 | Build InterviewDetail | `components/cases/interviews/InterviewDetail.tsx` |
| 4.7 | Build InterviewEditor | `components/cases/interviews/InterviewEditor.tsx` |
| 4.8 | Add tab to case page | `app/(app)/cases/[id]/page.tsx` |

### Phase 5: Frontend - Notes & Versions (4 days)

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Build InterviewTranscript | `components/cases/interviews/InterviewTranscript.tsx` |
| 5.2 | Build InterviewNotes (collapsible) | `components/cases/interviews/InterviewNotes.tsx` |
| 5.3 | Build note anchoring UI | `components/cases/interviews/InterviewNoteEditor.tsx` |
| 5.4 | Build InterviewVersionHistory | `components/cases/interviews/InterviewVersionHistory.tsx` |
| 5.5 | Build InterviewVersionDiff | `components/cases/interviews/InterviewVersionDiff.tsx` |
| 5.6 | Write frontend tests | `tests/interviews.test.tsx` |

### Phase 6: Frontend - Attachments (2 days)

| Task | Description | Files |
|------|-------------|-------|
| 6.1 | Build InterviewAttachments | `components/cases/interviews/InterviewAttachments.tsx` |
| 6.2 | Add transcription UI | `components/cases/interviews/TranscriptionStatus.tsx` |

### Phase 7: AI Integration (3 days)

| Task | Description | Files |
|------|-------------|-------|
| 7.1 | Implement Whisper transcription | `app/services/transcription_service.py` |
| 7.2 | Implement summary generation | `app/services/ai_interview_service.py` |
| 7.3 | Add AI endpoints | `app/routers/interviews.py` |
| 7.4 | Build InterviewAISummary | `components/cases/interviews/InterviewAISummary.tsx` |

### Phase 8: Compliance & Export (3 days)

| Task | Description | Files |
|------|-------------|-------|
| 8.1 | Extend compliance retention for interviews | `app/services/compliance_service.py` |
| 8.2 | Implement PDF/JSON export | `app/services/interview_export_service.py` |
| 8.3 | Add export endpoints | `app/routers/interviews.py` |
| 8.4 | Build InterviewExportDialog | `components/cases/interviews/InterviewExportDialog.tsx` |
| 8.5 | Reuse existing retention job (no new job) | `app/worker.py` |

### Phase 9: Polish & Integration (2 days)

| Task | Description | Files |
|------|-------------|-------|
| 9.1 | Mobile responsive testing | All frontend components |
| 9.2 | Keyboard navigation | All interactive components |
| 9.3 | Activity logging integration | `app/services/interview_service.py` |
| 9.4 | End-to-end testing | `tests/e2e/interviews.spec.ts` |

---

## File Checklist

### Backend Files

- [ ] `alembic/versions/xxx_add_interview_tables.py`
- [ ] `app/db/models.py` — Add 4 new models
- [ ] `app/schemas/interview.py` — All request/response schemas
- [ ] `app/routers/interviews.py` — API endpoints
- [ ] `app/services/interview_service.py` — Core CRUD
- [ ] `app/services/interview_version_service.py` — Versioning logic
- [ ] `app/services/interview_note_service.py` — Notes CRUD
- [ ] `app/services/anchor_service.py` — Anchor recalculation
- [ ] `app/services/interview_attachment_service.py` — File linking
- [ ] `app/services/transcript_storage_service.py` — S3 offloading
- [ ] `app/services/transcription_service.py` — Whisper integration
- [ ] `app/services/ai_interview_service.py` — AI summaries
- [ ] `app/services/interview_export_service.py` — PDF/JSON export
- [ ] `app/services/compliance_service.py` — Add interview retention entity
- [ ] `app/core/permissions.py` — Add interview permissions
- [ ] `tests/test_interviews.py`
- [ ] `tests/test_interview_anchors.py`
- [ ] `tests/test_interview_storage.py`

### Frontend Files

- [ ] `lib/api/interviews.ts` — API client
- [ ] `lib/hooks/use-interviews.ts` — React Query hooks
- [ ] `lib/types/interview.ts` — TypeScript types
- [ ] `components/cases/interviews/CaseInterviewTab.tsx`
- [ ] `components/cases/interviews/InterviewList.tsx`
- [ ] `components/cases/interviews/InterviewListItem.tsx`
- [ ] `components/cases/interviews/InterviewDetail.tsx`
- [ ] `components/cases/interviews/InterviewHeader.tsx`
- [ ] `components/cases/interviews/InterviewTranscript.tsx`
- [ ] `components/cases/interviews/InterviewTranscriptEditor.tsx`
- [ ] `components/cases/interviews/InterviewNotes.tsx`
- [ ] `components/cases/interviews/InterviewNoteItem.tsx`
- [ ] `components/cases/interviews/InterviewNoteEditor.tsx`
- [ ] `components/cases/interviews/InterviewAttachments.tsx`
- [ ] `components/cases/interviews/InterviewAttachmentItem.tsx`
- [ ] `components/cases/interviews/TranscriptionStatus.tsx`
- [ ] `components/cases/interviews/InterviewVersionHistory.tsx`
- [ ] `components/cases/interviews/InterviewVersionDiff.tsx`
- [ ] `components/cases/interviews/InterviewAISummary.tsx`
- [ ] `components/cases/interviews/InterviewExportDialog.tsx`
- [ ] `components/cases/interviews/InterviewEditor.tsx`
- [ ] `components/cases/interviews/InterviewDeleteDialog.tsx`
- [ ] `app/(app)/cases/[id]/page.tsx` — Add Interview tab
- [ ] `tests/interviews.test.tsx`

---

## Testing Strategy

### Backend Tests

```python
# tests/test_interviews.py

class TestInterviewPermissions:
    def test_cannot_create_interview_if_case_in_queue(self, client, case_in_queue):
        """Case must be claimed before adding interviews."""
        res = client.post(f"/cases/{case_in_queue.id}/interviews", ...)
        assert res.status_code == 403

    def test_assignee_can_create_interview(self, client, assigned_case, assignee_auth):
        res = client.post(f"/cases/{assigned_case.id}/interviews", ..., headers=assignee_auth)
        assert res.status_code == 201

    def test_case_manager_can_create_interview(self, client, assigned_case, case_manager_auth):
        res = client.post(f"/cases/{assigned_case.id}/interviews", ..., headers=case_manager_auth)
        assert res.status_code == 201

    def test_only_admin_can_delete_interview(self, client, interview, assignee_auth, admin_auth):
        res = client.delete(f"/interviews/{interview.id}", headers=assignee_auth)
        assert res.status_code == 403
        res = client.delete(f"/interviews/{interview.id}", headers=admin_auth)
        assert res.status_code == 204


class TestInterviewVersioning:
    def test_update_creates_new_version(self, client, interview, auth):
        original_version = interview.transcript_version
        client.patch(f"/interviews/{interview.id}", json={"transcript_html": "new"}, headers=auth)
        assert interview.transcript_version == original_version + 1

    def test_no_version_if_content_unchanged(self, client, interview, auth):
        original_version = interview.transcript_version
        client.patch(f"/interviews/{interview.id}", json={"transcript_html": interview.transcript_html}, headers=auth)
        assert interview.transcript_version == original_version

    def test_optimistic_concurrency_conflict(self, client, interview, auth):
        res = client.patch(
            f"/interviews/{interview.id}",
            json={"transcript_html": "new", "expected_version": 999},
            headers=auth,
        )
        assert res.status_code == 409

    def test_restore_version_creates_new_version(self, client, interview, auth):
        # Create v2
        client.patch(f"/interviews/{interview.id}", json={"transcript_html": "v2"}, headers=auth)
        # Restore v1
        res = client.post(f"/interviews/{interview.id}/versions/1/restore", headers=auth)
        assert res.json()["transcript_version"] == 3


class TestInterviewAnchors:
    def test_anchor_valid_on_same_version(self, client, interview, auth):
        # Create note on current version
        note = create_note(interview, anchor_start=0, anchor_end=10, anchor_text="Hello")
        assert note.anchor_status == "valid"

    def test_anchor_recalculated_after_edit(self, client, interview, auth):
        # Create note
        note = create_note(interview, anchor_start=0, anchor_end=5, anchor_text="Hello")
        # Edit transcript
        client.patch(f"/interviews/{interview.id}", json={"transcript_html": "Hi Hello world"})
        # Check anchor moved
        note.refresh()
        assert note.current_anchor_start == 3
        assert note.anchor_status == "valid"

    def test_anchor_lost_when_text_removed(self, client, interview, auth):
        note = create_note(interview, anchor_text="goodbye")
        client.patch(f"/interviews/{interview.id}", json={"transcript_html": "hello world"})
        note.refresh()
        assert note.anchor_status == "lost"


class TestInterviewStorage:
    def test_small_transcript_stored_inline(self, client, auth):
        res = client.post("/cases/{id}/interviews", json={"transcript_html": "small"})
        interview = Interview.get(res.json()["id"])
        assert interview.transcript_html == "small"
        assert interview.transcript_storage_key is None

    def test_large_transcript_offloaded_to_s3(self, client, auth):
        large_content = "x" * 200_000  # 200KB
        res = client.post("/cases/{id}/interviews", json={"transcript_html": large_content})
        interview = Interview.get(res.json()["id"])
        assert interview.transcript_html is None
        assert interview.transcript_storage_key is not None
```

### Frontend Tests

```typescript
// tests/interviews.test.tsx

describe("CaseInterviewTab", () => {
    it("renders empty state when no interviews", () => {
        mockUseInterviews.mockReturnValue({ data: [], isLoading: false });
        render(<CaseInterviewTab caseId="123" />);
        expect(screen.getByText(/no interviews/i)).toBeInTheDocument();
    });

    it("renders interview list", () => {
        mockUseInterviews.mockReturnValue({ data: mockInterviews, isLoading: false });
        render(<CaseInterviewTab caseId="123" />);
        expect(screen.getAllByRole("listitem")).toHaveLength(3);
    });

    it("shows detail view when interview selected", async () => {
        render(<CaseInterviewTab caseId="123" />);
        await userEvent.click(screen.getByText("January 4, 2026"));
        expect(screen.getByText(/transcript/i)).toBeInTheDocument();
    });
});

describe("InterviewNotes", () => {
    it("toggles collapse state", async () => {
        render(<InterviewNotes interview={mockInterview} collapsed={false} />);
        const toggle = screen.getByRole("button", { name: /collapse/i });
        await userEvent.click(toggle);
        expect(onToggle).toHaveBeenCalled();
    });

    it("shows anchor status badge", () => {
        const note = { ...mockNote, anchor_status: "approximate" };
        render(<InterviewNoteItem note={note} />);
        expect(screen.getByText(/approximate/i)).toBeInTheDocument();
    });
});

describe("InterviewVersionHistory", () => {
    it("lists versions with authors", () => {
        render(<InterviewVersionHistory interviewId="123" />);
        expect(screen.getByText("v3 · Jane Smith")).toBeInTheDocument();
    });

    it("opens diff modal", async () => {
        render(<InterviewVersionHistory interviewId="123" />);
        await userEvent.click(screen.getByText(/compare/i));
        expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
});
```

---

## Design Tokens Reference

Following `docs/layouts.md`:

| Element | Token |
|---------|-------|
| Interview type (phone) | `bg-blue-500/10 text-blue-600` |
| Interview type (video) | `bg-purple-500/10 text-purple-600` |
| Interview type (in_person) | `bg-green-500/10 text-green-600` |
| Notes sidebar | `bg-muted/30` |
| Version badge | `Badge variant="outline" text-xs` |
| Anchor highlight | `bg-primary/10 rounded` |
| Anchor status (valid) | `text-green-600` |
| Anchor status (approximate) | `text-yellow-600` |
| Anchor status (lost) | `text-red-600` |
| List item hover | `hover:bg-muted/50` |
| Card | `rounded-lg border bg-card` |

---

## Summary

**Total Estimated Effort:** 30 days (6 weeks at ~5 days/week)

**Key Technical Decisions:**
1. Reuse existing `Attachment` model via link table
2. Dual storage (HTML + text) for XSS safety and search
3. Anchors tied to specific transcript version with recalculation
4. S3 offloading for transcripts > 100KB
5. Optimistic concurrency with `expected_version`
6. Retention policies with background enforcement
7. Permission check: case must be user-owned (not in queue)

**Risk Mitigation:**
- Anchor recalculation is complex; test thoroughly with edge cases
- Large transcript handling needs load testing
- AI transcription costs should be monitored per org
