"""Persisted, sanitized Resend control-plane readiness snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization


class ResendReadinessSnapshot(Base):
    """One fenced readiness cache entry for an exact Resend delivery route."""

    __tablename__ = "resend_readiness_snapshots"
    __table_args__ = (
        CheckConstraint(
            "provider_scope IN ('platform', 'organization')",
            name="ck_resend_readiness_snapshot_scope",
        ),
        CheckConstraint(
            "(provider_scope = 'platform' "
            "AND organization_id IS NULL "
            "AND provider_account_id = 'platform:default') "
            "OR (provider_scope = 'organization' "
            "AND organization_id IS NOT NULL "
            "AND provider_account_id = ('organization:' || organization_id::text))",
            name="ck_resend_readiness_snapshot_scope_coherence",
        ),
        CheckConstraint(
            "probe_status IN ('succeeded', 'limited', 'failed')",
            name="ck_resend_readiness_snapshot_probe_status",
        ),
        CheckConstraint(
            "overall_status IN "
            "('ready', 'needs_attention', 'limited', 'unknown', 'not_configured') "
            "AND domain_status IN "
            "('ready', 'needs_attention', 'limited', 'unknown', 'not_configured') "
            "AND webhook_status IN "
            "('ready', 'needs_attention', 'limited', 'unknown', 'not_configured') "
            "AND sending_status IN "
            "('ready', 'needs_attention', 'limited', 'unknown', 'not_configured') "
            "AND delivery_tracking_status IN "
            "('ready', 'needs_attention', 'limited', 'unknown', 'not_configured') "
            "AND engagement_tracking_status IN "
            "('ready', 'needs_attention', 'limited', 'unknown', 'not_configured')",
            name="ck_resend_readiness_snapshot_statuses",
        ),
        CheckConstraint(
            "verified_domain_count >= 0 AND enabled_webhook_count >= 0",
            name="ck_resend_readiness_snapshot_counts",
        ),
        CheckConstraint(
            "issue_codes <@ ARRAY["
            "'admission_unavailable', "
            "'credential_rejected', "
            "'credential_unavailable', "
            "'delivery_events_missing', "
            "'domain_not_verified', "
            "'engagement_events_missing', "
            "'invalid_provider_response', "
            "'limited_visibility', "
            "'provider_unavailable', "
            "'sending_disabled', "
            "'snapshot_stale', "
            "'timeout', "
            "'webhook_disabled', "
            "'webhook_missing'"
            "]::varchar[] "
            "AND array_position(issue_codes, NULL) IS NULL",
            name="ck_resend_readiness_snapshot_issue_codes",
        ),
        CheckConstraint(
            "config_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_resend_readiness_snapshot_fingerprint",
        ),
        CheckConstraint(
            "checked_at >= probe_started_at",
            name="ck_resend_readiness_snapshot_probe_window",
        ),
        UniqueConstraint(
            "provider_scope",
            "provider_account_id",
            name="uq_resend_readiness_snapshot_route",
        ),
        Index(
            "uq_resend_readiness_snapshot_org",
            "organization_id",
            unique=True,
            postgresql_where=text("provider_scope = 'organization'"),
        ),
        Index(
            "uq_resend_readiness_snapshot_platform",
            "provider_scope",
            unique=True,
            postgresql_where=text("provider_scope = 'platform'"),
        ),
        Index("ix_resend_readiness_snapshot_checked", "checked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    provider_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    probe_status: Mapped[str] = mapped_column(String(20), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(30), nullable=False)
    domain_status: Mapped[str] = mapped_column(String(30), nullable=False)
    webhook_status: Mapped[str] = mapped_column(String(30), nullable=False)
    sending_status: Mapped[str] = mapped_column(String(30), nullable=False)
    delivery_tracking_status: Mapped[str] = mapped_column(String(30), nullable=False)
    engagement_tracking_status: Mapped[str] = mapped_column(String(30), nullable=False)
    verified_domain_count: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled_webhook_count: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        server_default=text("'{}'::varchar[]"),
        nullable=False,
    )
    probe_started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )

    organization: Mapped["Organization | None"] = relationship()
