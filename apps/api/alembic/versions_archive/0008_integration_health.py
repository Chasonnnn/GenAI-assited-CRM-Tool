"""Week 10: Integration Health + System Alerts + Request Metrics

Revision ID: 0008_integration_health
Revises: 0007_entity_notes
Create Date: 2025-12-16

Tables:
- integration_health: Per-integration status tracking
- integration_error_rollup: Hourly error counts
- system_alerts: Deduplicated actionable alerts
- request_metrics_rollup: Aggregated API metrics
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = "0008_integration_health"
down_revision = "0006_meta_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # integration_health - per integration status tracking
    op.create_table(
        "integration_health",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "integration_type", sa.String(50), nullable=False
        ),  # meta_leads, meta_capi, worker
        sa.Column(
            "integration_key", sa.String(255), nullable=True
        ),  # page_id for multi-page support
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="healthy"
        ),  # healthy, degraded, error
        sa.Column(
            "config_status", sa.String(30), nullable=False, server_default="configured"
        ),  # configured, missing_token, expired_token
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_integration_health_org_type",
        "integration_health",
        ["organization_id", "integration_type"],
    )
    op.create_unique_constraint(
        "uq_integration_health_org_type_key",
        "integration_health",
        ["organization_id", "integration_type", "integration_key"],
    )

    # integration_error_rollup - hourly error counts for computing 24h totals
    op.create_table(
        "integration_error_rollup",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("integration_type", sa.String(50), nullable=False),
        sa.Column("integration_key", sa.String(255), nullable=True),
        sa.Column(
            "period_start", sa.DateTime(timezone=True), nullable=False
        ),  # Hour bucket
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_integration_error_rollup_lookup",
        "integration_error_rollup",
        ["organization_id", "integration_type", "period_start"],
    )
    op.create_unique_constraint(
        "uq_integration_error_rollup",
        "integration_error_rollup",
        ["organization_id", "integration_type", "integration_key", "period_start"],
    )

    # system_alerts - deduplicated actionable alerts
    op.create_table(
        "system_alerts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(64), nullable=False),  # Fingerprint hash
        sa.Column("integration_key", sa.String(255), nullable=True),  # page_id etc
        sa.Column(
            "alert_type", sa.String(50), nullable=False
        ),  # meta_fetch_failed, worker_job_failed, etc
        sa.Column(
            "severity", sa.String(20), nullable=False, server_default="error"
        ),  # warn, error, critical
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="open"
        ),  # open, acknowledged, resolved, snoozed
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("occurrence_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=True),  # Additional context (PII-redacted)
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_system_alerts_org_status",
        "system_alerts",
        ["organization_id", "status", "severity"],
    )
    op.create_unique_constraint(
        "uq_system_alerts_dedupe", "system_alerts", ["organization_id", "dedupe_key"]
    )

    # request_metrics_rollup - aggregated API metrics (multi-replica safe with upserts)
    op.create_table(
        "request_metrics_rollup",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id", UUID(as_uuid=True), nullable=True
        ),  # Null for unauthenticated requests
        sa.Column(
            "period_start", sa.DateTime(timezone=True), nullable=False
        ),  # Minute bucket
        sa.Column(
            "period_type", sa.String(10), nullable=False, server_default="minute"
        ),  # minute, hour
        sa.Column("route", sa.String(100), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_2xx", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status_4xx", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status_5xx", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_request_metrics_period",
        "request_metrics_rollup",
        ["period_start", "period_type"],
    )
    op.create_unique_constraint(
        "uq_request_metrics_rollup",
        "request_metrics_rollup",
        ["organization_id", "period_start", "route", "method"],
    )


def downgrade() -> None:
    op.drop_table("request_metrics_rollup")
    op.drop_table("system_alerts")
    op.drop_table("integration_error_rollup")
    op.drop_table("integration_health")
