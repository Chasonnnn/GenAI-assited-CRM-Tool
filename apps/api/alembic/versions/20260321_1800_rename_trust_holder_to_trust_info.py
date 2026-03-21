"""rename trust holder fields to trust info

Revision ID: 20260321_1800
Revises: 20260321_1700
Create Date: 2026-03-21 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260321_1800"
down_revision: str | Sequence[str] | None = "20260321_1700"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "intended_parents"

_RENAMED_COLUMNS: list[tuple[str, str]] = [
    ("trust_holder_name", "trust_provider_name"),
    ("trust_holder_email", "trust_email"),
    ("trust_holder_phone", "trust_phone"),
    ("trust_holder_address_line1", "trust_address_line1"),
    ("trust_holder_address_line2", "trust_address_line2"),
    ("trust_holder_city", "trust_city"),
    ("trust_holder_state", "trust_state"),
    ("trust_holder_postal", "trust_postal"),
]

_ADDITIONAL_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("trust_primary_contact_name", sa.String(255)),
    ("trust_case_reference", sa.String(255)),
    ("trust_funding_status", sa.String(50)),
    ("trust_portal_url", sa.Text()),
    ("trust_notes", sa.Text()),
]


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade() -> None:
    for old_name, new_name in _RENAMED_COLUMNS:
        if _column_exists(_TABLE, old_name) and not _column_exists(_TABLE, new_name):
            op.alter_column(_TABLE, old_name, new_column_name=new_name)

    for column_name, column_type in _ADDITIONAL_COLUMNS:
        if not _column_exists(_TABLE, column_name):
            op.add_column(_TABLE, sa.Column(column_name, column_type, nullable=True))


def downgrade() -> None:
    for column_name, _ in reversed(_ADDITIONAL_COLUMNS):
        if _column_exists(_TABLE, column_name):
            op.drop_column(_TABLE, column_name)

    for old_name, new_name in reversed(_RENAMED_COLUMNS):
        if _column_exists(_TABLE, new_name) and not _column_exists(_TABLE, old_name):
            op.alter_column(_TABLE, new_name, new_column_name=old_name)
