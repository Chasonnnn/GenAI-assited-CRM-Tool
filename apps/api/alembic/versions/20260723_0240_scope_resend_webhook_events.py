"""Scope Resend webhook events to their trusted delivery route.

Revision ID: 20260723_0240
Revises: 20260723_0230
Create Date: 2026-07-23 20:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260723_0240"
down_revision = "20260723_0230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resend_webhook_events",
        sa.Column("provider_scope", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "resend_webhook_events",
        sa.Column("provider_account_id", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE resend_webhook_events AS event
        SET provider_scope = email.provider_scope,
            provider_account_id = email.provider_account_id
        FROM email_logs AS email
        WHERE event.email_log_id = email.id
          AND event.organization_id = email.organization_id
          AND email.provider = 'resend'
          AND email.provider_scope IN ('platform', 'organization')
          AND email.provider_account_id IS NOT NULL
          AND btrim(email.provider_account_id) <> ''
        """
    )
    op.create_check_constraint(
        "ck_resend_webhook_events_route",
        "resend_webhook_events",
        "(provider_scope IS NULL AND provider_account_id IS NULL) OR "
        "(provider_scope IN ('platform', 'organization') "
        "AND provider_account_id IS NOT NULL "
        "AND btrim(provider_account_id) <> '')",
    )
    op.create_index(
        "idx_resend_webhook_events_org_route_received",
        "resend_webhook_events",
        [
            "organization_id",
            "provider_scope",
            "provider_account_id",
            "received_at",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_resend_webhook_events_org_route_received",
        table_name="resend_webhook_events",
    )
    op.drop_constraint(
        "ck_resend_webhook_events_route",
        "resend_webhook_events",
        type_="check",
    )
    op.drop_column("resend_webhook_events", "provider_account_id")
    op.drop_column("resend_webhook_events", "provider_scope")
