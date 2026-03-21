"""Pydantic schemas for Intended Parents."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.utils.normalization import normalize_phone, normalize_state

EggSource = Literal["intended_mother", "egg_donor"]
SpermSource = Literal["intended_father", "sperm_donor"]
TrustFundingStatus = Literal["pending_funding", "funded", "needs_replenishment", "closed"]
MaritalStatus = Literal[
    "Single",
    "Married",
    "Partnered",
    "Committed Relationship",
    "Divorced",
    "Separated",
    "Widowed",
]


# =============================================================================
# Create / Update
# =============================================================================


class IntendedParentCreate(BaseModel):
    """Schema for creating an intended parent."""

    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(None, max_length=50)
    state: str | None = Field(None, max_length=100)
    budget: Decimal | None = Field(None, ge=0, le=9999999999.99)
    notes_internal: str | None = Field(None, max_length=10000)
    owner_type: str | None = None  # "user" or "queue"
    owner_id: UUID | None = None

    # Partner
    partner_name: str | None = Field(None, max_length=255)
    partner_email: EmailStr | None = None

    # Pronouns
    pronouns: str | None = Field(None, max_length=50)
    partner_pronouns: str | None = Field(None, max_length=50)
    date_of_birth: date | None = None
    partner_date_of_birth: date | None = None
    marital_status: MaritalStatus | None = None
    embryo_count: int | None = Field(None, ge=0, le=99)
    pgs_tested: bool | None = None
    egg_source: EggSource | None = None
    sperm_source: SpermSource | None = None
    trust_provider_name: str | None = Field(None, max_length=255)
    trust_primary_contact_name: str | None = Field(None, max_length=255)
    trust_email: EmailStr | None = None
    trust_phone: str | None = None
    trust_address_line1: str | None = None
    trust_address_line2: str | None = None
    trust_city: str | None = Field(None, max_length=100)
    trust_state: str | None = None
    trust_postal: str | None = Field(None, max_length=20)
    trust_case_reference: str | None = Field(None, max_length=255)
    trust_funding_status: TrustFundingStatus | None = None
    trust_portal_url: str | None = Field(None, max_length=2000)
    trust_notes: str | None = Field(None, max_length=10000)

    # Address
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = Field(None, max_length=100)
    postal: str | None = Field(None, max_length=20)

    # IVF Clinic
    ip_clinic_name: str | None = Field(None, max_length=255)
    ip_clinic_address_line1: str | None = None
    ip_clinic_address_line2: str | None = None
    ip_clinic_city: str | None = Field(None, max_length=100)
    ip_clinic_state: str | None = None
    ip_clinic_postal: str | None = Field(None, max_length=20)
    ip_clinic_phone: str | None = None
    ip_clinic_fax: str | None = None
    ip_clinic_email: EmailStr | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone_field(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else None

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state_field(cls, v: str | None) -> str | None:
        return normalize_state(v)  # Raises ValueError on invalid

    @field_validator("ip_clinic_state", "trust_state", mode="before")
    @classmethod
    def normalize_optional_state(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return normalize_state(v)

    @field_validator("ip_clinic_phone", "ip_clinic_fax", "trust_phone", mode="before")
    @classmethod
    def normalize_optional_phone(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return normalize_phone(v)


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

    # Partner
    partner_name: str | None = Field(None, max_length=255)
    partner_email: EmailStr | None = None

    # Pronouns
    pronouns: str | None = Field(None, max_length=50)
    partner_pronouns: str | None = Field(None, max_length=50)
    date_of_birth: date | None = None
    partner_date_of_birth: date | None = None
    marital_status: MaritalStatus | None = None
    embryo_count: int | None = Field(None, ge=0, le=99)
    pgs_tested: bool | None = None
    egg_source: EggSource | None = None
    sperm_source: SpermSource | None = None
    trust_provider_name: str | None = Field(None, max_length=255)
    trust_primary_contact_name: str | None = Field(None, max_length=255)
    trust_email: EmailStr | None = None
    trust_phone: str | None = None
    trust_address_line1: str | None = None
    trust_address_line2: str | None = None
    trust_city: str | None = Field(None, max_length=100)
    trust_state: str | None = None
    trust_postal: str | None = Field(None, max_length=20)
    trust_case_reference: str | None = Field(None, max_length=255)
    trust_funding_status: TrustFundingStatus | None = None
    trust_portal_url: str | None = Field(None, max_length=2000)
    trust_notes: str | None = Field(None, max_length=10000)

    # Address
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = Field(None, max_length=100)
    postal: str | None = Field(None, max_length=20)

    # IVF Clinic
    ip_clinic_name: str | None = Field(None, max_length=255)
    ip_clinic_address_line1: str | None = None
    ip_clinic_address_line2: str | None = None
    ip_clinic_city: str | None = Field(None, max_length=100)
    ip_clinic_state: str | None = None
    ip_clinic_postal: str | None = Field(None, max_length=20)
    ip_clinic_phone: str | None = None
    ip_clinic_fax: str | None = None
    ip_clinic_email: EmailStr | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone_field(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else None

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state_field(cls, v: str | None) -> str | None:
        return normalize_state(v)

    @field_validator("ip_clinic_state", "trust_state", mode="before")
    @classmethod
    def normalize_optional_state(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return normalize_state(v)

    @field_validator("ip_clinic_phone", "ip_clinic_fax", "trust_phone", mode="before")
    @classmethod
    def normalize_optional_phone(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return normalize_phone(v)


class IntendedParentStatusUpdate(BaseModel):
    """Schema for changing status."""

    stage_id: UUID
    reason: str | None = Field(None, max_length=500)
    effective_at: datetime | None = Field(
        None, description="When the change actually occurred (optional, defaults to now)"
    )


# =============================================================================
# Read / Response
# =============================================================================


class IntendedParentRead(BaseModel):
    """Full intended parent details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    intended_parent_number: str
    full_name: str
    email: str
    phone: str | None
    state: str | None
    budget: Decimal | None
    notes_internal: str | None
    status: str
    stage_id: UUID | None = None
    stage_key: str | None = None
    stage_slug: str | None = None
    status_label: str | None = None
    owner_type: str | None
    owner_id: UUID | None
    owner_name: str | None = None  # Resolved from user/queue

    # Partner
    partner_name: str | None = None
    partner_email: str | None = None

    # Pronouns
    pronouns: str | None = None
    partner_pronouns: str | None = None
    date_of_birth: date | None = None
    partner_date_of_birth: date | None = None
    marital_status: str | None = None
    embryo_count: int | None = None
    pgs_tested: bool | None = None
    egg_source: EggSource | None = None
    sperm_source: SpermSource | None = None
    trust_provider_name: str | None = None
    trust_primary_contact_name: str | None = None
    trust_email: str | None = None
    trust_phone: str | None = None
    trust_address_line1: str | None = None
    trust_address_line2: str | None = None
    trust_city: str | None = None
    trust_state: str | None = None
    trust_postal: str | None = None
    trust_case_reference: str | None = None
    trust_funding_status: TrustFundingStatus | None = None
    trust_portal_url: str | None = None
    trust_notes: str | None = None

    # Address
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    postal: str | None = None

    # IVF Clinic
    ip_clinic_name: str | None = None
    ip_clinic_address_line1: str | None = None
    ip_clinic_address_line2: str | None = None
    ip_clinic_city: str | None = None
    ip_clinic_state: str | None = None
    ip_clinic_postal: str | None = None
    ip_clinic_phone: str | None = None
    ip_clinic_fax: str | None = None
    ip_clinic_email: str | None = None

    is_archived: bool
    archived_at: datetime | None
    last_activity: datetime
    created_at: datetime
    updated_at: datetime


class IntendedParentListItem(BaseModel):
    """Minimal fields for list view."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    intended_parent_number: str
    full_name: str
    email: str
    phone: str | None
    state: str | None
    budget: Decimal | None
    status: str
    stage_id: UUID | None = None
    stage_key: str | None = None
    stage_slug: str | None = None
    status_label: str | None = None
    owner_type: str | None
    owner_id: UUID | None
    owner_name: str | None = None
    partner_name: str | None = None
    is_archived: bool
    last_activity: datetime
    created_at: datetime


class IntendedParentStatusHistoryItem(BaseModel):
    """Status history entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    old_stage_id: UUID | None = None
    new_stage_id: UUID | None = None
    old_status: str | None
    new_status: str
    reason: str | None
    changed_by_user_id: UUID | None
    changed_by_name: str | None = None  # Resolved user name
    changed_at: datetime
    effective_at: datetime | None = None
    recorded_at: datetime | None = None
    requested_at: datetime | None = None
    approved_by_user_id: UUID | None = None
    approved_by_name: str | None = None
    approved_at: datetime | None = None
    is_undo: bool = False
    request_id: UUID | None = None


class IntendedParentStatusChangeResponse(BaseModel):
    """Response for a status change request."""

    status: str  # 'applied' or 'pending_approval'
    intended_parent: IntendedParentRead | None = None
    request_id: UUID | None = None
    message: str | None = None


# =============================================================================
# Stats
# =============================================================================


class IntendedParentStats(BaseModel):
    """IP counts by status."""

    total: int
    by_status: dict[str, int]
