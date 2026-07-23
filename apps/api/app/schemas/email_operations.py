"""Sanitized response contracts for organization email operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ReadinessOverall = Literal["ready", "needs_attention", "not_configured"]
ReadinessCheckStatus = Literal["pass", "fail", "unknown", "not_applicable"]


class EmailOperationsReadinessCheck(BaseModel):
    """One stable, machine-readable readiness check."""

    key: str
    status: ReadinessCheckStatus
    detail: str
    observed_at: datetime | None = None


class EmailOperationsSummary24h(BaseModel):
    """Organization-scoped email activity in the trailing 24 hours."""

    messages: int
    pending: int
    sent: int
    failed: int
    delivered: int
    bounced: int
    complained: int
    estimated_opens: int
    clicks: int
    delivery_attempts: int
    webhook_events: int


class EmailOperationsReadinessResponse(BaseModel):
    """Persisted configuration and evidence used for readiness."""

    overall: ReadinessOverall
    can_send: bool
    can_track: bool
    provider: str | None
    provider_scope: str | None
    provider_account_id: str | None
    recent_webhook_activity: ReadinessCheckStatus
    last_webhook_received_at: datetime | None
    checks: list[EmailOperationsReadinessCheck]
    summary_24h: EmailOperationsSummary24h


class EmailOperationMessageSummary(BaseModel):
    """Sanitized message-log projection safe for authenticated org users."""

    id: UUID
    recipient_email: str
    subject: str
    from_email: str | None
    purpose: str | None
    source_type: str | None
    source_id: UUID | None
    provider: str | None
    provider_scope: str | None
    provider_account_id: str | None
    provider_message_id: str | None
    status: str
    provider_status: str | None
    delivery_status: str | None
    attempt_count: int | None
    max_attempts: int | None
    created_at: datetime
    sent_at: datetime | None
    delivered_at: datetime | None
    bounced_at: datetime | None
    bounce_type: str | None
    complained_at: datetime | None
    estimated_opened_at: datetime | None
    estimated_open_count: int
    clicked_at: datetime | None
    click_count: int
    open_tracking: Literal["estimated"] = "estimated"


class EmailOperationMessageListResponse(BaseModel):
    """Stable keyset-paginated message-log page."""

    items: list[EmailOperationMessageSummary]
    next_cursor: str | None


class EmailOperationDelivery(BaseModel):
    """Sanitized delivery outbox state for one message."""

    id: UUID
    status: str
    run_at: datetime
    attempt_count: int
    max_attempts: int
    first_attempt_at: datetime | None
    last_attempt_at: datetime | None
    completed_at: datetime | None
    last_error_type: str | None
    provider_message_id: str | None
    created_at: datetime
    updated_at: datetime


class EmailOperationDeliveryAttempt(BaseModel):
    """Sanitized provider attempt without lease or raw error content."""

    id: UUID
    attempt_number: int
    started_at: datetime
    completed_at: datetime | None
    outcome: str
    provider_http_status: int | None
    error_type: str | None
    provider_message_id: str | None
    retry_after_seconds: int | None


class EmailOperationProviderEvent(BaseModel):
    """Provider event metadata without its raw payload."""

    id: UUID
    provider_event_id: str
    event_type: str
    event_created_at: datetime
    received_at: datetime
    processed_at: datetime | None


class EmailOperationMessageDetail(EmailOperationMessageSummary):
    """Message summary plus its ordered delivery diagnostics."""

    delivery: EmailOperationDelivery | None
    attempts: list[EmailOperationDeliveryAttempt]
    provider_events: list[EmailOperationProviderEvent]


EmailReconciliationStatus = Literal[
    "pending",
    "running",
    "action_required",
    "resolved",
    "dismissed",
]
EmailReconciliationAction = Literal[
    "retry_correlation",
    "link_event",
    "dismiss",
    "confirm_sent",
    "confirm_not_sent",
]


class EmailReconciliationCaseSummary(BaseModel):
    """Sanitized operator projection for one email reconciliation case."""

    id: UUID
    case_type: Literal["orphan_webhook", "unknown_delivery"]
    status: EmailReconciliationStatus
    reason_code: str
    version: int
    provider: Literal["resend"]
    event_type: str | None
    event_created_at: datetime | None
    received_at: datetime | None
    message_id: UUID | None
    delivery_id: UUID | None
    attempt_count: int | None
    max_attempts: int | None
    next_attempt_at: datetime | None
    available_actions: list[EmailReconciliationAction]
    detected_at: datetime
    updated_at: datetime


class EmailReconciliationCounts(BaseModel):
    """Organization case totals grouped for the operator queue."""

    monitoring: int
    action_required: int
    resolved: int


class EmailReconciliationCaseListResponse(BaseModel):
    """Stable keyset-paginated reconciliation queue."""

    items: list[EmailReconciliationCaseSummary]
    next_cursor: str | None
    counts: EmailReconciliationCounts


class EmailReconciliationRetryRequest(BaseModel):
    """Optimistically fenced request to retry local event correlation."""

    expected_version: int = Field(ge=1)
