"""Schemas for Meta lead form mapping."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.import_template import ColumnMappingItem, ColumnSuggestionResponse


class MetaFormSummary(BaseModel):
    """Summary of a Meta lead form and mapping status."""

    id: UUID
    form_external_id: str
    form_name: str
    page_id: str
    page_name: str | None
    mapping_status: str
    current_version_id: UUID | None
    mapping_version_id: UUID | None
    mapping_updated_at: datetime | None
    mapping_updated_by_name: str | None
    is_active: bool
    synced_at: datetime
    unconverted_leads: int
    total_leads: int
    last_lead_at: datetime | None


class MetaFormColumn(BaseModel):
    """Column metadata for a Meta form question."""

    key: str
    label: str | None
    question_type: str | None


class MetaFormMappingPreviewResponse(BaseModel):
    """Preview response for Meta form mapping."""

    form: MetaFormSummary
    columns: list[MetaFormColumn]
    column_suggestions: list[ColumnSuggestionResponse]
    sample_rows: list[dict]
    has_live_leads: bool
    available_fields: list[str]
    ai_available: bool
    mapping_rules: list[ColumnMappingItem] | None
    unknown_column_behavior: Literal["ignore", "metadata", "warn"] = "metadata"


class MetaFormMappingUpdateRequest(BaseModel):
    """Request to update a Meta form mapping."""

    column_mappings: list[ColumnMappingItem] = Field(default_factory=list)
    unknown_column_behavior: Literal["ignore", "metadata", "warn"] = "metadata"


class MetaFormMappingUpdateResponse(BaseModel):
    """Response after updating mapping."""

    success: bool
    mapping_status: str
    mapping_version_id: UUID | None
    message: str | None = None


class MetaFormSyncRequest(BaseModel):
    """Request to sync forms."""

    page_id: str | None = None
