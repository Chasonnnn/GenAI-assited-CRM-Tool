"""Add dated medical records and import the flat medical profile columns.

Every nonempty medical or insurance section on a surrogate or donor becomes one
record with source 'import' and an unknown effective date. Encrypted columns
copy their ciphertext unchanged; both sides use the same field-level key.

The flat columns stay in place, unread and unwritten, until production is
verified; a follow-up migration drops them. Downgrade drops the new tables, so
records created after the upgrade are lost while the flat columns keep their
pre-upgrade values.

Revision ID: 20261003_1200_medical_records
Revises: 20260928_1340_zapier_event_effective_at
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261003_1200_medical_records"
down_revision = "20260928_1340_zapier_event_effective_at"
branch_labels = None
depends_on = None

_CONTACT = ("address_line1", "address_line2", "city", "state", "postal", "phone", "fax", "email")

# Record column -> flat column, per section. Frozen here so later model changes
# cannot alter what this migration imported.
SECTION_COLUMNS: dict[str, dict[str, str]] = {
    "insurance": {
        "name": "insurance_company",
        "plan_name": "insurance_plan_name",
        "phone": "insurance_phone",
        "fax": "insurance_fax",
        "policy_number": "insurance_policy_number",
        "member_id": "insurance_member_id",
        "group_number": "insurance_group_number",
        "subscriber_name": "insurance_subscriber_name",
        "subscriber_dob": "insurance_subscriber_dob",
    },
    "pcp": {
        "provider_name": "pcp_provider_name",
        "name": "pcp_name",
        **{column: f"pcp_{column}" for column in _CONTACT},
    },
    "lab_clinic": {
        "name": "lab_clinic_name",
        **{column: f"lab_clinic_{column}" for column in _CONTACT},
    },
    "clinic": {"name": "clinic_name", **{column: f"clinic_{column}" for column in _CONTACT}},
    "monitoring_clinic": {
        "name": "monitoring_clinic_name",
        **{column: f"monitoring_clinic_{column}" for column in _CONTACT},
    },
    "ob": {
        "provider_name": "ob_provider_name",
        "name": "ob_clinic_name",
        **{column: f"ob_{column}" for column in _CONTACT},
    },
    "delivery_hospital": {
        "name": "delivery_hospital_name",
        **{column: f"delivery_hospital_{column}" for column in _CONTACT},
    },
}

_OWNERS = (("surrogates", "surrogate_id"), ("donors", "donor_id"))


def _import_statement(owner_table: str, owner_column: str, section: str) -> str:
    mapping = SECTION_COLUMNS[section]
    targets = ", ".join(mapping)
    sources = ", ".join(f"o.{column}" for column in mapping.values())
    nonempty = " OR ".join(
        f"(o.{column} IS NOT NULL AND o.{column}::text <> '')" for column in mapping.values()
    )
    return (
        f"INSERT INTO medical_records (organization_id, {owner_column}, section, source, {targets}) "
        f"SELECT o.organization_id, o.id, '{section}', 'import', {sources} "
        f"FROM {owner_table} o WHERE {nonempty}"
    )


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.create_table(
        "medical_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "surrogate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("surrogates.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "donor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("donors.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("section", sa.String(32), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("provider_name", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("address_line1", sa.Text(), nullable=True),
        sa.Column("address_line2", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("postal", sa.String(20), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("fax", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("plan_name", sa.String(255), nullable=True),
        sa.Column("policy_number", sa.Text(), nullable=True),
        sa.Column("member_id", sa.Text(), nullable=True),
        sa.Column("group_number", sa.String(100), nullable=True),
        sa.Column("subscriber_name", sa.Text(), nullable=True),
        sa.Column("subscriber_dob", sa.Text(), nullable=True),
        sa.Column("archived_on", sa.Date(), nullable=True),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "archived_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "num_nonnulls(surrogate_id, donor_id) = 1",
            name="ck_medical_records_exactly_one_owner",
        ),
        sa.CheckConstraint(
            "section IN ('insurance', 'pcp', 'lab_clinic', 'clinic', "
            "'monitoring_clinic', 'ob', 'delivery_hospital')",
            name="ck_medical_records_section",
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'import', 'form', 'restore')",
            name="ck_medical_records_source",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_medical_records_revision_positive"),
    )
    op.create_index(
        "idx_medical_records_surrogate_section",
        "medical_records",
        ["organization_id", "surrogate_id", "section"],
    )
    op.create_index(
        "idx_medical_records_donor_section",
        "medical_records",
        ["organization_id", "donor_id", "section"],
    )
    op.create_index(
        "uq_medical_records_idempotency",
        "medical_records",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "medical_record_corrections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medical_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("redacted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.String(20), nullable=False, server_default=sa.text("'manual'")),
        sa.Column(
            "corrected_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "corrected_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_medical_record_corrections_record",
        "medical_record_corrections",
        ["record_id", "corrected_at"],
    )
    op.create_index(
        "idx_medical_record_corrections_org",
        "medical_record_corrections",
        ["organization_id"],
    )

    for owner_table, owner_column in _OWNERS:
        for section in SECTION_COLUMNS:
            op.execute(_import_statement(owner_table, owner_column, section))


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_table("medical_record_corrections")
    op.drop_table("medical_records")
