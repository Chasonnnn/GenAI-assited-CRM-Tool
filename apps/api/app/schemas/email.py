"""Pydantic schemas for email templates and logs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =============================================================================
# Email Templates
# =============================================================================

class EmailTemplateCreate(BaseModel):
    """Create a new email template."""
    name: str = Field(..., min_length=1, max_length=100)
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=50000)


class EmailTemplateUpdate(BaseModel):
    """Update an email template."""
    name: str | None = Field(None, min_length=1, max_length=100)
    subject: str | None = Field(None, min_length=1, max_length=200)
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
    body: str
    is_active: bool
    current_version: int  # For optimistic locking
    created_at: datetime
    updated_at: datetime


class EmailTemplateListItem(BaseModel):
    """Email template list item (minimal)."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    subject: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Email Logs
# =============================================================================

class EmailSendRequest(BaseModel):
    """Request to send an email from a template."""
    template_id: UUID
    recipient_email: EmailStr
    variables: dict[str, str] = {}
    case_id: UUID | None = None
    schedule_at: datetime | None = None


class EmailLogRead(BaseModel):
    """Email log response schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    organization_id: UUID
    job_id: UUID | None
    template_id: UUID | None
    case_id: UUID | None
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
    case_id: UUID | None
    recipient_email: str
    subject: str
    status: str
    sent_at: datetime | None
    created_at: datetime
