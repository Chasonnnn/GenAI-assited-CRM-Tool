"""Organization-related Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class OrgCreate(BaseModel):
    """Request schema for creating an organization."""

    name: str
    slug: str

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Validate slug format: lowercase, alphanumeric with hyphens only."""
        from app.services import org_service

        return org_service.validate_slug(v)


class OrgRead(BaseModel):
    """Response schema for reading an organization."""

    id: UUID
    name: str
    slug: str
    portal_base_url: str
    created_at: datetime

    model_config = {"from_attributes": True}
