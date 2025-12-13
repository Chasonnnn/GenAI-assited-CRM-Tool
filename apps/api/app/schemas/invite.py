"""Invite-related Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.db.enums import Role


class InviteCreate(BaseModel):
    """
    Request schema for creating an invite.
    
    Validates:
    - Email format
    - Role is valid enum value
    - Email is normalized to lowercase
    """
    email: EmailStr
    role: Role  # Must be valid Role enum
    expires_in_days: int | None = 30  # NULL = never expires
    
    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower()


class InviteRead(BaseModel):
    """Response schema for reading an invite."""
    id: UUID
    email: str
    role: Role
    expires_at: datetime | None
    accepted_at: datetime | None
    created_at: datetime
    
    model_config = {"from_attributes": True}
