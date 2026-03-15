"""expand intended parent fields – partner, pronouns, address, IVF clinic

Revision ID: 20260315_1300
Revises: 20260315_1200
Create Date: 2026-03-15 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260315_1300"
down_revision: str | Sequence[str] | None = "20260315_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


_TABLE = "intended_parents"

_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    # Partner
    ("partner_name", sa.String(255)),
    ("partner_email", sa.Text()),
    ("partner_email_hash", sa.String(64)),
    # Pronouns
    ("pronouns", sa.String(50)),
    ("partner_pronouns", sa.String(50)),
    # Address (expand from state-only)
    ("address_line1", sa.Text()),
    ("address_line2", sa.Text()),
    ("city", sa.String(100)),
    ("postal", sa.String(20)),
    # IVF Clinic
    ("ip_clinic_name", sa.String(255)),
    ("ip_clinic_address_line1", sa.Text()),
    ("ip_clinic_address_line2", sa.Text()),
    ("ip_clinic_city", sa.String(100)),
    ("ip_clinic_state", sa.String(2)),
    ("ip_clinic_postal", sa.String(20)),
    ("ip_clinic_phone", sa.Text()),
    ("ip_clinic_fax", sa.Text()),
    ("ip_clinic_email", sa.Text()),
]


def upgrade() -> None:
    for col_name, col_type in _COLUMNS:
        if not _column_exists(_TABLE, col_name):
            op.add_column(_TABLE, sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    for col_name, _ in reversed(_COLUMNS):
        if _column_exists(_TABLE, col_name):
            op.drop_column(_TABLE, col_name)
