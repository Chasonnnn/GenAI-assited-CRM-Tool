"""Pydantic schemas for email templates and logs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =============================================================================
# Email Templates
# =============================================================================

EmailTemplateScope = Literal["org", "personal"]


class EmailTemplateCreate(BaseModel):
    """Create a new email template."""

    name: str = Field(..., min_length=1, max_length=100)
    subject: str = Field(..., min_length=1, max_length=200)
    from_email: str | None = Field(
        None,
        max_length=200,
        description="Optional per-template From header override (e.g., 'Surrogacy Force <invites@surrogacyforce.com>').",
    )
    body: str = Field(..., min_length=1, max_length=50000)
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
    is_active: bool | None = None
    expected_version: int | None = Field(None, description="Required for optimistic locking")


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
    is_active: bool
    scope: str = "org"
    owner_user_id: UUID | None = None
    owner_name: str | None = None  # Populated by service
    source_template_id: UUID | None = None
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
    is_system_template: bool = False
    created_at: datetime
    updated_at: datetime


class EmailTemplateCopyRequest(BaseModel):
    """Request to copy an org/system template to personal."""

    name: str = Field(..., min_length=1, max_length=100)


class EmailTemplateShareRequest(BaseModel):
    """Request to share a personal template with the organization."""

    name: str = Field(..., min_length=1, max_length=100)


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

    template_id: UUID
    recipient_email: EmailStr
    variables: dict[str, str] = {}
    surrogate_id: UUID | None = None
    schedule_at: datetime | None = None


class EmailTemplateTestSendRequest(BaseModel):
    """Request to send a test email using an email template."""

    to_email: EmailStr
    variables: dict[str, str] = {}
    idempotency_key: str | None = None


class PlatformEmailTemplateTestSendRequest(BaseModel):
    """Request to send a test email using a platform email template for a specific org."""

    org_id: UUID
    to_email: EmailStr
    variables: dict[str, str] = {}
    idempotency_key: str | None = None


class EmailTemplateTestSendResponse(BaseModel):
    """Response after sending a test email."""

    success: bool
    provider_used: Literal["resend", "gmail"] | None = None
    email_log_id: UUID | None = None
    message_id: str | None = None
    error: str | None = None


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
