"""Add Meta lead mapping fields and remove legacy token columns.

Revision ID: 20260129_1900
Revises: 20260129_1300
Create Date: 2026-01-29 19:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260129_1900"
down_revision: Union[str, None] = "20260129_1300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Meta lead mapping fields
    op.add_column(
        "meta_forms",
        sa.Column("mapping_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "meta_forms",
        sa.Column("mapping_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "meta_forms",
        sa.Column(
            "mapping_status",
            sa.String(length=20),
            server_default="unmapped",
            nullable=False,
        ),
    )
    op.add_column(
        "meta_forms",
        sa.Column(
            "unknown_column_behavior",
            sa.String(length=20),
            server_default="metadata",
            nullable=False,
        ),
    )
    op.add_column(
        "meta_forms",
        sa.Column("mapping_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "meta_forms",
        sa.Column("mapping_updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_meta_forms_mapping_version",
        "meta_forms",
        "meta_form_versions",
        ["mapping_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_meta_forms_mapping_updated_by",
        "meta_forms",
        "users",
        ["mapping_updated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "meta_leads",
        sa.Column("unmapped_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Drop legacy token columns from meta_ad_accounts
    op.drop_column("meta_ad_accounts", "system_token_encrypted")
    op.drop_column("meta_ad_accounts", "token_expires_at")
    op.drop_column("meta_ad_accounts", "capi_token_encrypted")
    op.drop_column("meta_ad_accounts", "is_legacy")


def downgrade() -> None:
    # Restore legacy columns
    op.add_column(
        "meta_ad_accounts",
        sa.Column("is_legacy", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "meta_ad_accounts",
        sa.Column("capi_token_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "meta_ad_accounts",
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "meta_ad_accounts",
        sa.Column("system_token_encrypted", sa.Text(), nullable=True),
    )

    op.drop_column("meta_leads", "unmapped_fields")

    op.drop_constraint("fk_meta_forms_mapping_updated_by", "meta_forms", type_="foreignkey")
    op.drop_constraint("fk_meta_forms_mapping_version", "meta_forms", type_="foreignkey")
    op.drop_column("meta_forms", "mapping_updated_by_user_id")
    op.drop_column("meta_forms", "mapping_updated_at")
    op.drop_column("meta_forms", "unknown_column_behavior")
    op.drop_column("meta_forms", "mapping_status")
    op.drop_column("meta_forms", "mapping_version_id")
    op.drop_column("meta_forms", "mapping_rules")
