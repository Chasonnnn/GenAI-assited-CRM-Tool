"""Pydantic contracts for donors."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.utils.normalization import normalize_phone, normalize_state

DonorTypeValue = Literal["egg", "sperm"]


class DonorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    donor_type: DonorTypeValue
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(None, max_length=50)
    state: str | None = Field(None, max_length=100)
    education: str | None = Field(None, max_length=255)
    source: str | None = Field(None, max_length=100)
    owner_type: Literal["user", "queue"] | None = None
    owner_id: UUID | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone_field(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state_field(cls, value: str | None) -> str | None:
        return normalize_state(value)


class DonorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    state: str | None = Field(None, max_length=100)
    education: str | None = Field(None, max_length=255)
    source: str | None = Field(None, max_length=100)
    owner_type: Literal["user", "queue"] | None = None
    owner_id: UUID | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone_field(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state_field(cls, value: str | None) -> str | None:
        return normalize_state(value)


class DonorStatusUpdate(BaseModel):
    stage_id: UUID
    reason: str | None = Field(None, max_length=2000)
    effective_at: datetime | None = Field(
        None, description="When the change actually occurred (optional, defaults to now)"
    )


class DonorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    donor_number: str
    donor_type: DonorTypeValue
    full_name: str
    email: str
    phone: str | None
    state: str | None
    education: str | None
    source: str | None
    owner_type: str | None
    owner_id: UUID | None
    stage_id: UUID
    status: str
    stage_key: str
    stage_slug: str
    status_label: str
    profile_photo_attachment_id: UUID | None
    is_archived: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DonorListResponse(BaseModel):
    items: list[DonorRead]
    total: int
    page: int
    per_page: int
    pages: int


class DonorStatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    donor_id: UUID
    changed_by_user_id: UUID | None
    changed_by_name: str | None = None
    old_stage_id: UUID | None
    new_stage_id: UUID | None
    old_status: str | None
    new_status: str
    old_label_snapshot: str | None
    new_label_snapshot: str
    reason: str | None
    effective_at: datetime
    recorded_at: datetime
    requested_at: datetime | None = None
    approved_by_user_id: UUID | None = None
    approved_by_name: str | None = None
    approved_at: datetime | None = None
    is_undo: bool = False
    request_id: UUID | None = None


class DonorStatusChangeResponse(BaseModel):
    status: Literal["applied", "pending_approval"]
    donor: DonorRead | None = None
    history: DonorStatusHistoryRead | None = None
    request_id: UUID | None = None
    message: str | None = None
