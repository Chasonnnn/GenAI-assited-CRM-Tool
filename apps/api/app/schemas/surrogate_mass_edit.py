"""Schemas for developer-only surrogate mass edit operations."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.enums import SurrogateSource
from app.utils.normalization import (
    MASS_EDIT_RACE_FILTER_KEYS,
    normalize_race_key,
    normalize_state,
)


class SurrogateMassEditStageFilters(BaseModel):
    """Filter criteria for selecting surrogates in a mass edit operation."""

    # Common list filters
    stage_ids: list[UUID] | None = None
    source: SurrogateSource | None = None
    queue_id: UUID | None = None
    q: str | None = Field(None, max_length=100)
    include_archived: bool = False

    # Created date range (date-only; interpreted server-side)
    created_from: date | None = None
    created_to: date | None = None

    # Overview fields
    states: list[str] | None = None
    races: list[str] | None = None
    is_priority: bool | None = None

    # Checklist fields
    is_age_eligible: bool | None = None
    is_citizen_or_pr: bool | None = None
    has_child: bool | None = None
    is_non_smoker: bool | None = None
    has_surrogate_experience: bool | None = None
    num_deliveries_min: int | None = Field(None, ge=0, le=20)
    num_deliveries_max: int | None = Field(None, ge=0, le=20)
    num_csections_min: int | None = Field(None, ge=0, le=10)
    num_csections_max: int | None = Field(None, ge=0, le=10)

    # Derived fields (may require decrypting DOB to compute age)
    age_min: int | None = Field(None, ge=0, le=120)
    age_max: int | None = Field(None, ge=0, le=120)
    bmi_min: float | None = Field(None, ge=0, le=100)
    bmi_max: float | None = Field(None, ge=0, le=100)

    model_config = {"extra": "forbid"}

    @field_validator("states")
    @classmethod
    def normalize_states(cls, v: list[str] | None) -> list[str] | None:
        if not v:
            return None
        normalized: list[str] = []
        for raw in v:
            if raw is None:
                continue
            state = normalize_state(raw)
            if state:
                normalized.append(state)
        return normalized or None

    @field_validator("races")
    @classmethod
    def normalize_races(cls, v: list[str] | None) -> list[str] | None:
        """Normalize race values to canonical keys supported by mass edit."""
        if not v:
            return None
        allowed = set(MASS_EDIT_RACE_FILTER_KEYS)
        normalized: list[str] = []
        for raw in v:
            if raw is None:
                continue
            race_key = normalize_race_key(raw)
            if not race_key:
                continue
            if race_key not in allowed:
                raise ValueError(f"Unsupported race filter option: {raw}")
            normalized.append(race_key)
        return normalized or None

    @model_validator(mode="after")
    def validate_ranges(self) -> "SurrogateMassEditStageFilters":
        if self.age_min is not None and self.age_max is not None and self.age_min > self.age_max:
            raise ValueError("age_min must be <= age_max")
        if (
            self.num_deliveries_min is not None
            and self.num_deliveries_max is not None
            and self.num_deliveries_min > self.num_deliveries_max
        ):
            raise ValueError("num_deliveries_min must be <= num_deliveries_max")
        if (
            self.num_csections_min is not None
            and self.num_csections_max is not None
            and self.num_csections_min > self.num_csections_max
        ):
            raise ValueError("num_csections_min must be <= num_csections_max")
        if self.bmi_min is not None and self.bmi_max is not None and self.bmi_min > self.bmi_max:
            raise ValueError("bmi_min must be <= bmi_max")
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from must be <= created_to")
        return self


class SurrogateMassEditStagePreviewRequest(BaseModel):
    """Preview which surrogates match the given filters."""

    filters: SurrogateMassEditStageFilters = Field(default_factory=SurrogateMassEditStageFilters)

    model_config = {"extra": "forbid"}


class SurrogateMassEditStagePreviewItem(BaseModel):
    """Lightweight item for previewing a mass edit selection."""

    id: UUID
    surrogate_number: str
    full_name: str
    state: str | None
    stage_id: UUID
    status_label: str
    created_at: datetime
    age: int | None = None


class SurrogateMassEditStagePreviewResponse(BaseModel):
    total: int
    over_limit: bool
    max_apply: int
    items: list[SurrogateMassEditStagePreviewItem]


class SurrogateMassEditStageApplyRequest(BaseModel):
    """Apply a stage change to all surrogates matching the filters.

    Notes:
    - Mass edit stage changes are always effective now (no backdating).
    - `expected_total` must come from the preview response to prevent accidental wide updates.
    """

    filters: SurrogateMassEditStageFilters = Field(default_factory=SurrogateMassEditStageFilters)
    stage_id: UUID
    expected_total: int = Field(..., ge=0)
    trigger_workflows: bool = False
    reason: str | None = Field(None, max_length=500)

    model_config = {"extra": "forbid"}


class SurrogateMassEditStageFailure(BaseModel):
    surrogate_id: UUID
    reason: str


class SurrogateMassEditStageApplyResponse(BaseModel):
    matched: int
    applied: int
    pending_approval: int
    failed: list[SurrogateMassEditStageFailure] = Field(default_factory=list)


class SurrogateMassEditOptionsResponse(BaseModel):
    """Distinct filter option values derived from org data."""

    races: list[str] = Field(default_factory=list)
