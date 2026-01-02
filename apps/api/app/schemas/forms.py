"""Schemas for application forms and submissions."""

from datetime import datetime
from typing import Any, Literal
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


class FormField(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    type: FieldType
    required: bool = False
    options: list[FormFieldOption] | None = None
    validation: FormFieldValidation | None = None
    help_text: str | None = None


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


class FormUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    form_schema: FormSchema | None = None
    max_file_size_bytes: int | None = Field(None, ge=1)
    max_file_count: int | None = Field(None, ge=0, le=50)
    allowed_mime_types: list[str] | None = None


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


class FormPublishResponse(BaseModel):
    id: UUID
    status: str
    published_at: datetime


class FormTokenCreate(BaseModel):
    form_id: UUID
    expires_in_days: int = Field(14, ge=1, le=60)


class FormTokenRequest(BaseModel):
    case_id: UUID
    expires_in_days: int = Field(14, ge=1, le=60)


class FormTokenRead(BaseModel):
    token: str
    expires_at: datetime


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
    answers: dict[str, Any]


class FormSubmissionFileRead(BaseModel):
    id: UUID
    filename: str
    content_type: str
    file_size: int
    quarantined: bool
    scan_status: str


class FormSubmissionFileDownloadResponse(BaseModel):
    download_url: str
    filename: str


class FormSubmissionRead(BaseModel):
    id: UUID
    form_id: UUID
    case_id: UUID
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None
    reviewed_by_user_id: UUID | None
    review_notes: str | None
    answers: dict[str, Any]
    schema_snapshot: dict | None
    files: list[FormSubmissionFileRead]


class FormSubmissionPublicResponse(BaseModel):
    id: UUID
    status: str


class FormSubmissionStatusUpdate(BaseModel):
    review_notes: str | None = None


class FormFieldMappingItem(BaseModel):
    field_key: str = Field(..., min_length=1, max_length=100)
    case_field: str = Field(..., min_length=1, max_length=100)


class FormFieldMappingsUpdate(BaseModel):
    mappings: list[FormFieldMappingItem]


class FormSubmissionAnswerUpdate(BaseModel):
    """Single field update in a submission."""
    field_key: str = Field(..., min_length=1, max_length=100)
    value: Any


class FormSubmissionAnswersUpdate(BaseModel):
    """Batch update for submission answers."""
    updates: list[FormSubmissionAnswerUpdate]


class FormSubmissionAnswersUpdateResponse(BaseModel):
    """Response for submission answer updates."""
    submission: FormSubmissionRead
    case_updates: list[str]  # List of case fields that were updated
