"""Pydantic schemas for Custom Fields."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Custom Field Definition Schemas
# =============================================================================


class CustomFieldBase(BaseModel):
    """Base custom field fields."""

    key: str = Field(
        min_length=1,
        max_length=100,
        description="Unique field key (lowercase, underscores)",
    )
    label: str = Field(min_length=1, max_length=255, description="Display label")
    field_type: Literal["text", "number", "boolean", "date", "select"] = Field(
        description="Data type for the field"
    )
    options: list[str] | None = Field(
        default=None,
        description="Options for select type (required if field_type='select')",
    )

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """Normalize key to lowercase with underscores."""
        normalized = v.lower().strip().replace(" ", "_").replace("-", "_")
        if not normalized.replace("_", "").isalnum():
            raise ValueError("Key must contain only letters, numbers, and underscores")
        return normalized

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[str] | None, info) -> list[str] | None:
        """Ensure options are provided for select type."""
        if info.data.get("field_type") == "select" and not v:
            raise ValueError("Options are required for select type fields")
        return v


class CustomFieldCreate(CustomFieldBase):
    """Schema for creating a custom field."""

    pass


class CustomFieldUpdate(BaseModel):
    """Schema for updating a custom field."""

    label: str | None = Field(default=None, min_length=1, max_length=255)
    options: list[str] | None = None
    is_active: bool | None = None


class CustomFieldRead(CustomFieldBase):
    """Schema for reading a custom field."""

    id: UUID
    organization_id: UUID
    is_active: bool
    created_by_user_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomFieldListItem(BaseModel):
    """Schema for custom field list item."""

    id: UUID
    key: str
    label: str
    field_type: str
    options: list[str] | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# Custom Field Value Schemas
# =============================================================================


class CustomFieldValueSet(BaseModel):
    """Schema for setting a custom field value."""

    value: Any = Field(description="The value to set (type must match field_type)")


class CustomFieldValueRead(BaseModel):
    """Schema for reading a custom field value."""

    field_id: UUID
    field_key: str
    field_label: str
    field_type: str
    value: Any

    model_config = {"from_attributes": True}


class BulkCustomValueSet(BaseModel):
    """Schema for setting multiple custom field values at once."""

    values: dict[str, Any] = Field(description="Dict of field_key -> value")


class SurrogateCustomFieldsResponse(BaseModel):
    """Response containing all custom fields for a surrogate."""

    surrogate_id: UUID
    custom_fields: list[CustomFieldValueRead]


# =============================================================================
# Predefined Custom Field Suggestions
# =============================================================================


class PredefinedCustomField(BaseModel):
    """A predefined custom field that can be auto-created."""

    key: str
    label: str
    field_type: str
    options: list[str] | None = None
    description: str


class PredefinedCustomFieldsResponse(BaseModel):
    """List of predefined custom fields available."""

    fields: list[PredefinedCustomField]
