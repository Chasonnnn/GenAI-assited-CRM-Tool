"""add fax, pcp provider, and lab clinic fields to surrogates

Revision ID: 20260315_1200
Revises: faed99d040d9
Create Date: 2026-03-15 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260315_1200"
down_revision: str | Sequence[str] | None = "faed99d040d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade() -> None:
    # Fax fields for existing sections
    if not _column_exists("surrogates", "insurance_fax"):
        op.add_column("surrogates", sa.Column("insurance_fax", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "clinic_fax"):
        op.add_column("surrogates", sa.Column("clinic_fax", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "monitoring_clinic_fax"):
        op.add_column("surrogates", sa.Column("monitoring_clinic_fax", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "ob_fax"):
        op.add_column("surrogates", sa.Column("ob_fax", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "delivery_hospital_fax"):
        op.add_column("surrogates", sa.Column("delivery_hospital_fax", sa.Text(), nullable=True))

    # PCP Provider
    if not _column_exists("surrogates", "pcp_provider_name"):
        op.add_column("surrogates", sa.Column("pcp_provider_name", sa.String(255), nullable=True))
    if not _column_exists("surrogates", "pcp_name"):
        op.add_column("surrogates", sa.Column("pcp_name", sa.String(255), nullable=True))
    if not _column_exists("surrogates", "pcp_address_line1"):
        op.add_column("surrogates", sa.Column("pcp_address_line1", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "pcp_address_line2"):
        op.add_column("surrogates", sa.Column("pcp_address_line2", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "pcp_city"):
        op.add_column("surrogates", sa.Column("pcp_city", sa.String(100), nullable=True))
    if not _column_exists("surrogates", "pcp_state"):
        op.add_column("surrogates", sa.Column("pcp_state", sa.String(2), nullable=True))
    if not _column_exists("surrogates", "pcp_postal"):
        op.add_column("surrogates", sa.Column("pcp_postal", sa.String(20), nullable=True))
    if not _column_exists("surrogates", "pcp_phone"):
        op.add_column("surrogates", sa.Column("pcp_phone", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "pcp_fax"):
        op.add_column("surrogates", sa.Column("pcp_fax", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "pcp_email"):
        op.add_column("surrogates", sa.Column("pcp_email", sa.Text(), nullable=True))

    # Lab Clinic
    if not _column_exists("surrogates", "lab_clinic_name"):
        op.add_column("surrogates", sa.Column("lab_clinic_name", sa.String(255), nullable=True))
    if not _column_exists("surrogates", "lab_clinic_address_line1"):
        op.add_column("surrogates", sa.Column("lab_clinic_address_line1", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "lab_clinic_address_line2"):
        op.add_column("surrogates", sa.Column("lab_clinic_address_line2", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "lab_clinic_city"):
        op.add_column("surrogates", sa.Column("lab_clinic_city", sa.String(100), nullable=True))
    if not _column_exists("surrogates", "lab_clinic_state"):
        op.add_column("surrogates", sa.Column("lab_clinic_state", sa.String(2), nullable=True))
    if not _column_exists("surrogates", "lab_clinic_postal"):
        op.add_column("surrogates", sa.Column("lab_clinic_postal", sa.String(20), nullable=True))
    if not _column_exists("surrogates", "lab_clinic_phone"):
        op.add_column("surrogates", sa.Column("lab_clinic_phone", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "lab_clinic_fax"):
        op.add_column("surrogates", sa.Column("lab_clinic_fax", sa.Text(), nullable=True))
    if not _column_exists("surrogates", "lab_clinic_email"):
        op.add_column("surrogates", sa.Column("lab_clinic_email", sa.Text(), nullable=True))


def downgrade() -> None:
    # Lab Clinic (reverse order)
    op.drop_column("surrogates", "lab_clinic_email")
    op.drop_column("surrogates", "lab_clinic_fax")
    op.drop_column("surrogates", "lab_clinic_phone")
    op.drop_column("surrogates", "lab_clinic_postal")
    op.drop_column("surrogates", "lab_clinic_state")
    op.drop_column("surrogates", "lab_clinic_city")
    op.drop_column("surrogates", "lab_clinic_address_line2")
    op.drop_column("surrogates", "lab_clinic_address_line1")
    op.drop_column("surrogates", "lab_clinic_name")

    # PCP Provider (reverse order)
    op.drop_column("surrogates", "pcp_email")
    op.drop_column("surrogates", "pcp_fax")
    op.drop_column("surrogates", "pcp_phone")
    op.drop_column("surrogates", "pcp_postal")
    op.drop_column("surrogates", "pcp_state")
    op.drop_column("surrogates", "pcp_city")
    op.drop_column("surrogates", "pcp_address_line2")
    op.drop_column("surrogates", "pcp_address_line1")
    op.drop_column("surrogates", "pcp_name")
    op.drop_column("surrogates", "pcp_provider_name")

    # Fax fields (reverse order)
    op.drop_column("surrogates", "delivery_hospital_fax")
    op.drop_column("surrogates", "ob_fax")
    op.drop_column("surrogates", "monitoring_clinic_fax")
    op.drop_column("surrogates", "clinic_fax")
    op.drop_column("surrogates", "insurance_fax")
