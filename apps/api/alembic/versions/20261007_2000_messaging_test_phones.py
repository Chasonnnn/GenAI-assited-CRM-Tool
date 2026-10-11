"""Add code-verified test phones and the record of texts sent to them.

Revision ID: 20261007_2000_messaging_test_phones
Revises: 20261007_1800_drop_messaging_provider_admission
"""

import sqlalchemy as sa

import app.db.types
from alembic import op

revision = "20261007_2000_messaging_test_phones"
down_revision = "20261007_1800_drop_messaging_provider_admission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "messaging_test_phones",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("phone_e164", app.db.types.EncryptedString(), nullable=False),
        sa.Column("phone_hash", sa.String(length=64), nullable=False),
        sa.Column("phone_last4", sa.String(length=4), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.Column("code_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("code_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "phone_hash", name="uq_messaging_test_phones_org_phone"
        ),
    )
    op.create_table(
        "messaging_test_sends",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("route_id", sa.UUID(), nullable=False),
        sa.Column("test_phone_id", sa.UUID(), nullable=True),
        sa.Column("template_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("provider_message_sid", sa.String(length=64), nullable=True),
        sa.Column("provider_status", sa.String(length=30), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("sent_by_user_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint(
            "kind IN ('verification_code', 'template_test')", name="ck_messaging_test_sends_kind"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["twilio_routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["test_phone_id"], ["messaging_test_phones.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["template_id"], ["message_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sent_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_messaging_test_sends_route_sid",
        "messaging_test_sends",
        ["route_id", "provider_message_sid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_messaging_test_sends_route_sid", table_name="messaging_test_sends")
    op.drop_table("messaging_test_sends")
    op.drop_table("messaging_test_phones")
