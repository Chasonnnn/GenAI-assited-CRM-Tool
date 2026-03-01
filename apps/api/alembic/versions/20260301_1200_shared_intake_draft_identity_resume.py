"""add shared intake draft identity lookup columns

Revision ID: 20260301_1200
Revises: 20260227_1200
Create Date: 2026-03-01 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260301_1200"
down_revision: str | Sequence[str] | None = "20260227_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    if not _column_exists("form_intake_drafts", "full_name_normalized"):
        op.add_column(
            "form_intake_drafts",
            sa.Column("full_name_normalized", sa.String(length=255), nullable=True),
        )
    if not _column_exists("form_intake_drafts", "date_of_birth"):
        op.add_column(
            "form_intake_drafts",
            sa.Column("date_of_birth", sa.Date(), nullable=True),
        )
    if not _column_exists("form_intake_drafts", "email_hash"):
        op.add_column(
            "form_intake_drafts",
            sa.Column("email_hash", sa.String(length=64), nullable=True),
        )
    if not _column_exists("form_intake_drafts", "phone_hash"):
        op.add_column(
            "form_intake_drafts",
            sa.Column("phone_hash", sa.String(length=64), nullable=True),
        )

    if not _index_exists("form_intake_drafts", "idx_form_intake_drafts_org_form_updated"):
        op.create_index(
            "idx_form_intake_drafts_org_form_updated",
            "form_intake_drafts",
            ["organization_id", "form_id", "updated_at"],
            unique=False,
        )
    if not _index_exists("form_intake_drafts", "idx_form_intake_drafts_identity_email"):
        op.create_index(
            "idx_form_intake_drafts_identity_email",
            "form_intake_drafts",
            [
                "organization_id",
                "form_id",
                "full_name_normalized",
                "date_of_birth",
                "email_hash",
                "updated_at",
            ],
            unique=False,
        )
    if not _index_exists("form_intake_drafts", "idx_form_intake_drafts_identity_phone"):
        op.create_index(
            "idx_form_intake_drafts_identity_phone",
            "form_intake_drafts",
            [
                "organization_id",
                "form_id",
                "full_name_normalized",
                "date_of_birth",
                "phone_hash",
                "updated_at",
            ],
            unique=False,
        )


def downgrade() -> None:
    if _index_exists("form_intake_drafts", "idx_form_intake_drafts_identity_phone"):
        op.drop_index("idx_form_intake_drafts_identity_phone", table_name="form_intake_drafts")
    if _index_exists("form_intake_drafts", "idx_form_intake_drafts_identity_email"):
        op.drop_index("idx_form_intake_drafts_identity_email", table_name="form_intake_drafts")
    if _index_exists("form_intake_drafts", "idx_form_intake_drafts_org_form_updated"):
        op.drop_index("idx_form_intake_drafts_org_form_updated", table_name="form_intake_drafts")

    if _column_exists("form_intake_drafts", "phone_hash"):
        op.drop_column("form_intake_drafts", "phone_hash")
    if _column_exists("form_intake_drafts", "email_hash"):
        op.drop_column("form_intake_drafts", "email_hash")
    if _column_exists("form_intake_drafts", "date_of_birth"):
        op.drop_column("form_intake_drafts", "date_of_birth")
    if _column_exists("form_intake_drafts", "full_name_normalized"):
        op.drop_column("form_intake_drafts", "full_name_normalized")
