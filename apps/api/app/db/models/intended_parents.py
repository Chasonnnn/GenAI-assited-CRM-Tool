"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    DEFAULT_IP_STATUS,
)
from app.db.types import EncryptedString, EncryptedText

if TYPE_CHECKING:
    from app.db.models import Organization


class IntendedParent(Base):
    """
    Prospective parents seeking surrogacy services.

    Mirrors Surrogate patterns: org-scoped, soft-delete, status history.
    """

    __tablename__ = "intended_parents"
    __table_args__ = (
        Index("idx_ip_org_status", "organization_id", "status"),
        Index("idx_ip_org_created", "organization_id", "created_at"),
        Index("idx_ip_org_updated", "organization_id", "updated_at"),
        Index("idx_ip_org_owner", "organization_id", "owner_type", "owner_id"),
        UniqueConstraint(
            "organization_id",
            "intended_parent_number",
            name="uq_intended_parent_number",
        ),
        # Partial unique index: unique email per org for non-archived records
        Index(
            "uq_ip_email_hash_active",
            "organization_id",
            "email_hash",
            unique=True,
            postgresql_where=text("is_archived = false"),
        ),
        # GIN index for full-text search
        Index(
            "ix_intended_parents_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        # PII hash index for phone lookups
        Index("idx_ip_org_phone_hash", "organization_id", "phone_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    intended_parent_number: Mapped[str] = mapped_column(String(10), nullable=False)

    # Contact info
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Location (state only)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Budget (single field, Decimal for precision)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Internal notes (not the polymorphic notes, just a quick text field)
    notes_internal: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)

    # Status & workflow
    status: Mapped[str] = mapped_column(
        String(50), server_default=text(f"'{DEFAULT_IP_STATUS.value}'"), nullable=False
    )

    # Owner model (user or queue)
    owner_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Soft delete
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Activity tracking
    last_activity: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    status_history: Mapped[list["IntendedParentStatusHistory"]] = relationship(
        back_populates="intended_parent", cascade="all, delete-orphan"
    )


class IntendedParentStatusHistory(Base):
    """Tracks all status changes on intended parents for audit."""

    __tablename__ = "intended_parent_status_history"
    __table_args__ = (Index("idx_ip_history_ip", "intended_parent_id", "changed_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    intended_parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Dual timestamps for backdating support
    effective_at: Mapped[datetime | None] = mapped_column(nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Audit fields for approval flow
    requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_undo: Mapped[bool] = mapped_column(server_default=text("false"), nullable=False)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("status_change_requests.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    intended_parent: Mapped["IntendedParent"] = relationship(back_populates="status_history")


# =============================================================================
# Polymorphic Notes (replaces case_notes for new entities)
# =============================================================================
