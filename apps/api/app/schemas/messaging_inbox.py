"""Read-only organization messaging inbox contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MessagingPurpose = Literal["operational", "promotional"]
MessagingEntityType = Literal["surrogate", "intake_lead", "meta_lead"]


class MessagingLinkedEntityRead(BaseModel):
    entity_type: MessagingEntityType
    entity_id: UUID
    label: str


class MessagingConversationSummary(BaseModel):
    id: UUID
    contact_id: UUID
    masked_phone: str
    purpose: MessagingPurpose
    route_id: UUID
    route_label: str
    unread_count: int
    unlinked: bool
    linked_entities: list[MessagingLinkedEntityRead]
    last_message_at: datetime | None
    last_message_direction: Literal["inbound", "outbound"] | None
    last_message_preview: str | None


class MessagingConversationListResponse(BaseModel):
    items: list[MessagingConversationSummary]
    total: int
    limit: int
    offset: int


class MessagingMediaRead(BaseModel):
    id: UUID
    filename: str | None
    content_type: str
    byte_size: int
    scan_status: str
    provider_deleted: bool
    quarantined: bool


class MessagingDeliveryAttemptRead(BaseModel):
    id: UUID
    attempt_number: int
    outcome: str
    started_at: datetime
    completed_at: datetime | None
    provider_http_status: int | None
    error_type: str | None
    error_message: str | None


class MessagingDeliveryStatusEventRead(BaseModel):
    id: UUID
    status: str | None
    received_at: datetime


class MessagingDeliveryRead(BaseModel):
    id: UUID
    status: str
    source_type: str
    attempt_count: int
    max_attempts: int
    created_at: datetime
    completed_at: datetime | None
    last_error_type: str | None
    last_error: str | None
    attempts: list[MessagingDeliveryAttemptRead]
    status_events: list[MessagingDeliveryStatusEventRead]


class MessagingMessageRead(BaseModel):
    id: UUID
    direction: Literal["inbound", "outbound"]
    purpose: MessagingPurpose
    body: str
    provider_status: str | None
    is_unread: bool
    created_at: datetime
    media: list[MessagingMediaRead]
    delivery: MessagingDeliveryRead | None


class MessagingConsentEventRead(BaseModel):
    id: UUID
    purpose: str
    action: str
    source: str
    occurred_at: datetime
    instruction_text: str | None
    disclosure_hash: str | None


class MessagingReconciliationCaseRead(BaseModel):
    id: UUID
    case_type: str
    status: str
    reason_code: str
    detected_at: datetime
    resolved_at: datetime | None
    resolution_code: str | None
    version: int


class MessagingConversationDetail(MessagingConversationSummary):
    consent_states: dict[MessagingPurpose, str]
    global_suppression_active: bool
    global_suppression_reason: str
    messages: list[MessagingMessageRead]
    consent_timeline: list[MessagingConsentEventRead]
    reconciliation_cases: list[MessagingReconciliationCaseRead]


class MessagingConversationLinkRequest(BaseModel):
    entity_type: MessagingEntityType
    entity_id: UUID


class MessagingReconciliationUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    action: Literal["resolve", "dismiss"]
    resolution_code: str = Field(min_length=1, max_length=80)
