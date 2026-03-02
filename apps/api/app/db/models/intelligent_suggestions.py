"""Intelligent suggestion settings models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization


class OrgIntelligentSuggestionSettings(Base):
    """Organization-level configuration for intelligent suggestion rules."""

    __tablename__ = "org_intelligent_suggestion_settings"
    __table_args__ = (
        CheckConstraint("new_unread_business_days BETWEEN 1 AND 30", name="ck_intel_new_unread_days"),
        CheckConstraint(
            "meeting_outcome_business_days BETWEEN 1 AND 30",
            name="ck_intel_meeting_outcome_days",
        ),
        CheckConstraint("stuck_business_days BETWEEN 1 AND 60", name="ck_intel_stuck_days"),
        CheckConstraint("digest_hour_local BETWEEN 0 AND 23", name="ck_intel_digest_hour"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)

    new_unread_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    new_unread_business_days: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )

    meeting_outcome_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    meeting_outcome_business_days: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )

    stuck_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    stuck_business_days: Mapped[int] = mapped_column(
        Integer, server_default=text("5"), nullable=False
    )

    daily_digest_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    digest_hour_local: Mapped[int] = mapped_column(
        Integer, server_default=text("9"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship()
