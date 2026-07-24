"""Schemas for production-safe email template drafts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.email import (
    EmailTemplateTestSendRequest,
    EmailTemplateTestSendResponse,
)


EmailTemplateDraftScope = Literal["org", "personal"]


class EmailTemplateDraftCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=200)
    from_email: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1, max_length=50000)
    scope: EmailTemplateDraftScope = "org"


class EmailTemplateDraftUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    from_email: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=50000)
    is_active: bool | None = None
    expected_revision: int = Field(ge=1)

    @model_validator(mode="after")
    def require_content_change(self):
        changed_fields = self.model_fields_set - {"expected_revision"}
        if not changed_fields:
            raise ValueError("At least one draft field must be provided")
        return self


class EmailTemplateDraftPublishRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    expected_published_version: int | None = Field(default=None, ge=1)


class EmailTemplateDraftTestSendRequest(EmailTemplateTestSendRequest):
    expected_revision: int = Field(ge=1)


class EmailTemplateDraftTestSendResponse(EmailTemplateTestSendResponse):
    tested_revision: int = Field(ge=1)


class EmailTemplateDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    template_id: UUID | None
    created_by_user_id: UUID | None
    updated_by_user_id: UUID | None
    scope: EmailTemplateDraftScope
    owner_user_id: UUID | None
    owner_name: str | None = None
    name: str
    subject: str
    from_email: str | None
    body: str
    is_active: bool
    category: str | None
    base_version: int
    revision: int
    published_version: int | None
    is_stale: bool
    last_tested_revision: int | None
    last_tested_at: datetime | None
    created_at: datetime
    updated_at: datetime
