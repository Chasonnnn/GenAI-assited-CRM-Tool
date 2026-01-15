"""Add appointment token expiry fields.

Revision ID: 0043_appointment_token_expiry
Revises: 0042_appointments
Create Date: 2025-12-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0043_appointment_token_expiry"
down_revision = "0042_appointments"
branch_labels = None
depends_on = None


def upgrade():
    """Add token expiry timestamps to appointments."""
    op.add_column(
        "appointments",
        sa.Column("reschedule_token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("cancel_token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Backfill existing appointments with default expiry (end time + 7 days)
    op.execute(
        """
        UPDATE appointments
        SET reschedule_token_expires_at = scheduled_end + INTERVAL '7 days',
            cancel_token_expires_at = scheduled_end + INTERVAL '7 days'
        WHERE scheduled_end IS NOT NULL
        """
    )


def downgrade():
    """Remove token expiry timestamps from appointments."""
    op.drop_column("appointments", "cancel_token_expires_at")
    op.drop_column("appointments", "reschedule_token_expires_at")
