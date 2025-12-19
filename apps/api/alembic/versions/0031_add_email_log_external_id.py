"""Add external_id to email_logs.

Revision ID: 0031_add_email_log_external_id
Revises: 201ff7c41d70
Create Date: 2025-12-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0031_add_email_log_external_id"
down_revision: Union[str, Sequence[str], None] = "201ff7c41d70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add external_id column to email_logs."""
    op.add_column("email_logs", sa.Column("external_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove external_id column from email_logs."""
    op.drop_column("email_logs", "external_id")
