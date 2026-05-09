"""default public intake embeds to enhanced match lead tracking

Revision ID: 20260509_0915
Revises: 20260508_1330
Create Date: 2026-05-09 09:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260509_0915"
down_revision: str | Sequence[str] | None = "20260508_1330"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if _has_column("form_intake_links", "tracking_mode"):
        op.alter_column(
            "form_intake_links",
            "tracking_mode",
            existing_type=sa.String(length=30),
            server_default=sa.text("'enhanced_match_lead'"),
            existing_nullable=False,
        )


def downgrade() -> None:
    if _has_column("form_intake_links", "tracking_mode"):
        op.alter_column(
            "form_intake_links",
            "tracking_mode",
            existing_type=sa.String(length=30),
            server_default=sa.text("'internal_only'"),
            existing_nullable=False,
        )
