"""Add source-linked email reconciliation cases.

Revision ID: 20260723_0220
Revises: 20260723_0210
Create Date: 2026-07-23 17:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260723_0220"
down_revision = "20260723_0210"
branch_labels = None
depends_on = None


def _backfill_reconciliation_cases(connection) -> None:
    """Backfill only source identifiers and controlled reconciliation codes."""
    connection.execute(
        sa.text(
            """
            INSERT INTO email_reconciliation_cases (
                organization_id,
                case_type,
                status,
                reason_code,
                resend_webhook_event_id,
                detected_at,
                updated_at
            )
            SELECT
                event.organization_id,
                'orphan_webhook',
                'pending',
                'correlation_pending',
                event.id,
                event.received_at,
                event.received_at
            FROM resend_webhook_events AS event
            WHERE event.processed_at IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM email_reconciliation_cases AS existing
                  WHERE existing.organization_id = event.organization_id
                    AND existing.resend_webhook_event_id = event.id
              )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO email_reconciliation_cases (
                organization_id,
                case_type,
                status,
                reason_code,
                email_delivery_id,
                detected_at,
                updated_at
            )
            SELECT
                delivery.organization_id,
                'unknown_delivery',
                'action_required',
                CASE delivery.last_error_type
                    WHEN 'idempotency_window_expired' THEN 'idempotency_window_expired'
                    WHEN 'lease_expired' THEN 'delivery_lease_expired'
                    WHEN 'provider_outcome_unknown' THEN 'provider_outcome_unknown'
                    ELSE 'provider_outcome_unknown'
                END,
                delivery.id,
                COALESCE(delivery.completed_at, delivery.updated_at, delivery.created_at),
                COALESCE(delivery.completed_at, delivery.updated_at, delivery.created_at)
            FROM email_deliveries AS delivery
            WHERE delivery.status = 'reconciliation_required'
              AND NOT EXISTS (
                  SELECT 1
                  FROM email_reconciliation_cases AS existing
                  WHERE existing.organization_id = delivery.organization_id
                    AND existing.email_delivery_id = delivery.id
              )
            """
        )
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_resend_webhook_events_org_id",
        "resend_webhook_events",
        ["organization_id", "id"],
    )
    op.create_table(
        "email_reconciliation_cases",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("case_type", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("resend_webhook_event_id", UUID(as_uuid=True), nullable=True),
        sa.Column("email_delivery_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "detected_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_code", sa.String(length=80), nullable=True),
        sa.CheckConstraint(
            "case_type IN ('orphan_webhook', 'unknown_delivery')",
            name="ck_email_reconciliation_cases_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'action_required', 'resolved', 'dismissed')",
            name="ck_email_reconciliation_cases_status",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_email_reconciliation_cases_version",
        ),
        sa.CheckConstraint(
            "((case_type = 'orphan_webhook' "
            "AND resend_webhook_event_id IS NOT NULL "
            "AND email_delivery_id IS NULL) "
            "OR (case_type = 'unknown_delivery' "
            "AND email_delivery_id IS NOT NULL "
            "AND resend_webhook_event_id IS NULL))",
            name="ck_email_reconciliation_cases_source",
        ),
        sa.CheckConstraint(
            "((status IN ('resolved', 'dismissed') "
            "AND resolved_at IS NOT NULL AND resolution_code IS NOT NULL) "
            "OR (status NOT IN ('resolved', 'dismissed') "
            "AND resolved_at IS NULL AND resolution_code IS NULL))",
            name="ck_email_reconciliation_cases_resolution",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "resend_webhook_event_id"],
            ["resend_webhook_events.organization_id", "resend_webhook_events.id"],
            name="fk_email_reconciliation_cases_org_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "email_delivery_id"],
            ["email_deliveries.organization_id", "email_deliveries.id"],
            name="fk_email_reconciliation_cases_org_delivery",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_email_reconciliation_cases_org_id",
        ),
    )
    op.create_index(
        "uq_email_reconciliation_cases_event",
        "email_reconciliation_cases",
        ["organization_id", "resend_webhook_event_id"],
        unique=True,
        postgresql_where=sa.text("resend_webhook_event_id IS NOT NULL"),
    )
    op.create_index(
        "uq_email_reconciliation_cases_delivery",
        "email_reconciliation_cases",
        ["organization_id", "email_delivery_id"],
        unique=True,
        postgresql_where=sa.text("email_delivery_id IS NOT NULL"),
    )
    op.create_index(
        "idx_email_reconciliation_cases_org_status_detected",
        "email_reconciliation_cases",
        ["organization_id", "status", "detected_at", "id"],
    )
    _backfill_reconciliation_cases(op.get_bind())


def downgrade() -> None:
    op.drop_index(
        "idx_email_reconciliation_cases_org_status_detected",
        table_name="email_reconciliation_cases",
    )
    op.drop_index(
        "uq_email_reconciliation_cases_delivery",
        table_name="email_reconciliation_cases",
    )
    op.drop_index(
        "uq_email_reconciliation_cases_event",
        table_name="email_reconciliation_cases",
    )
    op.drop_table("email_reconciliation_cases")
    op.drop_constraint(
        "uq_resend_webhook_events_org_id",
        "resend_webhook_events",
        type_="unique",
    )
