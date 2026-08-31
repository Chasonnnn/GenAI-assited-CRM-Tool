"""Shared CRM entity activity schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EntityActivityRead(BaseModel):
    """One normalized entity activity event."""

    id: UUID
    activity_type: str
    actor_user_id: UUID | None
    actor_name: str | None
    details: dict | None
    created_at: datetime


class EntityActivityResponse(BaseModel):
    """Paginated normalized entity activity feed."""

    items: list[EntityActivityRead]
    total: int
    page: int
    pages: int
