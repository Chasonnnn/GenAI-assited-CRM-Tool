"""Pydantic contracts for donors."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.db.enums import SurrogateSource
from app.schemas.donor_profile import DonorProfileUpdate
from app.utils.normalization import normalize_phone, normalize_state

DonorTypeValue = Literal["egg", "sperm"]

# Donor source shares the surrogate source vocabulary. Hosted and embedded CRM
# form intake historically wrote its routing path; every such donor is a website donor.
DONOR_WEBSITE_SOURCE_ALIASES = frozenset(
    {
        "shared_intake",
        "form_embed",
        "website_intake",
        "website_embed",
        "manual_review_resolution",
        "manual_retry_resolution",
    }
)
DONOR_SOURCE_VALUES = frozenset(source.value for source in SurrogateSource)


def normalize_donor_source(value: object) -> str | None:
    """Return the canonical lowercase source value, or raise for an unknown source."""
    if value is None:
        return None
    if isinstance(value, SurrogateSource):
        return value.value
    if not isinstance(value, str):
        raise ValueError("Donor source must be text")
    key = value.strip().lower()
    if not key:
        return None
    if key in DONOR_SOURCE_VALUES:
        return key
    if key in DONOR_WEBSITE_SOURCE_ALIASES:
        return SurrogateSource.WEBSITE.value
    raise ValueError(
        "Invalid donor source. Use one of: " + ", ".join(source.value for source in SurrogateSource)
    )


class DonorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    donor_type: DonorTypeValue
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(None, max_length=50)
    state: str | None = Field(None, max_length=100)
    education: str | None = Field(None, max_length=255)
    source: str = Field(SurrogateSource.MANUAL.value, max_length=100)
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

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source_field(cls, value: object) -> str:
        return normalize_donor_source(value) or SurrogateSource.MANUAL.value


class DonorUpdate(DonorProfileUpdate):
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

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source_field(cls, value: object) -> str | None:
        return normalize_donor_source(value)


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
    owner_name: str | None = None
    can_claim: bool = False
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


class DonorMetaLeadAnswer(BaseModel):
    key: str
    label: str | None = None
    value: str


class DonorMetaLeadRead(BaseModel):
    """Read-only answers of the Meta lead a donor was converted from."""

    id: UUID
    form_name: str | None
    meta_created_time: datetime | None
    received_at: datetime
    answers: list[DonorMetaLeadAnswer]
    dropped_fields: list[str] = Field(default_factory=list)
