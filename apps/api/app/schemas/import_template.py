"""Pydantic schemas for Import Templates and CSV Import."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Column Mapping Schemas
# =============================================================================


class ColumnMappingItem(BaseModel):
    """Single column mapping configuration."""

    csv_column: str = Field(description="Original CSV column header")
    surrogate_field: str | None = Field(
        default=None,
        description="Target Surrogate model field (e.g., 'full_name', 'email')",
    )
    transformation: str | None = Field(
        default=None,
        description="Transformation to apply (e.g., 'date_flexible', 'boolean_flexible')",
    )
    action: Literal["map", "metadata", "custom", "ignore"] = Field(
        default="map",
        description="What to do with this column",
    )
    custom_field_key: str | None = Field(
        default=None,
        description="Custom field key if action='custom'",
    )


class ColumnSuggestionResponse(BaseModel):
    """Column mapping suggestion from detection/AI analysis."""

    csv_column: str
    suggested_field: str | None
    confidence: float = Field(ge=0, le=1)
    confidence_level: Literal["high", "medium", "low", "none"]
    transformation: str | None
    sample_values: list[str] = Field(max_length=5)
    reason: str
    warnings: list[str] = Field(default_factory=list)
    default_action: Literal["map", "metadata", "custom", "ignore"] | None = None
    needs_inversion: bool = False


# =============================================================================
# Import Template Schemas
# =============================================================================


class ImportTemplateBase(BaseModel):
    """Base import template fields."""

    name: str = Field(max_length=100, description="Template name")
    description: str | None = Field(default=None, max_length=500)
    is_default: bool = Field(default=False, description="Use as default for quick imports")
    encoding: Literal["auto", "utf-8", "utf-16", "utf-8-sig", "latin-1"] = "auto"
    delimiter: Literal["auto", ",", "\t", ";", "|"] = "auto"
    has_header: bool = True
    unknown_column_behavior: Literal["ignore", "metadata", "warn"] = "ignore"


class ImportTemplateCreate(ImportTemplateBase):
    """Schema for creating an import template."""

    column_mappings: list[ColumnMappingItem] = Field(default_factory=list)
    transformations: dict[str, str] | None = Field(
        default=None,
        description="Field-level transformation overrides, e.g., {'is_non_smoker': 'boolean_inverted'}",
    )


class ImportTemplateUpdate(BaseModel):
    """Schema for updating an import template."""

    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_default: bool | None = None
    encoding: Literal["auto", "utf-8", "utf-16", "utf-8-sig", "latin-1"] | None = None
    delimiter: Literal["auto", ",", "\t", ";", "|"] | None = None
    has_header: bool | None = None
    column_mappings: list[ColumnMappingItem] | None = None
    transformations: dict[str, str] | None = None
    unknown_column_behavior: Literal["ignore", "metadata", "warn"] | None = None


class ImportTemplateRead(ImportTemplateBase):
    """Schema for reading an import template."""

    id: UUID
    organization_id: UUID
    column_mappings: list[ColumnMappingItem] | None
    transformations: dict | None
    usage_count: int
    last_used_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImportTemplateListItem(BaseModel):
    """Schema for template list item."""

    id: UUID
    name: str
    description: str | None
    is_default: bool
    encoding: str
    delimiter: str
    usage_count: int
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MatchingTemplate(BaseModel):
    """Template that might match current CSV structure."""

    id: UUID
    name: str
    match_score: float = Field(ge=0, le=1)


# =============================================================================
# Enhanced Import Preview Schemas
# =============================================================================


class EnhancedImportPreviewResponse(BaseModel):
    """Enhanced preview response with detection and suggestions."""

    import_id: UUID
    total_rows: int
    sample_rows: list[dict]
    detected_encoding: str
    detected_delimiter: str
    has_header: bool

    # Column analysis
    column_suggestions: list[ColumnSuggestionResponse]
    matched_count: int = Field(description="Columns with confident mapping")
    unmatched_count: int = Field(description="Columns needing attention")

    # Template matching
    matching_templates: list[MatchingTemplate] = Field(default_factory=list)

    # Available fields for dropdown
    available_fields: list[str]

    # Validation summary
    duplicate_emails_db: int
    duplicate_emails_csv: int
    validation_errors: int
    date_ambiguity_warnings: list[dict] = Field(default_factory=list)

    # AI availability
    ai_available: bool = Field(description="Whether AI help is available for this org")


# =============================================================================
# Import Approval Schemas
# =============================================================================


class DeduplicationStats(BaseModel):
    """Statistics about duplicate detection."""

    total: int
    new_records: int
    duplicates: list[dict] = Field(
        default_factory=list,
        description="List of {email, existing_id} for duplicates",
    )


class ImportApprovalItem(BaseModel):
    """Import awaiting approval."""

    id: UUID
    filename: str
    status: str
    total_rows: int
    created_at: datetime
    created_by_name: str | None
    deduplication_stats: DeduplicationStats | None
    column_mapping_snapshot: list[ColumnMappingItem] | None
    backdate_created_at: bool = False


class ImportApproveRequest(BaseModel):
    """Request to approve an import."""

    pass  # No additional fields needed


class ImportRejectRequest(BaseModel):
    """Request to reject an import."""

    reason: str = Field(min_length=1, max_length=500)


class ImportApprovalResponse(BaseModel):
    """Response after approval/rejection."""

    import_id: UUID
    status: str
    message: str


# =============================================================================
# AI Mapping Request
# =============================================================================


class AIMapRequest(BaseModel):
    """Request AI assistance for unmapped columns."""

    unmatched_columns: list[str] = Field(description="List of column names to analyze with AI")


class AIMapResponse(BaseModel):
    """AI mapping suggestions response."""

    suggestions: list[ColumnSuggestionResponse]
    prompt_tokens: int
    completion_tokens: int
