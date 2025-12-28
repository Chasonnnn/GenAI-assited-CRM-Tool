"""User-related Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserRead(BaseModel):
    """Response schema for reading a user."""

    id: UUID
    email: str
    display_name: str
    avatar_url: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Request schema for updating a user profile."""

    display_name: str | None = None
    avatar_url: str | None = None
