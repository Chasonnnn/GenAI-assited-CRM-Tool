"""Pydantic schemas for email templates and logs."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.email_body_design import validate_body_design

# =============================================================================
# Email Templates
# =============================================================================

EmailTemplateScope = Literal["org", "personal"]
EmailBodyDesign = Annotated[dict[str, Any], AfterValidator(validate_body_design)]


def require_body_with_design(model: BaseModel) -> None:
    """A design is only stored together with the HTML compiled from it."""
    fields = model.model_fields_set
    if "body_design" in fields and getattr(model, "body_design") is not None:
        if "body" not in fields or getattr(model, "body") is None:
            raise ValueError("body_design must be sent with the body compiled from it")


class EmailTemplateCreate(BaseModel):
    """Create a new email template."""

    name: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=200)
    from_email: str | None = Field(
        None,
        max_length=200,
        description="Optional per-template From header override (e.g., 'Surrogacy Force <invites@surrogacyforce.com>').",
    )
    body: str = Field(min_length=1, max_length=50000)
    body_design: EmailBodyDesign | None = None
    scope: EmailTemplateScope = Field(
        default="org",
        description="Template scope: 'org' for shared templates, 'personal' for user-owned",
    )


class EmailTemplateUpdate(BaseModel):
    """Update an email template."""

    name: str | None = Field(None, min_length=1, max_length=100)
    subject: str | None = Field(None, min_length=1, max_length=200)
    from_email: str | None = Field(
        None,
        max_length=200,
        description="Optional per-template From header override (e.g., 'Surrogacy Force <invites@surrogacyforce.com>').",
    )
    body: str | None = Field(None, min_length=1, max_length=50000)
    body_design: EmailBodyDesign | None = None
    is_active: bool | None = None
    expected_version: int | None = Field(None, description="Required for optimistic locking")

    @model_validator(mode="after")
    def design_needs_body(self):
        require_body_with_design(self)
        return self


class EmailTemplateRead(BaseModel):
    """Email template response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    name: str
    subject: str
    from_email: str | None
    body: str
    body_design: dict[str, Any] | None = None
    is_active: bool
    scope: str = "org"
    owner_user_id: UUID | None = None
    owner_name: str | None = None  # Populated by service
    source_template_id: UUID | None = None
    proposed_by_user_id: UUID | None = None
    proposed_by_name: str | None = None
    capabilities: dict[str, bool] | None = None
    is_system_template: bool = False
    current_version: int  # For optimistic locking
    created_at: datetime
    updated_at: datetime


class EmailTemplateListItem(BaseModel):
    """Email template list item (minimal)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    subject: str
    from_email: str | None
    is_active: bool
    scope: str = "org"
    owner_user_id: UUID | None = None
    owner_name: str | None = None  # Populated by service
    proposed_by_name: str | None = None
    capabilities: dict[str, bool] | None = None
    is_system_template: bool = False
    created_at: datetime
    updated_at: datetime


class EmailTemplateCopyRequest(BaseModel):
    """Request to copy an org/system template to personal."""

    name: str = Field(min_length=1, max_length=100)


class EmailTemplateShareRequest(BaseModel):
    """Request to share a personal template with the organization."""

    name: str = Field(min_length=1, max_length=100)


# =============================================================================
# Template Variables Catalog
# =============================================================================


class TemplateVariableRead(BaseModel):
    """Template variable definition (name + metadata)."""

    name: str
    description: str
    category: str
    required: bool = False
    value_type: str = "text"  # "text" | "url" | "html"
    html_safe: bool = False


# =============================================================================
# Email Logs
# =============================================================================


class EmailSendRequest(BaseModel):
    """Request to send an email from a template."""

    idempotency_key: str = Field(min_length=1, max_length=256)
    template_id: UUID
    recipient_email: EmailStr
    variables: dict[str, str] = {}
    surrogate_id: UUID | None = None
    schedule_at: datetime | None = None


class EmailTemplateTestSendRequest(BaseModel):
    """Request to send a test email using an email template."""

    to_email: EmailStr
    variables: dict[str, str] = {}
    idempotency_key: str = Field(min_length=1, max_length=256)
    # Test-only: allows sending even if the recipient opted out of marketing emails.
    # Bounces/complaints remain suppressed.
    ignore_opt_out: bool = False


class PlatformEmailTemplateTestSendRequest(BaseModel):
    """Request to send a test email using a platform email template for a specific org."""

    org_id: UUID
    to_email: EmailStr
    variables: dict[str, str] = {}
    idempotency_key: str = Field(min_length=1, max_length=256)


class EmailTemplatePreviewRequest(BaseModel):
    """Unsaved template content to render through the send composition."""

    subject: str = Field(default="", max_length=200)
    body: str = Field(default="", max_length=50000)
    scope: EmailTemplateScope = "org"
    variable_mode: Literal["sample", "names", "record"] = "sample"
    surrogate_id: UUID | None = None

    @model_validator(mode="after")
    def record_needs_surrogate(self) -> EmailTemplatePreviewRequest:
        if self.variable_mode == "record" and self.surrogate_id is None:
            raise ValueError("surrogate_id is required for record previews")
        return self


class PlatformEmailTemplatePreviewRequest(BaseModel):
    """Unsaved platform template content to render as its test send does."""

    subject: str = Field(default="", max_length=200)
    body: str = Field(default="", max_length=50000)
    variable_mode: Literal["sample", "names"] = "sample"
    org_id: UUID | None = None


class EmailTemplatePreviewResponse(BaseModel):
    """Rendered preview document for a sandboxed iframe."""

    subject: str
    html: str
    unresolved_variables: list[str]


class EmailTemplateTestSendResponse(BaseModel):
    """Response after sending a test email."""

    success: bool
    queued: bool = False
    provider_used: Literal["resend", "gmail"] | None = None
    email_log_id: UUID | None = None
    message_id: str | None = None
    error: str | None = None
    error_code: Literal["idempotency_conflict"] | None = None


class EmailLogRead(BaseModel):
    """Email log response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    job_id: UUID | None
    template_id: UUID | None
    surrogate_id: UUID | None
    recipient_email: str
    subject: str
    body: str
    status: str
    sent_at: datetime | None
    error: str | None
    created_at: datetime


class EmailLogListItem(BaseModel):
    """Email log list item (minimal)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID | None
    surrogate_id: UUID | None
    recipient_email: str
    subject: str
    status: str
    sent_at: datetime | None
    created_at: datetime
