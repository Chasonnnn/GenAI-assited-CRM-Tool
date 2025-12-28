"""Pydantic schemas for cases."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.db.enums import CaseSource, OwnerType
from app.utils.normalization import normalize_phone, normalize_state


class CaseCreate(BaseModel):
    """Request schema for creating a case."""

    # Contact (required)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr

    # Contact (optional)
    phone: str | None = Field(None, max_length=20)
    state: str | None = Field(None, max_length=50)

    # Demographics
    date_of_birth: date | None = None
    race: str | None = Field(None, max_length=100)
    height_ft: Decimal | None = Field(None, ge=0, le=10)
    weight_lb: int | None = Field(None, ge=0, le=1000)

    # Eligibility
    is_age_eligible: bool | None = None
    is_citizen_or_pr: bool | None = None
    has_child: bool | None = None
    is_non_smoker: bool | None = None
    has_surrogate_experience: bool | None = None
    num_deliveries: int | None = Field(None, ge=0, le=20)
    num_csections: int | None = Field(None, ge=0, le=10)

    # Workflow
    source: CaseSource = CaseSource.MANUAL
    is_priority: bool = False

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Normalize and validate phone to E.164."""
        if v is None or v.strip() == "":
            return None
        return normalize_phone(v)  # Raises ValueError on invalid

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        """Normalize and validate state to 2-letter code."""
        if v is None or v.strip() == "":
            return None
        return normalize_state(v)  # Raises ValueError on invalid


class CaseUpdate(BaseModel):
    """Request schema for updating a case (partial)."""

    full_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = None
    state: str | None = None
    date_of_birth: date | None = None
    race: str | None = Field(None, max_length=100)
    height_ft: Decimal | None = Field(None, ge=0, le=10)
    weight_lb: int | None = Field(None, ge=0, le=1000)
    is_age_eligible: bool | None = None
    is_citizen_or_pr: bool | None = None
    has_child: bool | None = None
    is_non_smoker: bool | None = None
    has_surrogate_experience: bool | None = None
    num_deliveries: int | None = Field(None, ge=0, le=20)
    num_csections: int | None = Field(None, ge=0, le=10)
    is_priority: bool | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v.strip() == "":
            return None
        return normalize_phone(v)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v.strip() == "":
            return None
        return normalize_state(v)


class BulkAssign(BaseModel):
    """Request schema for bulk case assignment."""

    case_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    owner_type: OwnerType
    owner_id: UUID


class CaseRead(BaseModel):
    """Full case response for detail views."""

    id: UUID
    case_number: str
    stage_id: UUID
    status_label: str
    source: CaseSource
    is_priority: bool

    # Ownership (Salesforce-style)
    owner_type: str  # 'user' | 'queue'
    owner_id: UUID
    owner_name: str | None = None
    created_by_user_id: UUID | None

    # Contact
    full_name: str
    email: str
    phone: str | None
    state: str | None

    # Demographics
    date_of_birth: date | None
    race: str | None
    height_ft: Decimal | None
    weight_lb: int | None

    # Eligibility
    is_age_eligible: bool | None
    is_citizen_or_pr: bool | None
    has_child: bool | None
    is_non_smoker: bool | None
    has_surrogate_experience: bool | None
    num_deliveries: int | None
    num_csections: int | None

    # Soft delete
    is_archived: bool
    archived_at: datetime | None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CaseListItem(BaseModel):
    """Compact case for table views."""

    id: UUID
    case_number: str
    stage_id: UUID
    stage_slug: str | None = None
    stage_type: str | None = None
    status_label: str
    source: CaseSource
    full_name: str
    email: str
    phone: str | None
    state: str | None
    race: str | None = None  # Added for table display
    owner_type: str | None = None
    owner_id: UUID | None = None
    owner_name: str | None = None
    is_priority: bool
    is_archived: bool
    # Calculated fields for table display
    age: int | None = None  # Calculated from date_of_birth
    bmi: float | None = None  # Calculated from height_ft and weight_lb
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseListResponse(BaseModel):
    """Paginated case list response."""

    items: list[CaseListItem]
    total: int
    page: int
    per_page: int
    pages: int


class CaseStatusChange(BaseModel):
    """Request to change case stage."""

    stage_id: UUID
    reason: str | None = Field(None, max_length=500)


class CaseAssign(BaseModel):
    """Request to assign case to a user or queue."""

    owner_type: OwnerType
    owner_id: UUID


class CaseStatusHistoryRead(BaseModel):
    """Status history entry response."""

    id: UUID
    from_stage_id: UUID | None
    to_stage_id: UUID | None
    from_label_snapshot: str | None
    to_label_snapshot: str | None
    changed_by_user_id: UUID | None
    changed_by_name: str | None = None
    reason: str | None
    changed_at: datetime

    model_config = {"from_attributes": True}


class CaseStats(BaseModel):
    """Dashboard aggregation stats with period comparisons."""

    total: int
    by_status: dict[str, int]
    this_week: int
    last_week: int = 0
    week_change_pct: float | None = None
    this_month: int
    last_month: int = 0
    month_change_pct: float | None = None
    pending_tasks: int = 0


class CaseHandoffDeny(BaseModel):
    """Request to deny a pending_handoff case."""

    reason: str | None = Field(
        None, max_length=500, description="Reason for denial (logged in status history)"
    )


class CaseActivityRead(BaseModel):
    """Response schema for case activity log entry."""

    id: UUID
    activity_type: str
    actor_user_id: UUID | None
    actor_name: str | None  # Resolved at read-time
    details: dict | None
    created_at: datetime


class CaseActivityResponse(BaseModel):
    """Paginated response for case activity log."""

    items: list[CaseActivityRead]
    total: int
    page: int
    pages: int
