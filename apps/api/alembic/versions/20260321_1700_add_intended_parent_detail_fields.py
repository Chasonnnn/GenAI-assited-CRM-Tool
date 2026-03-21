"""add intended parent detail fields

Revision ID: 20260321_1700
Revises: 20260321_1200
Create Date: 2026-03-21 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260321_1700"
down_revision: str | Sequence[str] | None = "20260321_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


_TABLE = "intended_parents"

_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("date_of_birth", sa.Text()),
    ("partner_date_of_birth", sa.Text()),
    ("marital_status", sa.String(100)),
    ("embryo_count", sa.Integer()),
    ("pgs_tested", sa.Boolean()),
    ("egg_source", sa.String(50)),
    ("sperm_source", sa.String(50)),
    ("trust_holder_name", sa.String(255)),
    ("trust_holder_email", sa.Text()),
    ("trust_holder_phone", sa.Text()),
    ("trust_holder_address_line1", sa.Text()),
    ("trust_holder_address_line2", sa.Text()),
    ("trust_holder_city", sa.String(100)),
    ("trust_holder_state", sa.String(2)),
    ("trust_holder_postal", sa.String(20)),
]


def upgrade() -> None:
    for column_name, column_type in _COLUMNS:
        if not _column_exists(_TABLE, column_name):
            op.add_column(_TABLE, sa.Column(column_name, column_type, nullable=True))


def downgrade() -> None:
    for column_name, _ in reversed(_COLUMNS):
        if _column_exists(_TABLE, column_name):
            op.drop_column(_TABLE, column_name)
