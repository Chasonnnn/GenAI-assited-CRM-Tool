"""Match API schemas."""

from datetime import date as date_type
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.enums import MatchStatus


class MatchCreate(BaseModel):
    """Request to propose a match."""

    surrogate_id: UUID | None = None
    donor_id: UUID | None = None
    intended_parent_id: UUID
    notes: str | None = None

    @model_validator(mode="after")
    def validate_participants(self):
        if (self.surrogate_id is None) == (self.donor_id is None):
            raise ValueError("Exactly one surrogate or donor is required")
        return self


class MatchRead(BaseModel):
    """Match response."""

    id: str
    match_number: str
    surrogate_id: str | None
    donor_id: str | None = None
    donor_name: str | None = None
    donor_number: str | None = None
    donor_stage_label: str | None = None
    match_kind: Literal["surrogate", "donor"] = "surrogate"
    closed_at: str | None = None
    closure_reason: str | None = None
    outcome: str | None = None
    intended_parent_id: str
    status: MatchStatus
    proposed_by_user_id: str | None
    proposed_at: str
    reviewed_by_user_id: str | None
    reviewed_at: str | None
    notes: str | None
    decline_reason: str | None
    created_at: str
    updated_at: str
    # Denormalized for convenience
    surrogate_number: str | None = None
    surrogate_name: str | None = None
    ip_name: str | None = None
    ip_number: str | None = None
    # Surrogate stage info for status sync
    surrogate_stage_id: str | None = None
    surrogate_stage_slug: str | None = None
    surrogate_stage_label: str | None = None


class MatchListItem(BaseModel):
    """Match list item with summary info."""

    id: str
    match_number: str
    surrogate_id: str | None
    donor_id: str | None = None
    donor_name: str | None = None
    donor_number: str | None = None
    donor_stage_label: str | None = None
    match_kind: Literal["surrogate", "donor"] = "surrogate"
    closed_at: str | None = None
    closure_reason: str | None = None
    outcome: str | None = None
    surrogate_number: str | None
    surrogate_name: str | None
    intended_parent_id: str
    ip_name: str | None
    ip_number: str | None = None
    status: MatchStatus
    proposed_at: str
    # Surrogate stage info for status sync
    surrogate_stage_id: str | None = None
    surrogate_stage_slug: str | None = None
    surrogate_stage_label: str | None = None


class MatchListResponse(BaseModel):
    """Paginated match list."""

    items: list[MatchListItem]
    total: int
    page: int
    per_page: int


class MatchStatsResponse(BaseModel):
    """Match stats summary."""

    total: int
    by_status: dict[MatchStatus, int]


class MatchAcceptRequest(BaseModel):
    """Request to accept a match."""

    notes: str | None = None


class MatchDeclineRequest(BaseModel):
    """Request to decline a match."""

    notes: str | None = None
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def required_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Decline reason is required")
        return value.strip()


class MatchCancelRequest(BaseModel):
    """Request to cancel an accepted match (admin approval required)."""

    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def required_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Cancellation reason is required")
        return value.strip()


class MatchUpdateNotesRequest(BaseModel):
    """Request to update match notes."""

    notes: str


class MatchEventCreate(BaseModel):
    """Request to create a match event."""

    person_type: str = Field(pattern="^(surrogate|donor|ip)$")
    event_type: str = Field(pattern="^(medication|medical_exam|legal|delivery|custom)$")
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str = "America/Los_Angeles"
    all_day: bool = False
    start_date: str | None = None  # YYYY-MM-DD for all-day events
    end_date: str | None = None


class MatchEventUpdate(BaseModel):
    """Request to update a match event."""

    person_type: str | None = Field(None, pattern="^(surrogate|donor|ip)$")
    event_type: str | None = Field(
        None, pattern="^(medication|medical_exam|legal|delivery|custom)$"
    )
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str | None = None
    all_day: bool | None = None
    start_date: str | None = None
    end_date: str | None = None


class MatchEventRead(BaseModel):
    """Match event response."""

    id: str
    match_id: str
    person_type: str
    event_type: str
    title: str
    description: str | None
    starts_at: str | None
    ends_at: str | None
    timezone: str
    all_day: bool
    start_date: str | None
    end_date: str | None
    created_by_user_id: str | None
    created_at: str
    updated_at: str


class MatchCompleteRequest(BaseModel):
    outcome: str = Field(min_length=1, max_length=2000)
    reason: str | None = Field(None, max_length=2000)


class AttemptCreate(BaseModel):
    attempt_type: Literal["embryo_transfer", "retrieval", "collection", "other"]
    status: Literal["planned", "in_progress", "completed", "cancelled"] = "planned"
    started_at: date_type | None = None
    ended_at: date_type | None = None
    outcome: str | None = Field(None, max_length=2000)


class AttemptUpdate(BaseModel):
    attempt_type: Literal["embryo_transfer", "retrieval", "collection", "other"] | None = None
    status: Literal["planned", "in_progress", "completed", "cancelled"] | None = None
    started_at: date_type | None = None
    ended_at: date_type | None = None
    outcome: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def reject_null_required(self):
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in ("attempt_type", "status")
        ):
            raise ValueError("Attempt type and status cannot be null")
        return self


class AttemptRead(AttemptCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    match_id: UUID
    sequence: int
    created_at: datetime
    updated_at: datetime
