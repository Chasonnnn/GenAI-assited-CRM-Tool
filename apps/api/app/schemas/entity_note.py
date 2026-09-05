"""Pydantic schemas for polymorphic EntityNote."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field


class EntityNoteCreate(BaseModel):
    """Schema for creating a note on any entity."""

    content: str = Field(min_length=1, max_length=50000)


class EntityNoteRead(BaseModel):
    """Note response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    entity_type: str
    entity_id: UUID
    author_id: UUID
    content: str
    created_at: datetime


class EntityNoteListItem(BaseModel):
    """Minimal note for list view."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID
    author_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("author_name", AliasPath("author", "display_name")),
    )
    content: str
    created_at: datetime
