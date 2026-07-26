"""Link appointment notifications to durable email occurrences.

Revision ID: 20260723_0210
Revises: 20260723_0200
Create Date: 2026-07-23 04:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260723_0210"
down_revision = "20260723_0200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointment_email_logs",
        sa.Column("occurrence_key", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "appointment_email_logs",
        sa.Column("email_log_id", UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE appointment_email_logs
        SET occurrence_key = 'legacy-appointment-email/' || id::text
        WHERE occurrence_key IS NULL
        """
    )
    op.alter_column(
        "appointment_email_logs",
        "occurrence_key",
        existing_type=sa.String(length=256),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_appointment_email_logs_occurrence",
        "appointment_email_logs",
        ["organization_id", "occurrence_key"],
    )
    op.create_unique_constraint(
        "uq_appointment_email_logs_email_log",
        "appointment_email_logs",
        ["email_log_id"],
    )
    op.create_foreign_key(
        "fk_appointment_email_logs_email_log",
        "appointment_email_logs",
        "email_logs",
        ["email_log_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_appointment_email_logs_email_log",
        "appointment_email_logs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_appointment_email_logs_email_log",
        "appointment_email_logs",
        type_="unique",
    )
    op.drop_constraint(
        "uq_appointment_email_logs_occurrence",
        "appointment_email_logs",
        type_="unique",
    )
    op.drop_column("appointment_email_logs", "email_log_id")
    op.drop_column("appointment_email_logs", "occurrence_key")
