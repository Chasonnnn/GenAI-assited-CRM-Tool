"""Add Vertex WIF fields to ai_settings.

Revision ID: 20260128_1030
Revises: 20260126_1100
Create Date: 2026-01-28
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260128_1030"
down_revision = "20260126_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_settings", sa.Column("vertex_project_id", sa.String(length=128), nullable=True)
    )
    op.add_column("ai_settings", sa.Column("vertex_location", sa.String(length=64), nullable=True))
    op.add_column("ai_settings", sa.Column("vertex_audience", sa.String(length=255), nullable=True))
    op.add_column(
        "ai_settings",
        sa.Column("vertex_service_account_email", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_settings", "vertex_service_account_email")
    op.drop_column("ai_settings", "vertex_audience")
    op.drop_column("ai_settings", "vertex_location")
    op.drop_column("ai_settings", "vertex_project_id")
