"""Add meeting_modes to appointment types.

Revision ID: 20260202_1600
Revises: 20260202_1415
Create Date: 2026-02-02 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260202_1600"
down_revision: str | Sequence[str] | None = "20260202_1415"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "appointment_types",
        sa.Column(
            "meeting_modes",
            postgresql.JSONB(),
            server_default=sa.text("'[\"zoom\"]'::jsonb"),
            nullable=False,
        ),
    )
    op.execute("UPDATE appointment_types SET meeting_modes = jsonb_build_array(meeting_mode)")


def downgrade() -> None:
    op.drop_column("appointment_types", "meeting_modes")
