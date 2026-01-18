"""Pydantic schemas for surrogates."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.db.enums import SurrogateSource, OwnerType
from app.utils.normalization import normalize_phone, normalize_state


class SurrogateCreate(BaseModel):
    """Request schema for creating a surrogate."""

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
    source: SurrogateSource = SurrogateSource.MANUAL
    is_priority: bool = False
    assign_to_user: bool | None = None

    # =========================================================================
    # INSURANCE INFO
    # =========================================================================
    insurance_company: str | None = Field(None, max_length=255)
    insurance_plan_name: str | None = Field(None, max_length=255)
    insurance_phone: str | None = None
    insurance_policy_number: str | None = None
    insurance_member_id: str | None = None
    insurance_group_number: str | None = Field(None, max_length=100)
    insurance_subscriber_name: str | None = None
    insurance_subscriber_dob: date | None = None

    # =========================================================================
    # IVF CLINIC
    # =========================================================================
    clinic_name: str | None = Field(None, max_length=255)
    clinic_address_line1: str | None = None
    clinic_address_line2: str | None = None
    clinic_city: str | None = Field(None, max_length=100)
    clinic_state: str | None = None
    clinic_postal: str | None = Field(None, max_length=20)
    clinic_phone: str | None = None
    clinic_email: EmailStr | None = None

    # =========================================================================
    # MONITORING CLINIC
    # =========================================================================
    monitoring_clinic_name: str | None = Field(None, max_length=255)
    monitoring_clinic_address_line1: str | None = None
    monitoring_clinic_address_line2: str | None = None
    monitoring_clinic_city: str | None = Field(None, max_length=100)
    monitoring_clinic_state: str | None = None
    monitoring_clinic_postal: str | None = Field(None, max_length=20)
    monitoring_clinic_phone: str | None = None
    monitoring_clinic_email: EmailStr | None = None

    # =========================================================================
    # OB PROVIDER
    # =========================================================================
    ob_provider_name: str | None = Field(None, max_length=255)
    ob_clinic_name: str | None = Field(None, max_length=255)
    ob_address_line1: str | None = None
    ob_address_line2: str | None = None
    ob_city: str | None = Field(None, max_length=100)
    ob_state: str | None = None
    ob_postal: str | None = Field(None, max_length=20)
    ob_phone: str | None = None
    ob_email: EmailStr | None = None

    # =========================================================================
    # DELIVERY HOSPITAL
    # =========================================================================
    delivery_hospital_name: str | None = Field(None, max_length=255)
    delivery_hospital_address_line1: str | None = None
    delivery_hospital_address_line2: str | None = None
    delivery_hospital_city: str | None = Field(None, max_length=100)
    delivery_hospital_state: str | None = None
    delivery_hospital_postal: str | None = Field(None, max_length=20)
    delivery_hospital_phone: str | None = None
    delivery_hospital_email: EmailStr | None = None

    # =========================================================================
    # PREGNANCY TRACKING
    # =========================================================================
    pregnancy_start_date: date | None = None
    pregnancy_due_date: date | None = None
    actual_delivery_date: date | None = None

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

    @field_validator(
        "insurance_phone",
        "clinic_phone",
        "monitoring_clinic_phone",
        "ob_phone",
        "delivery_hospital_phone",
    )
    @classmethod
    def validate_optional_phone(cls, v: str | None) -> str | None:
        """Normalize and validate optional phone fields to E.164."""
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return normalize_phone(v)

    @field_validator(
        "clinic_state",
        "monitoring_clinic_state",
        "ob_state",
        "delivery_hospital_state",
    )
    @classmethod
    def validate_optional_state(cls, v: str | None) -> str | None:
        """Normalize and validate optional state fields to 2-letter code."""
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return normalize_state(v)


class SurrogateUpdate(BaseModel):
    """Request schema for updating a surrogate (partial)."""

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

    # =========================================================================
    # INSURANCE INFO
    # =========================================================================
    insurance_company: str | None = Field(None, max_length=255)
    insurance_plan_name: str | None = Field(None, max_length=255)
    insurance_phone: str | None = None
    insurance_policy_number: str | None = None
    insurance_member_id: str | None = None
    insurance_group_number: str | None = Field(None, max_length=100)
    insurance_subscriber_name: str | None = None
    insurance_subscriber_dob: date | None = None

    # =========================================================================
    # IVF CLINIC
    # =========================================================================
    clinic_name: str | None = Field(None, max_length=255)
    clinic_address_line1: str | None = None
    clinic_address_line2: str | None = None
    clinic_city: str | None = Field(None, max_length=100)
    clinic_state: str | None = None
    clinic_postal: str | None = Field(None, max_length=20)
    clinic_phone: str | None = None
    clinic_email: EmailStr | None = None

    # =========================================================================
    # MONITORING CLINIC
    # =========================================================================
    monitoring_clinic_name: str | None = Field(None, max_length=255)
    monitoring_clinic_address_line1: str | None = None
    monitoring_clinic_address_line2: str | None = None
    monitoring_clinic_city: str | None = Field(None, max_length=100)
    monitoring_clinic_state: str | None = None
    monitoring_clinic_postal: str | None = Field(None, max_length=20)
    monitoring_clinic_phone: str | None = None
    monitoring_clinic_email: EmailStr | None = None

    # =========================================================================
    # OB PROVIDER
    # =========================================================================
    ob_provider_name: str | None = Field(None, max_length=255)
    ob_clinic_name: str | None = Field(None, max_length=255)
    ob_address_line1: str | None = None
    ob_address_line2: str | None = None
    ob_city: str | None = Field(None, max_length=100)
    ob_state: str | None = None
    ob_postal: str | None = Field(None, max_length=20)
    ob_phone: str | None = None
    ob_email: EmailStr | None = None

    # =========================================================================
    # DELIVERY HOSPITAL
    # =========================================================================
    delivery_hospital_name: str | None = Field(None, max_length=255)
    delivery_hospital_address_line1: str | None = None
    delivery_hospital_address_line2: str | None = None
    delivery_hospital_city: str | None = Field(None, max_length=100)
    delivery_hospital_state: str | None = None
    delivery_hospital_postal: str | None = Field(None, max_length=20)
    delivery_hospital_phone: str | None = None
    delivery_hospital_email: EmailStr | None = None

    # =========================================================================
    # PREGNANCY TRACKING
    # =========================================================================
    pregnancy_start_date: date | None = None
    pregnancy_due_date: date | None = None
    actual_delivery_date: date | None = None

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

    @field_validator(
        "insurance_phone",
        "clinic_phone",
        "monitoring_clinic_phone",
        "ob_phone",
        "delivery_hospital_phone",
    )
    @classmethod
    def validate_optional_phone(cls, v: str | None) -> str | None:
        """Normalize and validate optional phone fields to E.164."""
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return normalize_phone(v)

    @field_validator(
        "clinic_state",
        "monitoring_clinic_state",
        "ob_state",
        "delivery_hospital_state",
    )
    @classmethod
    def validate_optional_state(cls, v: str | None) -> str | None:
        """Normalize and validate optional state fields to 2-letter code."""
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return normalize_state(v)


class BulkAssign(BaseModel):
    """Request schema for bulk surrogateassignment."""

    surrogate_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    owner_type: OwnerType
    owner_id: UUID


class SurrogateRead(BaseModel):
    """Full surrogateresponse for detail views."""

    id: UUID
    surrogate_number: str
    stage_id: UUID
    status_label: str
    source: SurrogateSource
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

    # =========================================================================
    # INSURANCE INFO
    # =========================================================================
    insurance_company: str | None = None
    insurance_plan_name: str | None = None
    insurance_phone: str | None = None
    insurance_policy_number: str | None = None
    insurance_member_id: str | None = None
    insurance_group_number: str | None = None
    insurance_subscriber_name: str | None = None
    insurance_subscriber_dob: date | None = None

    # =========================================================================
    # IVF CLINIC
    # =========================================================================
    clinic_name: str | None = None
    clinic_address_line1: str | None = None
    clinic_address_line2: str | None = None
    clinic_city: str | None = None
    clinic_state: str | None = None
    clinic_postal: str | None = None
    clinic_phone: str | None = None
    clinic_email: str | None = None

    # =========================================================================
    # MONITORING CLINIC
    # =========================================================================
    monitoring_clinic_name: str | None = None
    monitoring_clinic_address_line1: str | None = None
    monitoring_clinic_address_line2: str | None = None
    monitoring_clinic_city: str | None = None
    monitoring_clinic_state: str | None = None
    monitoring_clinic_postal: str | None = None
    monitoring_clinic_phone: str | None = None
    monitoring_clinic_email: str | None = None

    # =========================================================================
    # OB PROVIDER
    # =========================================================================
    ob_provider_name: str | None = None
    ob_clinic_name: str | None = None
    ob_address_line1: str | None = None
    ob_address_line2: str | None = None
    ob_city: str | None = None
    ob_state: str | None = None
    ob_postal: str | None = None
    ob_phone: str | None = None
    ob_email: str | None = None

    # =========================================================================
    # DELIVERY HOSPITAL
    # =========================================================================
    delivery_hospital_name: str | None = None
    delivery_hospital_address_line1: str | None = None
    delivery_hospital_address_line2: str | None = None
    delivery_hospital_city: str | None = None
    delivery_hospital_state: str | None = None
    delivery_hospital_postal: str | None = None
    delivery_hospital_phone: str | None = None
    delivery_hospital_email: str | None = None

    # =========================================================================
    # PREGNANCY TRACKING
    # =========================================================================
    pregnancy_start_date: date | None = None
    pregnancy_due_date: date | None = None
    actual_delivery_date: date | None = None

    # Soft delete
    is_archived: bool
    archived_at: datetime | None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SurrogateListItem(BaseModel):
    """Compact surrogatefor table views."""

    id: UUID
    surrogate_number: str
    stage_id: UUID
    stage_slug: str | None = None
    stage_type: str | None = None
    status_label: str
    source: SurrogateSource
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
    last_activity_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SurrogateListResponse(BaseModel):
    """Paginated surrogatelist response."""

    items: list[SurrogateListItem]
    total: int
    page: int
    per_page: int
    pages: int


class SurrogateStatusChange(BaseModel):
    """Request to change surrogate stage with optional backdating.

    effective_at: When the change actually occurred.
        - If None or not provided: effective now
        - If date is today with no time: effective_at = now
        - If date is past with no time: default to 12:00 PM org timezone

    reason: Required for backdated changes and regressions.
    """

    stage_id: UUID
    reason: str | None = Field(None, max_length=500)
    effective_at: datetime | None = Field(
        None, description="When the change actually occurred (optional, defaults to now)"
    )


class SurrogateStatusChangeResponse(BaseModel):
    """Response for a status change request.

    status: 'applied' if change was applied, 'pending_approval' if regression needs admin approval.
    """

    status: str  # 'applied' or 'pending_approval'
    surrogate: "SurrogateRead | None" = None
    request_id: UUID | None = None
    message: str | None = None


class SurrogateAssign(BaseModel):
    """Request to assign surrogate to a user or queue."""

    owner_type: OwnerType
    owner_id: UUID


class SurrogateStatusHistoryRead(BaseModel):
    """Status history entry response with dual timestamps for backdating support."""

    id: UUID
    from_stage_id: UUID | None
    to_stage_id: UUID | None
    from_label_snapshot: str | None
    to_label_snapshot: str | None
    changed_by_user_id: UUID | None
    changed_by_name: str | None = None
    reason: str | None
    changed_at: datetime  # Legacy, derived from effective_at

    # Dual timestamps for backdating
    effective_at: datetime | None = None  # When it actually happened
    recorded_at: datetime | None = None  # When recorded in system

    # Audit fields for approval flow
    requested_at: datetime | None = None
    approved_by_user_id: UUID | None = None
    approved_by_name: str | None = None
    approved_at: datetime | None = None
    is_undo: bool = False
    request_id: UUID | None = None

    model_config = {"from_attributes": True}


class SurrogateStats(BaseModel):
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


class SurrogateActivityRead(BaseModel):
    """Response schema for surrogateactivity log entry."""

    id: UUID
    activity_type: str
    actor_user_id: UUID | None
    actor_name: str | None  # Resolved at read-time
    details: dict | None
    created_at: datetime


class SurrogateActivityResponse(BaseModel):
    """Paginated response for surrogateactivity log."""

    items: list[SurrogateActivityRead]
    total: int
    page: int
    pages: int


# =============================================================================
# Contact Attempts Tracking
# =============================================================================


class ContactAttemptCreate(BaseModel):
    """Request schema for logging a contact attempt."""

    contact_methods: list[str] = Field(..., min_length=1, max_length=3)
    outcome: str
    notes: str | None = Field(None, max_length=5000)
    attempted_at: datetime | None = None  # Optional: defaults to now() if not provided

    @field_validator("contact_methods")
    @classmethod
    def validate_methods(cls, v: list[str]) -> list[str]:
        """Validate contact methods are valid."""
        valid_methods = {"phone", "email", "sms"}
        for method in v:
            if method not in valid_methods:
                raise ValueError(f"Invalid contact method: {method}")
        return v

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        """Validate outcome is valid."""
        valid_outcomes = {"reached", "no_answer", "voicemail", "wrong_number", "email_bounced"}
        if v not in valid_outcomes:
            raise ValueError(f"Invalid outcome: {v}")
        return v


class ContactAttemptResponse(BaseModel):
    """Response schema for a contact attempt."""

    id: UUID
    surrogate_id: UUID
    attempted_by_user_id: UUID | None
    attempted_by_name: str | None
    contact_methods: list[str]
    outcome: str
    notes: str | None
    attempted_at: datetime
    created_at: datetime
    is_backdated: bool
    surrogate_owner_id_at_attempt: UUID

    model_config = {"from_attributes": True}


class ContactAttemptsSummary(BaseModel):
    """Summary of contact attempts for a surrogate."""

    total_attempts: int  # All attempts in history
    current_assignment_attempts: int  # Attempts since latest owner assignment
    distinct_days_current_assignment: int  # Distinct calendar days (org timezone)
    successful_attempts: int
    last_attempt_at: datetime | None
    days_since_last_attempt: int | None
    attempts: list[ContactAttemptResponse]  # All attempts, ordered by attempted_at DESC
