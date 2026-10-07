"""Schemas for the development-only `/dev` endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class DevLoginResponse(BaseModel):
    status: str
    user_id: str
    email: str
    role: str
    org_id: str


class DevGoogleLoginRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(default="Dev Google User", min_length=1, max_length=255)
    invite_id: UUID | None = None


class DevInviteCreate(BaseModel):
    email: EmailStr
    role: str
    expires_at: datetime | None = None


class DevInviteRead(BaseModel):
    id: str
    email: str
    role: str
    status: str
    expires_at: str | None
