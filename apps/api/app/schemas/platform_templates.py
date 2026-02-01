"""Pydantic schemas for platform template studio."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.forms import FormSchema


TemplateStatus = Literal["draft", "published", "archived"]


class TemplatePublishRequest(BaseModel):
    publish_all: bool = False
    org_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def validate_targets(self):
        if not self.publish_all and not self.org_ids:
            raise ValueError("org_ids is required when publish_all is false")
        return self


class PlatformEmailTemplateDraft(BaseModel):
    name: str = Field(max_length=120)
    subject: str = Field(max_length=200)
    body: str
    from_email: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=50)


class PlatformEmailTemplateCreate(PlatformEmailTemplateDraft):
    pass


class PlatformEmailTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = None
    from_email: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=50)
    expected_version: int | None = None


class PlatformEmailTemplateRead(BaseModel):
    id: UUID
    status: TemplateStatus
    current_version: int
    published_version: int
    is_published_globally: bool
    target_org_ids: list[UUID] = Field(default_factory=list)
    published_at: datetime | None
    draft: PlatformEmailTemplateDraft
    published: PlatformEmailTemplateDraft | None
    created_at: datetime
    updated_at: datetime


class PlatformEmailTemplateListItem(BaseModel):
    id: UUID
    status: TemplateStatus
    current_version: int
    published_version: int
    is_published_globally: bool
    draft: PlatformEmailTemplateDraft
    published_at: datetime | None
    updated_at: datetime


class EmailTemplateLibraryItem(BaseModel):
    id: UUID
    name: str
    subject: str
    from_email: str | None
    category: str | None
    published_at: datetime | None
    updated_at: datetime


class EmailTemplateLibraryDetail(EmailTemplateLibraryItem):
    body: str


class PlatformFormTemplateDraft(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str = Field(max_length=150)
    description: str | None = None
    form_schema: FormSchema | None = Field(default=None, alias="schema_json")
    settings_json: dict | None = None


class PlatformFormTemplateCreate(PlatformFormTemplateDraft):
    pass


class PlatformFormTemplateUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str | None = Field(default=None, max_length=150)
    description: str | None = None
    form_schema: FormSchema | None = Field(default=None, alias="schema_json")
    settings_json: dict | None = None
    expected_version: int | None = None


class PlatformFormTemplateRead(BaseModel):
    id: UUID
    status: TemplateStatus
    current_version: int
    published_version: int
    is_published_globally: bool
    target_org_ids: list[UUID] = Field(default_factory=list)
    published_at: datetime | None
    draft: PlatformFormTemplateDraft
    published: PlatformFormTemplateDraft | None
    created_at: datetime
    updated_at: datetime


class PlatformFormTemplateListItem(BaseModel):
    id: UUID
    status: TemplateStatus
    current_version: int
    published_version: int
    is_published_globally: bool
    draft: PlatformFormTemplateDraft
    published_at: datetime | None
    updated_at: datetime


class FormTemplateLibraryItem(BaseModel):
    id: UUID
    name: str
    description: str | None
    published_at: datetime | None
    updated_at: datetime


class FormTemplateLibraryDetail(FormTemplateLibraryItem):
    model_config = ConfigDict(populate_by_name=True)
    form_schema: FormSchema | None = Field(alias="schema_json")
    settings_json: dict | None


class PlatformWorkflowTemplateDraft(BaseModel):
    name: str = Field(max_length=100)
    description: str | None = None
    icon: str = Field(default="template", max_length=50)
    category: str = Field(default="general", max_length=50)
    trigger_type: str
    trigger_config: dict = Field(default_factory=dict)
    conditions: list[dict] = Field(default_factory=list)
    condition_logic: str = "AND"
    actions: list[dict] = Field(default_factory=list)


class PlatformWorkflowTemplateCreate(PlatformWorkflowTemplateDraft):
    pass


class PlatformWorkflowTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=50)
    category: str | None = Field(default=None, max_length=50)
    trigger_type: str | None = None
    trigger_config: dict | None = None
    conditions: list[dict] | None = None
    condition_logic: str | None = None
    actions: list[dict] | None = None
    expected_version: int | None = None


class PlatformWorkflowTemplateRead(BaseModel):
    id: UUID
    status: TemplateStatus
    published_version: int
    is_published_globally: bool
    target_org_ids: list[UUID] = Field(default_factory=list)
    published_at: datetime | None
    draft: PlatformWorkflowTemplateDraft
    published: PlatformWorkflowTemplateDraft | None
    created_at: datetime
    updated_at: datetime


class PlatformWorkflowTemplateListItem(BaseModel):
    id: UUID
    status: TemplateStatus
    published_version: int
    is_published_globally: bool
    draft: PlatformWorkflowTemplateDraft
    published_at: datetime | None
    updated_at: datetime
