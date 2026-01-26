"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization, User


class Queue(Base):
    """
    Work queues for case routing and assignment.

    Salesforce-style: cases can be owned by a queue or a user.
    When claimed, ownership transfers from queue to user.
    """

    __tablename__ = "queues"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_queue_name"),
        Index("idx_queues_org_active", "organization_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=datetime.now, nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    members: Mapped[list["QueueMember"]] = relationship(
        back_populates="queue",
        cascade="all, delete-orphan",
    )


class QueueMember(Base):
    """
    Queue membership - assigns users to specific queues.

    Only members of a queue can claim cases from that queue.
    If a queue has no members, it's open to all case_manager+ users.
    """

    __tablename__ = "queue_members"
    __table_args__ = (
        UniqueConstraint("queue_id", "user_id", name="uq_queue_member"),
        Index("idx_queue_members_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queues.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    queue: Mapped["Queue"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()


# =============================================================================
# Surrogate Management Models
# =============================================================================
