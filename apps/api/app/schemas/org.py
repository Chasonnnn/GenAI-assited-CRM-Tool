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
        """Validate slug format: lowercase, alphanumeric with hyphens/underscores."""
        v = v.lower().strip()
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Slug must be alphanumeric with optional hyphens/underscores"
            )
        return v


class OrgRead(BaseModel):
    """Response schema for reading an organization."""

    id: UUID
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}
