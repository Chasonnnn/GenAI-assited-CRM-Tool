"""Campaign schemas for request/response validation."""
from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Filter Criteria
# =============================================================================

class FilterCriteria(BaseModel):
    """Filter criteria for campaign recipients."""
    stage_ids: list[str] | None = None
    stage_slugs: list[str] | None = None
    states: list[str] | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    source: str | None = None
    is_priority: bool | None = None
    has_email: bool = True  # Always filter for valid emails


# =============================================================================
# Campaign CRUD
# =============================================================================

class CampaignCreate(BaseModel):
    """Create a new campaign."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    email_template_id: UUID
    recipient_type: str = Field(default="case", pattern="^(case|intended_parent)$")
    filter_criteria: FilterCriteria = Field(default_factory=FilterCriteria)
    scheduled_at: datetime | None = None


class CampaignUpdate(BaseModel):
    """Update a campaign (only drafts can be updated)."""
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    email_template_id: UUID | None = None
    recipient_type: str | None = Field(None, pattern="^(case|intended_parent)$")
    filter_criteria: FilterCriteria | None = None
    scheduled_at: datetime | None = None


class CampaignResponse(BaseModel):
    """Campaign response."""
    id: UUID
    name: str
    description: str | None
    email_template_id: UUID
    email_template_name: str | None = None
    recipient_type: str
    filter_criteria: dict
    scheduled_at: datetime | None
    status: str
    created_by_user_id: UUID | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    
    # Stats
    total_recipients: int = 0
    sent_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    
    model_config = {"from_attributes": True}


class CampaignListItem(BaseModel):
    """Campaign list item (lightweight)."""
    id: UUID
    name: str
    email_template_name: str | None = None
    recipient_type: str
    status: str
    scheduled_at: datetime | None
    
    # Latest run stats
    total_recipients: int = 0
    sent_count: int = 0
    failed_count: int = 0
    
    created_at: datetime
    
    model_config = {"from_attributes": True}


# =============================================================================
# Campaign Runs
# =============================================================================

class CampaignRunResponse(BaseModel):
    """Campaign run response."""
    id: UUID
    campaign_id: UUID
    started_at: datetime
    completed_at: datetime | None
    status: str
    error_message: str | None
    total_count: int
    sent_count: int
    failed_count: int
    skipped_count: int
    
    model_config = {"from_attributes": True}


class CampaignRecipientResponse(BaseModel):
    """Campaign recipient response."""
    id: UUID
    entity_type: str
    entity_id: UUID
    recipient_email: str
    recipient_name: str | None
    status: str
    error: str | None
    skip_reason: str | None
    sent_at: datetime | None
    
    model_config = {"from_attributes": True}


# =============================================================================
# Preview
# =============================================================================

class RecipientPreview(BaseModel):
    """Preview of a recipient matching the filter."""
    entity_type: str
    entity_id: UUID
    email: str
    name: str | None = None
    stage: str | None = None


class CampaignPreviewResponse(BaseModel):
    """Preview response showing matching recipients."""
    total_count: int
    sample_recipients: list[RecipientPreview]


class PreviewFiltersRequest(BaseModel):
    """Request to preview recipients matching filter criteria."""
    recipient_type: str = Field(..., pattern="^(case|intended_parent)$")
    filter_criteria: FilterCriteria = Field(default_factory=FilterCriteria)


# =============================================================================
# Send
# =============================================================================

class CampaignSendRequest(BaseModel):
    """Request to send a campaign."""
    send_now: bool = True  # If false, schedule for scheduled_at time


class CampaignSendResponse(BaseModel):
    """Response after enqueueing a campaign send."""
    message: str
    run_id: UUID | None = None
    scheduled_at: datetime | None = None


# =============================================================================
# Suppression
# =============================================================================

class SuppressionCreate(BaseModel):
    """Add an email to suppression list."""
    email: str = Field(..., min_length=1)
    reason: str = Field(default="opt_out", pattern="^(opt_out|bounced|archived|complaint)$")


class SuppressionResponse(BaseModel):
    """Suppression list entry."""
    id: UUID
    email: str
    reason: str
    created_at: datetime
    
    model_config = {"from_attributes": True}
