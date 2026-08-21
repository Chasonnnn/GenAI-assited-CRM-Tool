"""Campaign schemas for request/response validation."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

CampaignChannel = Literal["email", "messaging"]

# =============================================================================
# Filter Criteria
# =============================================================================


class FilterCriteria(BaseModel):
    """Filter criteria for campaign recipients."""

    stage_ids: list[UUID] | None = None
    stage_keys: list[str] | None = None
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

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    channel: CampaignChannel = "email"
    email_template_id: UUID | None = None
    message_template_version_id: UUID | None = None
    recipient_type: str = Field(default="case", pattern="^(case|intended_parent)$")
    filter_criteria: FilterCriteria = Field(default_factory=FilterCriteria)
    scheduled_at: datetime | None = None
    include_unsubscribed: bool = False

    @model_validator(mode="after")
    def validate_channel_template(self) -> CampaignCreate:
        if self.channel == "email":
            if self.email_template_id is None or self.message_template_version_id is not None:
                raise ValueError("Email campaigns require email_template_id only")
        elif self.message_template_version_id is None or self.email_template_id is not None:
            raise ValueError("Messaging campaigns require message_template_version_id only")
        if self.channel == "messaging" and self.include_unsubscribed:
            raise ValueError("include_unsubscribed is not available for messaging campaigns")
        return self


class CampaignUpdate(BaseModel):
    """Update a campaign (only drafts can be updated)."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    channel: CampaignChannel | None = None
    email_template_id: UUID | None = None
    message_template_version_id: UUID | None = None
    recipient_type: str | None = Field(None, pattern="^(case|intended_parent)$")
    filter_criteria: FilterCriteria | None = None
    scheduled_at: datetime | None = None
    include_unsubscribed: bool | None = None


class CampaignResponse(BaseModel):
    """Campaign response."""

    id: UUID
    name: str
    description: str | None
    channel: CampaignChannel
    email_template_id: UUID | None
    email_template_name: str | None = None
    message_template_version_id: UUID | None = None
    message_template_name: str | None = None
    recipient_type: str
    filter_criteria: dict
    scheduled_at: datetime | None
    status: str
    include_unsubscribed: bool = False
    created_by_user_id: UUID | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime

    # Stats
    total_recipients: int = 0
    sent_count: int = 0
    delivered_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    opened_count: int = 0
    clicked_count: int = 0

    model_config = {"from_attributes": True}


class CampaignListItem(BaseModel):
    """Campaign list item (lightweight)."""

    id: UUID
    name: str
    channel: CampaignChannel
    email_template_name: str | None = None
    message_template_name: str | None = None
    recipient_type: str
    status: str
    scheduled_at: datetime | None
    include_unsubscribed: bool = False

    # Latest run stats
    total_recipients: int = 0
    sent_count: int = 0
    delivered_count: int = 0
    failed_count: int = 0
    opened_count: int = 0
    clicked_count: int = 0

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
    delivered_count: int
    failed_count: int
    skipped_count: int
    opened_count: int
    clicked_count: int

    model_config = {"from_attributes": True}


class CampaignRetryResponse(BaseModel):
    """Campaign retry response."""

    message: str
    run_id: UUID
    job_id: UUID | None = None
    failed_count: int = 0


class CampaignRecipientResponse(BaseModel):
    """Campaign recipient response."""

    id: UUID
    entity_type: str
    entity_id: UUID
    recipient_email: str | None
    recipient_phone_last4: str | None = None
    message_delivery_id: UUID | None = None
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
    email: str | None = None
    phone_last4: str | None = None
    name: str | None = None
    stage: str | None = None


class CampaignPreviewResponse(BaseModel):
    """Preview response showing matching recipients."""

    total_count: int
    eligible_count: int | None = None
    suppressed_count: int = 0
    unknown_consent_count: int = 0
    sample_recipients: list[RecipientPreview]


class PreviewFiltersRequest(BaseModel):
    """Request to preview recipients matching filter criteria."""

    channel: CampaignChannel = "email"
    recipient_type: str = Field(pattern="^(case|intended_parent)$")
    filter_criteria: FilterCriteria = Field(default_factory=FilterCriteria)
    include_unsubscribed: bool = False

    @model_validator(mode="after")
    def reject_messaging_unsubscribe_bypass(self) -> PreviewFiltersRequest:
        if self.channel == "messaging" and self.include_unsubscribed:
            raise ValueError("include_unsubscribed is not available for messaging campaigns")
        return self


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

    email: str = Field(min_length=1)
    reason: str = Field(default="opt_out", pattern="^(opt_out|bounced|archived|complaint)$")


class SuppressionResponse(BaseModel):
    """Suppression list entry."""

    id: UUID
    email: str
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}
