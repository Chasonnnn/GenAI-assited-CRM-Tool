"""add_email_log_engagement

Revision ID: 20260125_2330
Revises: 20260125_2100
Create Date: 2026-01-25 23:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260125_2330"
down_revision: Union[str, Sequence[str], None] = "20260125_2100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add open/click tracking fields to email_logs."""
    op.add_column(
        "email_logs",
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "email_logs",
        sa.Column("open_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "email_logs",
        sa.Column("clicked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "email_logs",
        sa.Column("click_count", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    """Remove open/click tracking fields from email_logs."""
    op.drop_column("email_logs", "click_count")
    op.drop_column("email_logs", "clicked_at")
    op.drop_column("email_logs", "open_count")
    op.drop_column("email_logs", "opened_at")
