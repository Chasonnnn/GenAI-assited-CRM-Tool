"""add ai studio image output settings

Revision ID: 20260509_1515
Revises: 20260509_1500
Create Date: 2026-05-09 15:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260509_1515"
down_revision: str | Sequence[str] | None = "20260509_1500"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("ai_studio_drafts", "image_size"):
        op.add_column(
            "ai_studio_drafts",
            sa.Column(
                "image_size",
                sa.String(length=30),
                server_default=sa.text("'auto'"),
                nullable=False,
            ),
        )
    if not _has_column("ai_studio_drafts", "image_quality"):
        op.add_column(
            "ai_studio_drafts",
            sa.Column(
                "image_quality",
                sa.String(length=20),
                server_default=sa.text("'auto'"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    if _has_column("ai_studio_drafts", "image_quality"):
        op.drop_column("ai_studio_drafts", "image_quality")
    if _has_column("ai_studio_drafts", "image_size"):
        op.drop_column("ai_studio_drafts", "image_size")
