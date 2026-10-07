"""Add organization-scoped messaging consent ledger.

Revision ID: 20260731_2210
Revises: 20260731_2200
Create Date: 2026-07-31 22:10:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260731_2210"
down_revision = "20260731_2200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "messaging_contacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_e164", sa.Text(), nullable=False),
        sa.Column("phone_hash", sa.String(length=64), nullable=False),
        sa.Column("phone_last4", sa.String(length=4), nullable=False),
        sa.Column("intake_lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("meta_lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("surrogate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intake_lead_id"], ["intake_leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["meta_lead_id"], ["meta_leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["surrogate_id"], ["surrogates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "phone_hash", name="uq_messaging_contacts_org_phone"
        ),
    )
    op.create_index("idx_messaging_contacts_org", "messaging_contacts", ["organization_id"])
    op.create_index(
        "idx_messaging_contacts_intake_lead",
        "messaging_contacts",
        ["organization_id", "intake_lead_id"],
    )
    op.create_index(
        "idx_messaging_contacts_meta_lead",
        "messaging_contacts",
        ["organization_id", "meta_lead_id"],
    )
    op.create_index(
        "idx_messaging_contacts_surrogate",
        "messaging_contacts",
        ["organization_id", "surrogate_id"],
    )

    op.create_table(
        "messaging_consent_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("disclosure_text_snapshot", sa.Text(), nullable=True),
        sa.Column("disclosure_hash", sa.String(length=64), nullable=True),
        sa.Column("instruction_text", sa.Text(), nullable=True),
        sa.Column(
            "evidence_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('operational', 'promotional', 'all')",
            name="ck_messaging_consent_evidence_purpose",
        ),
        sa.CheckConstraint(
            "action IN ('opt_in', 'opt_out', 'ambiguous_hold', 'restore')",
            name="ck_messaging_consent_evidence_action",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["messaging_contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_messaging_consent_evidence_org_idempotency",
        ),
    )
    op.create_index(
        "idx_messaging_consent_evidence_timeline",
        "messaging_consent_evidence",
        ["organization_id", "contact_id", "occurred_at"],
    )

    op.create_table(
        "messaging_consent_states",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'unknown'"), nullable=False
        ),
        sa.Column("latest_evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("effective_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('operational', 'promotional')",
            name="ck_messaging_consent_state_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('unknown', 'opted_in', 'opted_out')",
            name="ck_messaging_consent_state_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["messaging_contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["latest_evidence_id"], ["messaging_consent_evidence.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "contact_id", "purpose", name="uq_messaging_consent_state"
        ),
    )
    op.create_index(
        "idx_messaging_consent_states_org_status",
        "messaging_consent_states",
        ["organization_id", "purpose", "status"],
    )

    op.create_table(
        "messaging_global_suppressions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reason", sa.String(length=30), server_default=sa.text("'none'"), nullable=False),
        sa.Column("latest_evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("effective_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason IN ('none', 'global_opt_out', 'ambiguous_hold')",
            name="ck_messaging_global_suppression_reason",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["messaging_contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["latest_evidence_id"], ["messaging_consent_evidence.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "contact_id", name="uq_messaging_global_suppression"
        ),
    )
    op.create_index(
        "idx_messaging_global_suppressions_active",
        "messaging_global_suppressions",
        ["organization_id", "active"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_messaging_global_suppressions_active",
        table_name="messaging_global_suppressions",
    )
    op.drop_table("messaging_global_suppressions")
    op.drop_index("idx_messaging_consent_states_org_status", table_name="messaging_consent_states")
    op.drop_table("messaging_consent_states")
    op.drop_index(
        "idx_messaging_consent_evidence_timeline",
        table_name="messaging_consent_evidence",
    )
    op.drop_table("messaging_consent_evidence")
    op.drop_index("idx_messaging_contacts_surrogate", table_name="messaging_contacts")
    op.drop_index("idx_messaging_contacts_meta_lead", table_name="messaging_contacts")
    op.drop_index("idx_messaging_contacts_intake_lead", table_name="messaging_contacts")
    op.drop_index("idx_messaging_contacts_org", table_name="messaging_contacts")
    op.drop_table("messaging_contacts")
