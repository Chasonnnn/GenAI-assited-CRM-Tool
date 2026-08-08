"""Add organization Twilio settings and purpose-bound routes.

Revision ID: 20260731_2200
Revises: 20260725_0290
Create Date: 2026-07-31 22:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260731_2200"
down_revision = "20260725_0290"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "twilio_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("account_sid_encrypted", sa.Text(), nullable=True),
        sa.Column("api_key_sid_encrypted", sa.Text(), nullable=True),
        sa.Column("api_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("auth_token_encrypted", sa.Text(), nullable=True),
        sa.Column("legal_messaging_brand", sa.String(length=160), nullable=True),
        sa.Column("operational_disclosure", sa.Text(), nullable=True),
        sa.Column("promotional_disclosure", sa.Text(), nullable=True),
        sa.Column("sms_terms_url", sa.String(length=1000), nullable=True),
        sa.Column("privacy_policy_url", sa.String(length=1000), nullable=True),
        sa.Column("support_contact", sa.String(length=255), nullable=True),
        sa.Column("expected_frequency", sa.String(length=255), nullable=True),
        sa.Column("counsel_approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("compliance_toolkit_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("twilio_edition", sa.String(length=40), nullable=True),
        sa.Column("baa_verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("compliance_approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("phi_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("current_version >= 1", name="ck_twilio_settings_version"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_table(
        "twilio_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("settings_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("messaging_service_sid_encrypted", sa.Text(), nullable=True),
        sa.Column("sender_phone_encrypted", sa.Text(), nullable=True),
        sa.Column("sender_phone_hash", sa.String(length=64), nullable=True),
        sa.Column("sender_phone_last4", sa.String(length=4), nullable=True),
        sa.Column("a2p_status", sa.String(length=20), server_default=sa.text("'unconfigured'"), nullable=False),
        sa.Column("advanced_opt_out_status", sa.String(length=20), server_default=sa.text("'unconfigured'"), nullable=False),
        sa.Column("consent_management_status", sa.String(length=20), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("capability_evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("webhook_id", sa.String(length=36), server_default=sa.text("gen_random_uuid()::text"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("purpose IN ('operational', 'promotional')", name="ck_twilio_routes_purpose"),
        sa.CheckConstraint("a2p_status IN ('unconfigured', 'pending', 'approved', 'rejected')", name="ck_twilio_routes_a2p_status"),
        sa.CheckConstraint("advanced_opt_out_status IN ('unconfigured', 'enabled', 'verified')", name="ck_twilio_routes_advanced_opt_out_status"),
        sa.CheckConstraint("consent_management_status IN ('unknown', 'available', 'unavailable')", name="ck_twilio_routes_consent_management_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["settings_id"], ["twilio_settings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "purpose", name="uq_twilio_routes_org_purpose"),
    )
    op.create_index("idx_twilio_routes_org", "twilio_routes", ["organization_id"])
    op.create_index("idx_twilio_routes_sender_hash", "twilio_routes", ["organization_id", "sender_phone_hash"])
    op.create_index("idx_twilio_routes_webhook_id", "twilio_routes", ["webhook_id"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_twilio_routes_webhook_id", table_name="twilio_routes")
    op.drop_index("idx_twilio_routes_sender_hash", table_name="twilio_routes")
    op.drop_index("idx_twilio_routes_org", table_name="twilio_routes")
    op.drop_table("twilio_routes")
    op.drop_table("twilio_settings")
