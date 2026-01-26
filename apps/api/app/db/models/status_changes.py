"""SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StatusChangeRequest(Base):
    """
    Tracks pending regression requests that require admin approval.

    Used for both surrogates (stage changes) and intended parents (status changes).
    Regressions = moving to an earlier stage/status in the defined order.
    """

    __tablename__ = "status_change_requests"
    __table_args__ = (
        Index("idx_status_change_requests_org_status", "organization_id", "status"),
        # Partial unique indexes to prevent duplicate pending requests
        Index(
            "idx_pending_surrogate_requests",
            "organization_id",
            "entity_id",
            "target_stage_id",
            "effective_at",
            unique=True,
            postgresql_where=text("entity_type = 'surrogate' AND status = 'pending'"),
        ),
        Index(
            "idx_pending_ip_requests",
            "organization_id",
            "entity_id",
            "target_status",
            "effective_at",
            unique=True,
            postgresql_where=text("entity_type = 'intended_parent' AND status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'surrogate' or 'intended_parent'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True
    )  # For surrogates
    target_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # For intended parents
    effective_at: Mapped[datetime] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Request tracking
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="pending", nullable=False)

    # Approval tracking
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Rejection tracking
    rejected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Cancellation tracking
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
