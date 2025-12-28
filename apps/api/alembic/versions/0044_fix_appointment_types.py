"""Fix appointment column types to CITEXT and TIMESTAMPTZ.

Revision ID: 0044_fix_appointment_types
Revises: bd48fc289751
Create Date: 2024-12-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0044_fix_appointment_types"
down_revision = "bd48fc289751"
branch_labels = None
depends_on = None


def upgrade():
    """Fix column types for appointments tables."""

    # Fix client_email to CITEXT
    op.alter_column(
        "appointments",
        "client_email",
        type_=postgresql.CITEXT(),
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    # Fix recipient_email to CITEXT
    op.alter_column(
        "appointment_email_logs",
        "recipient_email",
        type_=postgresql.CITEXT(),
        existing_type=sa.Text(),
        existing_nullable=False,
    )

    # Fix TIMESTAMP to TIMESTAMPTZ for appointment_types
    op.alter_column(
        "appointment_types",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "appointment_types",
        "updated_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )

    # Fix TIMESTAMP to TIMESTAMPTZ for availability_rules
    op.alter_column(
        "availability_rules",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "availability_rules",
        "updated_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )

    # Fix TIMESTAMP to TIMESTAMPTZ for availability_overrides
    op.alter_column(
        "availability_overrides",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )

    # Fix TIMESTAMP to TIMESTAMPTZ for booking_links
    op.alter_column(
        "booking_links",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "booking_links",
        "updated_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )

    # Fix TIMESTAMP to TIMESTAMPTZ for appointments
    op.alter_column(
        "appointments",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "appointments",
        "updated_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )

    # Fix TIMESTAMP to TIMESTAMPTZ for appointment_email_logs
    op.alter_column(
        "appointment_email_logs",
        "created_at",
        type_=sa.TIMESTAMP(timezone=True),
        existing_type=sa.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )


def downgrade():
    """Revert column types."""
    # Revert CITEXT to TEXT
    op.alter_column(
        "appointments",
        "client_email",
        type_=sa.Text(),
        existing_type=postgresql.CITEXT(),
        existing_nullable=False,
    )
    op.alter_column(
        "appointment_email_logs",
        "recipient_email",
        type_=sa.Text(),
        existing_type=postgresql.CITEXT(),
        existing_nullable=False,
    )

    # Revert TIMESTAMPTZ to TIMESTAMP (all created_at/updated_at columns)
    for table in [
        "appointment_types",
        "availability_rules",
        "booking_links",
        "appointments",
    ]:
        op.alter_column(
            table,
            "created_at",
            type_=sa.TIMESTAMP(),
            existing_type=sa.TIMESTAMP(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.text("now()"),
        )
        if table != "availability_overrides":
            op.alter_column(
                table,
                "updated_at",
                type_=sa.TIMESTAMP(),
                existing_type=sa.TIMESTAMP(timezone=True),
                existing_nullable=False,
                existing_server_default=sa.text("now()"),
            )

    op.alter_column(
        "availability_overrides",
        "created_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )

    op.alter_column(
        "appointment_email_logs",
        "created_at",
        type_=sa.TIMESTAMP(),
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
