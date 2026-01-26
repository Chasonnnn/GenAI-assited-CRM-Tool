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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization


class RequestMetricsRollup(Base):
    """
    Aggregated API request metrics.

    Uses DB upserts (ON CONFLICT DO UPDATE) for multi-replica safety.
    Keyed by (org_id, period_start, route, method) so multiple workers can safely increment.
    """

    __tablename__ = "request_metrics_rollup"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # Null for unauthenticated requests
    )
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(10), default="minute", server_default=text("'minute'")
    )
    route: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_2xx: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    status_4xx: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    status_5xx: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    request_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    __table_args__ = (
        Index("ix_request_metrics_period", "period_start", "period_type"),
        Index(
            "uq_request_metrics_rollup_null_org",
            "period_start",
            "route",
            "method",
            unique=True,
            postgresql_where=text("organization_id IS NULL"),
        ),
        UniqueConstraint(
            "organization_id",
            "period_start",
            "route",
            "method",
            name="uq_request_metrics_rollup",
        ),
    )


# =============================================================================
# Analytics Snapshots (Cached aggregates)
# =============================================================================


class AnalyticsSnapshot(Base):
    """
    Cached analytics payloads for dashboard and reports.

    snapshot_key is a deterministic hash of the request params.
    """

    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "snapshot_key", name="uq_analytics_snapshot_key"),
        Index("idx_analytics_snapshot_org_type", "organization_id", "snapshot_type"),
        Index("idx_analytics_snapshot_expires", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_type: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_key: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    range_start: Mapped[datetime | None] = mapped_column(nullable=True)
    range_end: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    organization: Mapped["Organization"] = relationship()


# =============================================================================
# AI Assistant Models (Week 11)
# =============================================================================
