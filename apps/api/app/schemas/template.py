"""Pydantic schemas for Workflow Templates (Marketplace)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TemplateBase(BaseModel):
    """Base template fields."""

    name: str = Field(max_length=100)
    description: str | None = None
    icon: str = Field(default="template", max_length=50)
    category: str = Field(default="general", max_length=50)


class TemplateCreate(TemplateBase):
    """Schema for creating a template from workflow config."""

    trigger_type: str
    trigger_config: dict = Field(default_factory=dict)
    conditions: list[dict] = Field(default_factory=list)
    condition_logic: str = "AND"
    actions: list[dict] = Field(min_length=1)


class TemplateFromWorkflow(BaseModel):
    """Schema for creating a template from an existing workflow."""

    workflow_id: UUID
    name: str = Field(max_length=100)
    description: str | None = None
    category: str = "general"


class TemplateRead(TemplateBase):
    """Schema for reading a template."""

    id: UUID
    trigger_type: str
    trigger_config: dict
    conditions: list[dict]
    condition_logic: str
    actions: list[dict]
    is_global: bool
    organization_id: UUID | None
    usage_count: int
    created_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateListItem(BaseModel):
    """Schema for template list item."""

    id: UUID
    name: str
    description: str | None
    icon: str
    category: str
    trigger_type: str
    is_global: bool
    usage_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class UseTemplateRequest(BaseModel):
    """Request to create a workflow from a template."""

    name: str = Field(max_length=100)
    description: str | None = None
    is_enabled: bool = True
    action_overrides: dict[str, dict] | None = None


TEMPLATE_CATEGORIES = [
    {"value": "onboarding", "label": "Onboarding"},
    {"value": "follow-up", "label": "Follow-up"},
    {"value": "notifications", "label": "Notifications"},
    {"value": "compliance", "label": "Compliance"},
    {"value": "general", "label": "General"},
]
