"""Pydantic schemas for Intended Parents."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.utils.normalization import normalize_phone, normalize_state


# =============================================================================
# Create / Update
# =============================================================================

class IntendedParentCreate(BaseModel):
    """Schema for creating an intended parent."""
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(None, max_length=50)
    state: str | None = Field(None, max_length=100)
    budget: Decimal | None = Field(None, ge=0, le=9999999999.99)
    notes_internal: str | None = Field(None, max_length=10000)
    owner_type: str | None = None  # "user" or "queue"
    owner_id: UUID | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone_field(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else None

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state_field(cls, v: str | None) -> str | None:
        return normalize_state(v)  # Raises ValueError on invalid


class IntendedParentUpdate(BaseModel):
    """Schema for updating an intended parent."""
    full_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    state: str | None = Field(None, max_length=100)
    budget: Decimal | None = Field(None, ge=0, le=9999999999.99)
    notes_internal: str | None = Field(None, max_length=10000)
    owner_type: str | None = None
    owner_id: UUID | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone_field(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else None

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state_field(cls, v: str | None) -> str | None:
        return normalize_state(v)


class IntendedParentStatusUpdate(BaseModel):
    """Schema for changing status."""
    status: str = Field(..., min_length=1)
    reason: str | None = Field(None, max_length=500)


# =============================================================================
# Read / Response
# =============================================================================

class IntendedParentRead(BaseModel):
    """Full intended parent details."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    organization_id: UUID
    full_name: str
    email: str
    phone: str | None
    state: str | None
    budget: Decimal | None
    notes_internal: str | None
    status: str
    owner_type: str | None
    owner_id: UUID | None
    owner_name: str | None = None  # Resolved from user/queue
    is_archived: bool
    archived_at: datetime | None
    last_activity: datetime
    created_at: datetime
    updated_at: datetime


class IntendedParentListItem(BaseModel):
    """Minimal fields for list view."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    full_name: str
    email: str
    phone: str | None
    state: str | None
    budget: Decimal | None
    status: str
    owner_type: str | None
    owner_id: UUID | None
    owner_name: str | None = None
    is_archived: bool
    last_activity: datetime
    created_at: datetime


class IntendedParentStatusHistoryItem(BaseModel):
    """Status history entry."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    old_status: str | None
    new_status: str
    reason: str | None
    changed_by_user_id: UUID | None
    changed_by_name: str | None = None  # Resolved user name
    changed_at: datetime


# =============================================================================
# Stats
# =============================================================================

class IntendedParentStats(BaseModel):
    """IP counts by status."""
    total: int
    by_status: dict[str, int]

