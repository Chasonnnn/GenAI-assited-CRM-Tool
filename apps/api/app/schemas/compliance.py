"""Schemas for compliance exports, retention policies, and legal holds."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ExportJobCreate(BaseModel):
    start_date: datetime
    end_date: datetime
    format: Literal["csv", "json"] = "csv"
    redact_mode: Literal["redacted", "full"] = "redacted"
    acknowledgment: str | None = None


class ExportJobRead(BaseModel):
    id: UUID
    status: str
    export_type: str
    format: str
    redact_mode: str
    date_range_start: datetime
    date_range_end: datetime
    record_count: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    download_url: str | None = None

    model_config = {"from_attributes": True}


class ExportJobListResponse(BaseModel):
    items: list[ExportJobRead]


class RetentionPolicyUpsert(BaseModel):
    entity_type: str
    retention_days: int = Field(ge=0)
    is_active: bool = True


class RetentionPolicyRead(BaseModel):
    id: UUID
    entity_type: str
    retention_days: int
    is_active: bool
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LegalHoldCreate(BaseModel):
    entity_type: str | None = None
    entity_id: UUID | None = None
    reason: str


class LegalHoldRead(BaseModel):
    id: UUID
    entity_type: str | None
    entity_id: UUID | None
    reason: str
    created_by_user_id: UUID | None
    created_at: datetime
    released_at: datetime | None
    released_by_user_id: UUID | None

    model_config = {"from_attributes": True}


class PurgePreviewItem(BaseModel):
    entity_type: str
    count: int


class PurgePreviewResponse(BaseModel):
    items: list[PurgePreviewItem]


class PurgeExecuteResponse(BaseModel):
    job_id: UUID
