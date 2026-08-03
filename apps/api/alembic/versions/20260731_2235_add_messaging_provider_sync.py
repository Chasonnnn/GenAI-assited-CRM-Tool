"""Add provider synchronization state for messaging consent.

Revision ID: 20260731_2235
Revises: 20260731_2230
Create Date: 2026-07-31 22:35:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260731_2235"
down_revision = "20260731_2230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_messaging_consent_state_status",
        "messaging_consent_states",
        type_="check",
    )
    op.create_check_constraint(
        "ck_messaging_consent_state_status",
        "messaging_consent_states",
        "status IN ('unknown', 'opted_in', 'opted_out', 'reopt_pending')",
    )
    op.add_column(
        "messaging_consent_states",
        sa.Column(
            "provider_sync_status",
            sa.String(length=20),
            server_default=sa.text("'not_required'"),
            nullable=False,
        ),
    )
    op.add_column(
        "messaging_consent_states",
        sa.Column("provider_sync_error_code", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "messaging_consent_states",
        sa.Column("provider_sync_requested_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "messaging_consent_states",
        sa.Column("provider_synced_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_messaging_consent_state_provider_sync_status",
        "messaging_consent_states",
        "provider_sync_status IN "
        "('not_required', 'pending', 'synced', 'failed', 'unavailable')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_messaging_consent_state_provider_sync_status",
        "messaging_consent_states",
        type_="check",
    )
    op.drop_column("messaging_consent_states", "provider_synced_at")
    op.drop_column("messaging_consent_states", "provider_sync_requested_at")
    op.drop_column("messaging_consent_states", "provider_sync_error_code")
    op.drop_column("messaging_consent_states", "provider_sync_status")
    op.drop_constraint(
        "ck_messaging_consent_state_status",
        "messaging_consent_states",
        type_="check",
    )
    op.create_check_constraint(
        "ck_messaging_consent_state_status",
        "messaging_consent_states",
        "status IN ('unknown', 'opted_in', 'opted_out')",
    )
