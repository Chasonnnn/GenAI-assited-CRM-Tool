"""Track exact Google appointment links and synchronization state.

Revision ID: 20260921_0100_google_appointment_sync
Revises: 20260920_0200_donor_zapier_reporting
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260921_0100_google_appointment_sync"
down_revision = "20260920_0200_donor_zapier_reporting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.add_column("appointments", sa.Column("google_calendar_id", sa.String(255)))
    op.add_column("appointments", sa.Column("google_account_email", sa.String(255)))
    op.add_column("appointments", sa.Column("google_integration_id", postgresql.UUID(as_uuid=True)))
    op.add_column("appointments", sa.Column("google_event_etag", sa.String(255)))
    op.add_column(
        "appointments",
        sa.Column("google_sync_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("appointments", sa.Column("google_sync_state", sa.String(20)))
    op.create_foreign_key(
        "fk_appointments_google_integration",
        "appointments",
        "user_integrations",
        ["google_integration_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_appointments_google_sync_revision_nonnegative",
        "appointments",
        "google_sync_revision >= 0",
    )
    op.create_check_constraint(
        "ck_appointments_google_sync_state",
        "appointments",
        "google_sync_state IS NULL OR google_sync_state IN ('pending', 'completed', 'failed', 'conflict', 'unlinked')",
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_constraint("ck_appointments_google_sync_state", "appointments", type_="check")
    op.drop_constraint(
        "ck_appointments_google_sync_revision_nonnegative", "appointments", type_="check"
    )
    op.drop_constraint("fk_appointments_google_integration", "appointments", type_="foreignkey")
    for name in (
        "google_sync_state",
        "google_sync_revision",
        "google_event_etag",
        "google_integration_id",
        "google_calendar_id",
        "google_account_email",
    ):
        op.drop_column("appointments", name)
