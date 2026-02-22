"""Schemas for application forms and submissions."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


FieldType = Literal[
    "text",
    "textarea",
    "email",
    "phone",
    "number",
    "date",
    "select",
    "multiselect",
    "radio",
    "checkbox",
    "file",
    "address",
    "repeatable_table",
]


class FormFieldOption(BaseModel):
    label: str
    value: str


class FormFieldValidation(BaseModel):
    min_length: int | None = None
    max_length: int | None = None
    min_value: float | None = None
    max_value: float | None = None
    pattern: str | None = None


ConditionOperator = Literal[
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "is_empty",
    "is_not_empty",
]


class FormFieldCondition(BaseModel):
    field_key: str = Field(..., min_length=1, max_length=100)
    operator: ConditionOperator
    value: object | None = None


TableColumnType = Literal["text", "number", "date", "select"]


class FormFieldColumn(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    type: TableColumnType
    required: bool = False
    options: list[FormFieldOption] | None = None
    validation: FormFieldValidation | None = None


class FormField(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    type: FieldType
    required: bool = False
    options: list[FormFieldOption] | None = None
    validation: FormFieldValidation | None = None
    help_text: str | None = None
    show_if: FormFieldCondition | None = None
    columns: list[FormFieldColumn] | None = None
    min_rows: int | None = Field(None, ge=0)
    max_rows: int | None = Field(None, ge=0)


class FormPage(BaseModel):
    title: str | None = None
    fields: list[FormField]


class FormSchema(BaseModel):
    pages: list[FormPage]
    public_title: str | None = Field(None, max_length=200)
    logo_url: str | None = Field(None, max_length=1000)
    privacy_notice: str | None = None


class FormCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    form_schema: FormSchema | None = None
    max_file_size_bytes: int | None = Field(None, ge=1)
    max_file_count: int | None = Field(None, ge=0, le=50)
    allowed_mime_types: list[str] | None = None
    default_application_email_template_id: UUID | None = None


class FormUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    form_schema: FormSchema | None = None
    max_file_size_bytes: int | None = Field(None, ge=1)
    max_file_count: int | None = Field(None, ge=0, le=50)
    allowed_mime_types: list[str] | None = None
    default_application_email_template_id: UUID | None = None


class FormSummary(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class FormRead(FormSummary):
    description: str | None
    form_schema: FormSchema | None
    published_schema: FormSchema | None
    max_file_size_bytes: int
    max_file_count: int
    allowed_mime_types: list[str] | None
    default_application_email_template_id: UUID | None


class FormPublishResponse(BaseModel):
    id: UUID
    status: str
    published_at: datetime


class FormTokenCreate(BaseModel):
    form_id: UUID
    expires_in_days: int = Field(14, ge=1, le=60)


class FormTokenRequest(BaseModel):
    surrogate_id: UUID
    expires_in_days: int = Field(14, ge=1, le=60)


class FormTokenRead(BaseModel):
    token_id: UUID
    token: str
    expires_at: datetime
    application_url: str | None = None


class FormPublicRead(BaseModel):
    form_id: UUID
    name: str
    description: str | None
    form_schema: FormSchema
    max_file_size_bytes: int
    max_file_count: int
    allowed_mime_types: list[str] | None


class FormLogoRead(BaseModel):
    id: UUID
    logo_url: str
    filename: str
    content_type: str
    file_size: int
    created_at: datetime


class FormSubmissionCreate(BaseModel):
    answers: dict[str, object]


class FormSubmissionFileRead(BaseModel):
    id: UUID
    filename: str
    content_type: str
    file_size: int
    quarantined: bool
    scan_status: str
    field_key: str | None = None


class FormSubmissionFileDownloadResponse(BaseModel):
    download_url: str
    filename: str


class FormSubmissionRead(BaseModel):
    id: UUID
    form_id: UUID
    surrogate_id: UUID | None
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None
    reviewed_by_user_id: UUID | None
    review_notes: str | None
    answers: dict[str, object]
    schema_snapshot: dict[str, object] | None
    source_mode: str
    intake_link_id: UUID | None
    intake_lead_id: UUID | None
    match_status: str
    match_reason: str | None
    matched_at: datetime | None
    files: list[FormSubmissionFileRead]


class FormSubmissionPublicResponse(BaseModel):
    id: UUID
    status: str


class FormDeliverySettings(BaseModel):
    default_application_email_template_id: UUID | None = None


class FormDeliverySettingsUpdate(BaseModel):
    default_application_email_template_id: UUID | None = None


class FormSubmissionStatusUpdate(BaseModel):
    review_notes: str | None = None


class FormFieldMappingItem(BaseModel):
    field_key: str = Field(..., min_length=1, max_length=100)
    surrogate_field: str = Field(..., min_length=1, max_length=100)


class FormMappingOption(BaseModel):
    value: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    is_critical: bool = False


class FormFieldMappingsUpdate(BaseModel):
    mappings: list[FormFieldMappingItem]


class FormSubmissionAnswerUpdate(BaseModel):
    """Single field update in a submission."""

    field_key: str = Field(..., min_length=1, max_length=100)
    value: object


class FormSubmissionAnswersUpdate(BaseModel):
    """Batch update for submission answers."""

    updates: list[FormSubmissionAnswerUpdate]


class FormSubmissionAnswersUpdateResponse(BaseModel):
    """Response for submission answer updates."""

    submission: FormSubmissionRead
    surrogate_updates: list[str]  # List of surrogate fields that were updated


# =============================================================================
# Draft Schemas (Public autosave)
# =============================================================================


class FormDraftUpsertRequest(BaseModel):
    answers: dict[str, object] = Field(default_factory=dict)


class FormDraftWriteResponse(BaseModel):
    started_at: datetime | None
    updated_at: datetime


class FormDraftPublicRead(BaseModel):
    answers: dict[str, object]
    started_at: datetime | None
    updated_at: datetime


class FormDraftStatusRead(BaseModel):
    started_at: datetime | None
    updated_at: datetime


FormLinkMode = Literal["dedicated", "shared"]
SharedSubmissionOutcome = Literal["linked", "ambiguous_review", "lead_created"]


class FormIntakeLinkCreate(BaseModel):
    campaign_name: str | None = Field(None, max_length=255)
    event_name: str | None = Field(None, max_length=255)
    expires_at: datetime | None = None
    max_submissions: int | None = Field(None, ge=1, le=100000)
    utm_defaults: dict[str, str] | None = None


class FormIntakeLinkUpdate(BaseModel):
    campaign_name: str | None = Field(None, max_length=255)
    event_name: str | None = Field(None, max_length=255)
    expires_at: datetime | None = None
    max_submissions: int | None = Field(None, ge=1, le=100000)
    utm_defaults: dict[str, str] | None = None
    is_active: bool | None = None


class FormIntakeLinkRead(BaseModel):
    id: UUID
    form_id: UUID
    slug: str
    campaign_name: str | None
    event_name: str | None
    utm_defaults: dict[str, str] | None
    is_active: bool
    expires_at: datetime | None
    max_submissions: int | None
    submissions_count: int
    intake_url: str | None = None
    created_at: datetime
    updated_at: datetime


class FormIntakePublicRead(BaseModel):
    form_id: UUID
    intake_link_id: UUID
    name: str
    description: str | None
    form_schema: FormSchema
    max_file_size_bytes: int
    max_file_count: int
    allowed_mime_types: list[str] | None
    campaign_name: str | None
    event_name: str | None


class FormIntakeDraftPublicRead(BaseModel):
    answers: dict[str, object]
    started_at: datetime | None
    updated_at: datetime


class FormIntakeDraftWriteResponse(BaseModel):
    started_at: datetime | None
    updated_at: datetime


class FormSubmissionSharedResponse(BaseModel):
    id: UUID
    status: str
    outcome: SharedSubmissionOutcome
    surrogate_id: UUID | None = None
    intake_lead_id: UUID | None = None


class MatchCandidateRead(BaseModel):
    id: UUID
    submission_id: UUID
    surrogate_id: UUID
    reason: str
    created_at: datetime


class FormSubmissionMatchResolveRequest(BaseModel):
    surrogate_id: UUID | None = None
    create_intake_lead: bool = False
    review_notes: str | None = None


class FormSubmissionMatchResolveResponse(BaseModel):
    submission: FormSubmissionRead
    outcome: SharedSubmissionOutcome
    candidate_count: int


class IntakeLeadRead(BaseModel):
    id: UUID
    form_id: UUID | None
    intake_link_id: UUID | None
    full_name: str
    email: str | None
    phone: str | None
    date_of_birth: str | None
    status: str
    promoted_surrogate_id: UUID | None
    created_at: datetime
    updated_at: datetime
    promoted_at: datetime | None


class IntakeLeadPromoteRequest(BaseModel):
    source: str | None = None
    is_priority: bool = False
    assign_to_user: bool | None = None


class IntakeLeadPromoteResponse(BaseModel):
    intake_lead_id: UUID
    surrogate_id: UUID
    linked_submission_count: int


class FormTokenSendRequest(BaseModel):
    template_id: UUID | None = None


class FormTokenSendResponse(BaseModel):
    token_id: UUID
    token: str
    template_id: UUID
    email_log_id: UUID
    sent_at: datetime
    application_url: str | None = None
