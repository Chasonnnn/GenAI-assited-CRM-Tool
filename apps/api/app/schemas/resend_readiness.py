"""Sanitized public contracts for cached Resend readiness checks."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


ReadinessCheckStatus = Literal["idle", "queued", "running"]
ReadinessFreshness = Literal["fresh", "stale", "never_checked"]
ReadinessProbeStatus = Literal["succeeded", "limited", "failed"]
ReadinessCapabilityStatus = Literal[
    "ready",
    "needs_attention",
    "limited",
    "unknown",
    "not_configured",
]


class ResendReadinessSnapshotResponse(BaseModel):
    """Provider-safe cached result; no routing, credential, or provider identifiers."""

    model_config = ConfigDict(from_attributes=True)

    freshness: ReadinessFreshness
    probe_status: ReadinessProbeStatus | None
    overall_status: ReadinessCapabilityStatus
    domain_status: ReadinessCapabilityStatus
    webhook_status: ReadinessCapabilityStatus
    sending_status: ReadinessCapabilityStatus
    delivery_tracking_status: ReadinessCapabilityStatus
    engagement_tracking_status: ReadinessCapabilityStatus
    verified_domain_count: int
    enabled_webhook_count: int
    issue_codes: tuple[str, ...]
    checked_at: datetime | None
    last_success_at: datetime | None


class ResendReadinessEnvelope(BaseModel):
    """Current durable-check state plus the latest still-visible cached result."""

    model_config = ConfigDict(from_attributes=True)

    check_status: ReadinessCheckStatus
    last_snapshot: ResendReadinessSnapshotResponse
