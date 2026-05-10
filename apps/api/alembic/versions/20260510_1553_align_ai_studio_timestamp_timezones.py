"""align ai studio timestamp timezones

Revision ID: 20260510_1553
Revises: 20260509_1515
Create Date: 2026-05-10 15:53:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260510_1553"
down_revision: str | Sequence[str] | None = "20260509_1515"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


AI_STUDIO_TIMESTAMP_COLUMNS = (
    ("ai_studio_drafts", "created_at"),
    ("ai_studio_drafts", "updated_at"),
    ("ai_studio_settings", "created_at"),
    ("ai_studio_settings", "updated_at"),
)


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _to_timestamptz(table_name: str, column_name: str) -> None:
    op.execute(
        f"ALTER TABLE {table_name} "
        f"ALTER COLUMN {column_name} TYPE TIMESTAMPTZ "
        f"USING {column_name} AT TIME ZONE 'UTC'"
    )


def _to_timestamp(table_name: str, column_name: str) -> None:
    op.execute(
        f"ALTER TABLE {table_name} "
        f"ALTER COLUMN {column_name} TYPE TIMESTAMP WITHOUT TIME ZONE "
        f"USING {column_name} AT TIME ZONE 'UTC'"
    )


def upgrade() -> None:
    for table_name, column_name in AI_STUDIO_TIMESTAMP_COLUMNS:
        if _has_column(table_name, column_name):
            _to_timestamptz(table_name, column_name)


def downgrade() -> None:
    for table_name, column_name in reversed(AI_STUDIO_TIMESTAMP_COLUMNS):
        if _has_column(table_name, column_name):
            _to_timestamp(table_name, column_name)
