"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization, User


def _default_stage_key(context) -> str:
    """Derive immutable stage_key from slug when callers omit stage_key."""
    slug = str((context.get_current_parameters() or {}).get("slug") or "").strip().lower()
    if slug == "qualified":
        return "pre_qualified"
    return slug


class Pipeline(Base):
    """
    Organization pipeline configuration.

    v2 (Full CRUD):
    - PipelineStage rows define custom stages
    - Surrogates reference stage_id (FK)
    - Stages have immutable stage_key, editable slug/label/color
    """

    __tablename__ = "pipelines"
    __table_args__ = (Index("idx_pipelines_org", "organization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(100), default="Default", nullable=False)
    is_default: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Version control
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    stages: Mapped[list["PipelineStage"]] = relationship(
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="PipelineStage.order",
    )


class PipelineStage(Base):
    """
    Individual pipeline stage configuration.

    - stage_key: Immutable semantic key, unique per pipeline
    - slug: Editable external identifier, unique per pipeline
    - stage_type: Immutable, controls role access (intake/post_approval/terminal)
    - Soft-delete via is_active + deleted_at
    - Surrogates reference stage_id (FK)
    """

    __tablename__ = "pipeline_stages"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "slug", name="uq_stage_slug"),
        UniqueConstraint("pipeline_id", "stage_key", name="uq_stage_key"),
        Index("idx_stage_pipeline_order", "pipeline_id", "order"),
        Index("idx_stage_pipeline_active", "pipeline_id", "is_active"),
        Index("idx_stage_pipeline_key", "pipeline_id", "stage_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Immutable semantic identity
    stage_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=_default_stage_key,
    )

    # Editable external reference
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    stage_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # intake/post_approval/terminal

    # Editable
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)  # hex #RRGGBB
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Soft-delete
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(), nullable=True)

    # Contact attempts UI gating
    is_intake_stage: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )

    # Future: transition rules
    allowed_next_slugs: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(), server_default=text("now()"), nullable=False
    )

    # Relationships
    pipeline: Mapped["Pipeline"] = relationship(back_populates="stages")


# =============================================================================
# Entity Versioning (Encrypted Config Snapshots)
# =============================================================================


class EntityVersion(Base):
    """
    Append-only configuration version snapshots.

    Used for:
    - Pipelines, email templates, AI settings, org settings
    - Integration configs (tokens redacted)
    - Membership/role changes

    NOT used for: Surrogates, tasks, notes (use activity logs instead)

    Security:
    - payload_encrypted: Fernet-encrypted JSON
    - checksum: SHA256 of decrypted payload for integrity
    - Never store secrets (tokens stored as [REDACTED:key_id])

    Rollback:
    - Creates new version from old payload (never rewrites history)
    - comment field tracks "Rollback from v{N}"
    """

    __tablename__ = "entity_versions"
    __table_args__ = (
        # Unique version per entity
        UniqueConstraint("organization_id", "entity_type", "entity_id", "version"),
        # History queries
        Index(
            "idx_entity_versions_lookup",
            "organization_id",
            "entity_type",
            "entity_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # What's being versioned
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "pipeline", "email_template", etc.
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Version metadata
    version: Mapped[int] = mapped_column(nullable=False)  # Monotonic, starts at 1
    schema_version: Mapped[int] = mapped_column(
        default=1, nullable=False
    )  # For future payload migrations

    # Encrypted payload (Fernet)
    payload_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Integrity verification
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 of decrypted payload

    # Audit trail
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # "Updated stages", "Rollback from v3"

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()


# =============================================================================
# Automation Workflows
# =============================================================================
