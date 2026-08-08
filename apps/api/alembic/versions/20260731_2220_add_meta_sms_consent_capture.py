"""Add immutable Meta legal snapshots and lead disclaimer responses.

Revision ID: 20260731_2220
Revises: 20260731_2210
Create Date: 2026-07-31 22:20:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260731_2220"
down_revision = "20260731_2210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_form_legal_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("form_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "legal_content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("privacy_policy_url", sa.String(length=1000), nullable=True),
        sa.Column("legal_content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "detected_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["form_id"], ["meta_forms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("form_id", "legal_content_hash", name="uq_meta_form_legal_snapshot"),
    )
    op.create_index(
        "idx_meta_form_legal_snapshot_org",
        "meta_form_legal_snapshots",
        ["organization_id"],
    )
    op.create_index(
        "idx_meta_form_legal_snapshot_form",
        "meta_form_legal_snapshots",
        ["form_id", "detected_at"],
    )

    op.add_column(
        "meta_leads",
        sa.Column(
            "custom_disclaimer_responses",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "meta_leads",
        sa.Column(
            "meta_form_legal_snapshot_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_meta_leads_legal_snapshot",
        "meta_leads",
        "meta_form_legal_snapshots",
        ["meta_form_legal_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_meta_leads_legal_snapshot",
        "meta_leads",
        ["meta_form_legal_snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_meta_leads_legal_snapshot", table_name="meta_leads")
    op.drop_constraint("fk_meta_leads_legal_snapshot", "meta_leads", type_="foreignkey")
    op.drop_column("meta_leads", "meta_form_legal_snapshot_id")
    op.drop_column("meta_leads", "custom_disclaimer_responses")
    op.drop_index(
        "idx_meta_form_legal_snapshot_form",
        table_name="meta_form_legal_snapshots",
    )
    op.drop_index(
        "idx_meta_form_legal_snapshot_org",
        table_name="meta_form_legal_snapshots",
    )
    op.drop_table("meta_form_legal_snapshots")
