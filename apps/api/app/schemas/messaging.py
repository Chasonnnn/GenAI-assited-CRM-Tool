"""API contracts for organization-scoped messaging consent administration."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.normalization import normalize_phone

MessagingPurpose = Literal["operational", "promotional"]
MessagingConsentStatus = Literal["unknown", "opted_in", "opted_out", "reopt_pending"]


class MessagingConsentEvidenceInput(BaseModel):
    phone: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=50)
    source_reference: str = Field(min_length=1, max_length=255)
    occurred_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=255)
    evidence_metadata: dict = Field(default_factory=dict)
    intake_lead_id: UUID | None = None
    meta_lead_id: UUID | None = None
    surrogate_id: UUID | None = None

    @field_validator("phone")
    @classmethod
    def normalize_recipient_phone(cls, value: str) -> str:
        normalized = normalize_phone(value)
        if normalized is None:
            raise ValueError("Phone number is required")
        return normalized

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class MessagingConsentImportRequest(MessagingConsentEvidenceInput):
    purpose: MessagingPurpose
    affirmative: bool = False
    disclosure_text: str | None = Field(default=None, max_length=4000)


class MessagingConsentRevocationRequest(MessagingConsentEvidenceInput):
    instruction_text: str = Field(min_length=1, max_length=4000)
    route_purpose: MessagingPurpose


class MessagingConsentTransitionResponse(BaseModel):
    contact_id: UUID
    phone_last4: str
    purpose_states: dict[MessagingPurpose, MessagingConsentStatus]
    global_suppression_active: bool
    global_suppression_reason: Literal["none", "global_opt_out", "ambiguous_hold"]
    evidence_id: UUID | None
    classification: str | None


MessagingContentClassification = Literal["no_phi", "phi"]
MessagingTemplateStatus = Literal["draft", "published", "retired"]
MessagingMediaScanStatus = Literal["pending", "clean", "quarantined", "rejected"]


class MessagingTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    purpose: MessagingPurpose
    body: str = Field(min_length=1, max_length=1600)
    is_enrollment_confirmation: bool = False
    content_classification: MessagingContentClassification = "no_phi"


class MessagingTemplateNextVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    purpose: MessagingPurpose | None = None
    body: str | None = Field(default=None, min_length=1, max_length=1600)
    is_enrollment_confirmation: bool | None = None
    content_classification: MessagingContentClassification | None = None


class MessagingTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_key: UUID
    version: int
    name: str
    purpose: MessagingPurpose
    body: str
    content_hash: str
    status: MessagingTemplateStatus
    is_enrollment_confirmation: bool
    content_classification: MessagingContentClassification
    published_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime


class MessagingMediaAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str | None
    content_type: str
    byte_size: int
    checksum_sha256: str
    scan_status: MessagingMediaScanStatus
    quarantine_reason: str | None
    content_classification: MessagingContentClassification
    created_at: datetime


class MessagingMediaAccessResponse(BaseModel):
    url: str
    expires_at: datetime
    content_type: str
    byte_size: int


class MessagingPreferenceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["opt_in", "opt_out"]
    purposes: list[MessagingPurpose] = Field(min_length=1, max_length=2)
    affirmative: bool = False
    submission_id: UUID

    @field_validator("purposes")
    @classmethod
    def require_unique_purposes(cls, value: list[MessagingPurpose]) -> list[MessagingPurpose]:
        if len(value) != len(set(value)):
            raise ValueError("Purposes must be unique")
        return value


class MessagingPreferencePurposeResponse(BaseModel):
    disclosure: str
    status: MessagingConsentStatus


class MessagingPreferenceResponse(BaseModel):
    legal_brand: str
    masked_phone: str
    support_contact: str
    expected_frequency: str | None
    sms_terms_url: str
    privacy_policy_url: str
    purposes: dict[MessagingPurpose, MessagingPreferencePurposeResponse]
    global_suppression_active: bool
    expires_at: datetime
