"""Persist sanitized, fenced Resend readiness snapshots.

Revision ID: 20260723_0260
Revises: 20260723_0250
Create Date: 2026-07-23 21:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260723_0260"
down_revision = "20260723_0250"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resend_readiness_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_scope", sa.String(length=20), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("probe_status", sa.String(length=20), nullable=False),
        sa.Column("overall_status", sa.String(length=30), nullable=False),
        sa.Column("domain_status", sa.String(length=30), nullable=False),
        sa.Column("webhook_status", sa.String(length=30), nullable=False),
        sa.Column("sending_status", sa.String(length=30), nullable=False),
        sa.Column("delivery_tracking_status", sa.String(length=30), nullable=False),
        sa.Column("engagement_tracking_status", sa.String(length=30), nullable=False),
        sa.Column("verified_domain_count", sa.Integer(), nullable=False),
        sa.Column("enabled_webhook_count", sa.Integer(), nullable=False),
        sa.Column(
            "issue_codes",
            postgresql.ARRAY(sa.String(length=50)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column(
            "probe_started_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "checked_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_success_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider_scope IN ('platform', 'organization')",
            name="ck_resend_readiness_snapshot_scope",
        ),
        sa.CheckConstraint(
            "(provider_scope = 'platform' "
            "AND organization_id IS NULL "
            "AND provider_account_id = 'platform:default') "
            "OR (provider_scope = 'organization' "
            "AND organization_id IS NOT NULL "
            "AND provider_account_id = ('organization:' || organization_id::text))",
            name="ck_resend_readiness_snapshot_scope_coherence",
        ),
        sa.CheckConstraint(
            "probe_status IN ('succeeded', 'limited', 'failed')",
            name="ck_resend_readiness_snapshot_probe_status",
        ),
        sa.CheckConstraint(
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
        sa.CheckConstraint(
            "verified_domain_count >= 0 AND enabled_webhook_count >= 0",
            name="ck_resend_readiness_snapshot_counts",
        ),
        sa.CheckConstraint(
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
        sa.CheckConstraint(
            "config_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_resend_readiness_snapshot_fingerprint",
        ),
        sa.CheckConstraint(
            "checked_at >= probe_started_at",
            name="ck_resend_readiness_snapshot_probe_window",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_scope",
            "provider_account_id",
            name="uq_resend_readiness_snapshot_route",
        ),
    )
    op.create_index(
        "uq_resend_readiness_snapshot_org",
        "resend_readiness_snapshots",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("provider_scope = 'organization'"),
    )
    op.create_index(
        "uq_resend_readiness_snapshot_platform",
        "resend_readiness_snapshots",
        ["provider_scope"],
        unique=True,
        postgresql_where=sa.text("provider_scope = 'platform'"),
    )
    op.create_index(
        "ix_resend_readiness_snapshot_checked",
        "resend_readiness_snapshots",
        ["checked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resend_readiness_snapshot_checked",
        table_name="resend_readiness_snapshots",
    )
    op.drop_index(
        "uq_resend_readiness_snapshot_platform",
        table_name="resend_readiness_snapshots",
    )
    op.drop_index(
        "uq_resend_readiness_snapshot_org",
        table_name="resend_readiness_snapshots",
    )
    op.drop_table("resend_readiness_snapshots")
