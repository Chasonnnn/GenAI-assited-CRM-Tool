"""Drop the flat medical profile columns replaced by medical_records.

20261003_1700_medical_records imported these columns and production was
verified on the imported records (ADR 0006). Downgrade re-adds the columns
empty and nullable; the 20261003_1700 application version does not read them.

Revision ID: 20261004_1000_drop_flat_medical_columns
Revises: 20261003_1800_timezone_aware_form_timestamps
"""

import sqlalchemy as sa

from alembic import op

revision = "20261004_1000_drop_flat_medical_columns"
down_revision = "20261003_1800_timezone_aware_form_timestamps"
branch_labels = None
depends_on = None

_OWNER_TABLES = ("surrogates", "donors")

_CONTACT_TYPES: dict[str, sa.types.TypeEngine] = {
    "address_line1": sa.Text(),
    "address_line2": sa.Text(),
    "city": sa.String(100),
    "state": sa.String(2),
    "postal": sa.String(20),
    "phone": sa.Text(),
    "fax": sa.Text(),
    "email": sa.Text(),
}


def _contact(prefix: str) -> dict[str, sa.types.TypeEngine]:
    return {f"{prefix}_{column}": type_ for column, type_ in _CONTACT_TYPES.items()}


# Column -> type as it exists on both owner tables. Frozen here so later model
# changes cannot alter what downgrade restores.
FLAT_COLUMNS: dict[str, sa.types.TypeEngine] = {
    "insurance_company": sa.String(255),
    "insurance_plan_name": sa.String(255),
    "insurance_phone": sa.Text(),
    "insurance_fax": sa.Text(),
    "insurance_policy_number": sa.Text(),
    "insurance_member_id": sa.Text(),
    "insurance_group_number": sa.String(100),
    "insurance_subscriber_name": sa.Text(),
    "insurance_subscriber_dob": sa.Text(),
    "pcp_provider_name": sa.String(255),
    "pcp_name": sa.String(255),
    **_contact("pcp"),
    "lab_clinic_name": sa.String(255),
    **_contact("lab_clinic"),
    "clinic_name": sa.String(255),
    **_contact("clinic"),
    "monitoring_clinic_name": sa.String(255),
    **_contact("monitoring_clinic"),
    "ob_provider_name": sa.String(255),
    "ob_clinic_name": sa.String(255),
    **_contact("ob"),
    "delivery_hospital_name": sa.String(255),
    **_contact("delivery_hospital"),
}


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    for table in _OWNER_TABLES:
        drops = ", ".join(f"DROP COLUMN IF EXISTS {column}" for column in FLAT_COLUMNS)
        op.execute(f"ALTER TABLE {table} {drops}")


def downgrade() -> None:
    for table in _OWNER_TABLES:
        for column, type_ in FLAT_COLUMNS.items():
            op.add_column(table, sa.Column(column, type_, nullable=True))
