"""Schemas for AI bulk task creation."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, model_validator


class BulkTaskItem(BaseModel):
    """A single task to create."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    due_date: str | None = None  # ISO format
    due_time: str | None = None  # HH:MM format
    task_type: str = "other"
    dedupe_key: str | None = None


class BulkTaskCreateRequest(BaseModel):
    """Request to create multiple tasks."""

    request_id: uuid.UUID  # Idempotency key
    # At least one entity ID must be provided
    surrogate_id: uuid.UUID | None = None
    intended_parent_id: uuid.UUID | None = None
    match_id: uuid.UUID | None = None
    tasks: list[BulkTaskItem] = Field(..., min_length=1, max_length=50)

    @model_validator(mode="before")
    @classmethod
    def _normalize_case_id(cls, values):
        if isinstance(values, dict) and not values.get("surrogate_id") and values.get("case_id"):
            values["surrogate_id"] = values["case_id"]
        return values

    @model_validator(mode="after")
    def _validate_entity_ids(self):
        if not any([self.surrogate_id, self.intended_parent_id, self.match_id]):
            raise ValueError(
                "At least one of surrogate_id, intended_parent_id, or match_id must be provided"
            )
        return self


class BulkTaskCreateResponse(BaseModel):
    """Response from bulk task creation."""

    success: bool
    created: list[dict]
    error: str | None = None
