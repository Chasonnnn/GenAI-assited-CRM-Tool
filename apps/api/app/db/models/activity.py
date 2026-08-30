"""Shared activity persistence for non-surrogate CRM entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Donor, IntendedParent, Organization, User


class EntityActivityLog(Base):
    """Durable safe-metadata activity for Intended Parents and Donors."""

    __tablename__ = "entity_activity_logs"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(intended_parent_id, donor_id) = 1",
            name="ck_entity_activity_exactly_one_subject",
        ),
        Index(
            "idx_entity_activity_ip_time",
            "organization_id",
            "intended_parent_id",
            "occurred_at",
            "id",
        ),
        Index(
            "idx_entity_activity_donor_time",
            "organization_id",
            "donor_id",
            "occurred_at",
            "id",
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
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=True,
    )
    donor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("donors.id", ondelete="CASCADE"),
        nullable=True,
    )
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    organization: Mapped[Organization] = relationship()
    intended_parent: Mapped[IntendedParent | None] = relationship()
    donor: Mapped[Donor | None] = relationship()
    actor: Mapped[User | None] = relationship()
