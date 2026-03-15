"""Intelligent suggestion settings and rule models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization


class OrgIntelligentSuggestionSettings(Base):
    """Organization-level configuration for intelligent suggestion rules."""

    __tablename__ = "org_intelligent_suggestion_settings"
    __table_args__ = (
        CheckConstraint(
            "new_unread_business_days BETWEEN 1 AND 30", name="ck_intel_new_unread_days"
        ),
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

    stuck_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
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


class OrgIntelligentSuggestionRule(Base):
    """Organization-level configurable intelligent suggestion rule."""

    __tablename__ = "org_intelligent_suggestion_rules"
    __table_args__ = (
        CheckConstraint("business_days BETWEEN 1 AND 60", name="ck_intel_rule_business_days"),
        CheckConstraint(
            "rule_kind IN ('stage_inactivity', 'meeting_outcome_missing')",
            name="ck_intel_rule_kind",
        ),
        Index(
            "idx_intel_rules_org_enabled",
            "organization_id",
            "enabled",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    stage_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_days: Mapped[int] = mapped_column(
        Integer,
        server_default=text("1"),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
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
