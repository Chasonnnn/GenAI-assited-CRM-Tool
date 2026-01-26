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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization, User


class AuditLog(Base):
    """
    Security and compliance audit log.

    Tracks authentication, settings changes, data exports, AI actions,
    and integration events for enterprise compliance.

    Security:
    - Never stores secrets/tokens
    - PII in details is hashed (email) or ID-only
    - IP captured from X-Forwarded-For or client IP
    - Hash chain makes tampering detectable
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_org_created", "organization_id", "created_at"),
        Index("idx_audit_org_event_created", "organization_id", "event_type", "created_at"),
        Index(
            "idx_audit_org_actor_created",
            "organization_id",
            "actor_user_id",
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
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # System events have no actor
    )

    # Event classification
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # AuditEventType

    # Target entity (optional)
    target_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'user', 'case', 'ai_action', etc.
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Event details (redacted - no secrets, hashed PII)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Request metadata
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Request correlation (for grouping related audit events)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Tamper-evident hash chain
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA256 hex
    entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA256 hex

    # Version control links (for config change auditing)
    before_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    after_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    actor: Mapped["User | None"] = relationship()


# =============================================================================
# Compliance
# =============================================================================


class LegalHold(Base):
    """
    Legal hold to block data purges.

    If entity_type/entity_id are NULL, the hold is org-wide.
    """

    __tablename__ = "legal_holds"
    __table_args__ = (
        Index("idx_legal_holds_org_active", "organization_id", "released_at"),
        Index(
            "idx_legal_holds_entity_active",
            "organization_id",
            "entity_type",
            "entity_id",
            "released_at",
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
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    released_by: Mapped["User | None"] = relationship(foreign_keys=[released_by_user_id])


class DataRetentionPolicy(Base):
    """
    Data retention policy by entity type (audit logs are archive-only).

    retention_days=0 means "keep forever".
    """

    __tablename__ = "data_retention_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_type", name="uq_retention_policy_org_entity"),
        Index("idx_retention_policy_org_active", "organization_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()
