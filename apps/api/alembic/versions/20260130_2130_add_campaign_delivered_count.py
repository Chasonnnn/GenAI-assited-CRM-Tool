"""Add delivered_count to campaign_runs.

Revision ID: 20260130_2130
Revises: 20260130_1900
Create Date: 2026-01-30 21:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260130_2130"
down_revision: Union[str, Sequence[str], None] = "20260130_1900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaign_runs",
        sa.Column("delivered_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.execute(
        """
        UPDATE campaign_runs cr
        SET delivered_count = sub.count
        FROM (
            SELECT run_id, COUNT(*) AS count
            FROM campaign_recipients
            WHERE status = 'delivered'
            GROUP BY run_id
        ) sub
        WHERE cr.id = sub.run_id
        """
    )
    op.alter_column("campaign_runs", "delivered_count", server_default=None)


def downgrade() -> None:
    op.drop_column("campaign_runs", "delivered_count")
