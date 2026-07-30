"""add appointment buffer snapshots

Revision ID: b2a7e1c9f4d0
Revises: a4f2c9b7e1d3
Create Date: 2025-12-26 13:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2a7e1c9f4d0"
down_revision: str | Sequence[str] | None = "a4f2c9b7e1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "appointments",
        sa.Column(
            "buffer_before_minutes",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "buffer_after_minutes",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )

    op.execute("""
        UPDATE appointments a
        SET
            buffer_before_minutes = COALESCE(at.buffer_before_minutes, 0),
            buffer_after_minutes = COALESCE(at.buffer_after_minutes, 0)
        FROM appointment_types at
        WHERE a.appointment_type_id = at.id;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("appointments", "buffer_after_minutes")
    op.drop_column("appointments", "buffer_before_minutes")
