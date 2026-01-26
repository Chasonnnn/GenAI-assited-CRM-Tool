"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
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
    from app.db.models import User


class IntegrationHealth(Base):
    """
    Per-integration health status tracking.

    Tracks the health of integrations like Meta Leads, CAPI, etc.
    integration_key is nullable for now but allows per-page tracking later.
    """

    __tablename__ = "integration_health"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    integration_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="healthy", server_default=text("'healthy'")
    )
    config_status: Mapped[str] = mapped_column(
        String(30), default="configured", server_default=text("'configured'")
    )
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (
        Index("ix_integration_health_org_type", "organization_id", "integration_type"),
        Index(
            "uq_integration_health_org_type_null_key",
            "organization_id",
            "integration_type",
            unique=True,
            postgresql_where=text("integration_key IS NULL"),
        ),
        UniqueConstraint(
            "organization_id",
            "integration_type",
            "integration_key",
            name="uq_integration_health_org_type_key",
        ),
    )


class IntegrationErrorRollup(Base):
    """
    Hourly error counts per integration.

    Used to compute "errors in last 24h" as SUM(error_count) WHERE period_start > now() - 24h.
    Avoids storing raw events while maintaining accurate counts.
    """

    __tablename__ = "integration_error_rollup"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    integration_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    period_start: Mapped[datetime] = mapped_column(nullable=False)  # Hour bucket
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (
        Index(
            "ix_integration_error_rollup_lookup",
            "organization_id",
            "integration_type",
            "period_start",
        ),
        Index(
            "uq_integration_error_rollup_null_key",
            "organization_id",
            "integration_type",
            "period_start",
            unique=True,
            postgresql_where=text("integration_key IS NULL"),
        ),
        UniqueConstraint(
            "organization_id",
            "integration_type",
            "integration_key",
            "period_start",
            name="uq_integration_error_rollup",
        ),
    )


class SystemAlert(Base):
    """
    Deduplicated actionable alerts.

    Alerts are grouped by dedupe_key (fingerprint hash).
    Occurrence count tracks how many times the same issue occurred.
    """

    __tablename__ = "system_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), default="error", server_default=text("'error'")
    )
    status: Mapped[str] = mapped_column(String(20), default="open", server_default=text("'open'"))
    first_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_system_alerts_org_status", "organization_id", "status", "severity"),
        UniqueConstraint("organization_id", "dedupe_key", name="uq_system_alerts_dedupe"),
    )

    # Relationships
    resolved_by: Mapped["User | None"] = relationship()
