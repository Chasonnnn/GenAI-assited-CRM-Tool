"""Pydantic schemas for notes."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    """Request to add a note."""

    body: str = Field(..., min_length=2, max_length=4000)


class NoteRead(BaseModel):
    """Note response."""

    id: UUID
    surrogate_id: UUID
    author_id: UUID
    author_name: str | None = None
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}
