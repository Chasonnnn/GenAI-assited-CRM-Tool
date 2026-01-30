"""Add appointment type location, dial-in, and auto-approve fields.

Revision ID: 20260131_1500
Revises: 20260131_1200
Create Date: 2026-01-31 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260131_1500"
down_revision: Union[str, Sequence[str], None] = "20260131_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointment_types",
        sa.Column("meeting_location", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "appointment_types",
        sa.Column("dial_in_number", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "appointment_types",
        sa.Column(
            "auto_approve",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "appointments",
        sa.Column("meeting_location", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("dial_in_number", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("appointments", "dial_in_number")
    op.drop_column("appointments", "meeting_location")
    op.drop_column("appointment_types", "auto_approve")
    op.drop_column("appointment_types", "dial_in_number")
    op.drop_column("appointment_types", "meeting_location")
