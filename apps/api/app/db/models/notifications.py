"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization, User


class Notification(Base):
    """
    In-app notifications for users.

    Supports case and task events with dedupe to prevent spam.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notif_user_unread", "user_id", "read_at", "created_at"),
        Index("idx_notif_org_user", "organization_id", "user_id", "created_at"),
        Index("idx_notif_dedupe", "dedupe_key", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Notification type (enum)
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Entity reference (for click-through)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "case", "task"
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Dedupe key: {type}:{entity_id}:{user_id} - prevents duplicate notifications
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Read status
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship()
    organization: Mapped["Organization"] = relationship()


class UserNotificationSettings(Base):
    """
    Per-user notification preferences.

    Missing row = all defaults ON.
    """

    __tablename__ = "user_notification_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # In-app notification toggles (all default TRUE)
    surrogate_assigned: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    surrogate_status_changed: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )
    surrogate_claim_available: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )
    task_assigned: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    workflow_approvals: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    task_reminders: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )  # Due soon/overdue
    appointments: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )  # New/confirmed/cancelled
    contact_reminder: Mapped[bool] = mapped_column(
        default=True, server_default=text("true")
    )  # Contact attempt reminders

    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship()
    organization: Mapped["Organization"] = relationship()


# =============================================================================
# Week 10: Integration Health + System Alerts Models
# =============================================================================
