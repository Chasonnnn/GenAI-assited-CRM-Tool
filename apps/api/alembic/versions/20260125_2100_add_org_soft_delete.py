"""add_org_soft_delete

Revision ID: 20260125_2100
Revises: 20260125_2000
Create Date: 2026-01-25 21:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260125_2100"
down_revision: Union[str, Sequence[str], None] = "20260125_2000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fk_for_column(table: str, column: str) -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT DISTINCT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_attribute att ON att.attrelid = rel.oid
            WHERE con.contype = 'f'
              AND rel.relname = :table
              AND att.attname = :column
              AND att.attnum = ANY (con.conkey)
            """
        ),
        {"table": table, "column": column},
    )
    for row in result:
        op.drop_constraint(row.conname, table, type_="foreignkey")


def upgrade() -> None:
    """Add org soft-delete fields and cascade org FKs for interviews."""
    op.add_column(
        "organizations",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("purge_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("deleted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "organizations_deleted_by_user_id_fkey",
        "organizations",
        "users",
        ["deleted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_organizations_deleted_at", "organizations", ["deleted_at"])
    op.create_index("ix_organizations_purge_at", "organizations", ["purge_at"])

    _drop_fk_for_column("surrogate_interviews", "organization_id")
    op.create_foreign_key(
        "surrogate_interviews_organization_id_fkey",
        "surrogate_interviews",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    _drop_fk_for_column("interview_transcript_versions", "organization_id")
    op.create_foreign_key(
        "interview_transcript_versions_organization_id_fkey",
        "interview_transcript_versions",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    _drop_fk_for_column("interview_notes", "organization_id")
    op.create_foreign_key(
        "interview_notes_organization_id_fkey",
        "interview_notes",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    _drop_fk_for_column("interview_attachments", "organization_id")
    op.create_foreign_key(
        "interview_attachments_organization_id_fkey",
        "interview_attachments",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Remove org soft-delete fields and revert interview org FKs."""
    op.drop_constraint(
        "interview_attachments_organization_id_fkey",
        "interview_attachments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "interview_attachments_organization_id_fkey",
        "interview_attachments",
        "organizations",
        ["organization_id"],
        ["id"],
    )

    op.drop_constraint(
        "interview_notes_organization_id_fkey",
        "interview_notes",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "interview_notes_organization_id_fkey",
        "interview_notes",
        "organizations",
        ["organization_id"],
        ["id"],
    )

    op.drop_constraint(
        "interview_transcript_versions_organization_id_fkey",
        "interview_transcript_versions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "interview_transcript_versions_organization_id_fkey",
        "interview_transcript_versions",
        "organizations",
        ["organization_id"],
        ["id"],
    )

    op.drop_constraint(
        "surrogate_interviews_organization_id_fkey",
        "surrogate_interviews",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "surrogate_interviews_organization_id_fkey",
        "surrogate_interviews",
        "organizations",
        ["organization_id"],
        ["id"],
    )

    op.drop_index("ix_organizations_purge_at", table_name="organizations")
    op.drop_index("ix_organizations_deleted_at", table_name="organizations")
    op.drop_constraint(
        "organizations_deleted_by_user_id_fkey",
        "organizations",
        type_="foreignkey",
    )
    op.drop_column("organizations", "deleted_by_user_id")
    op.drop_column("organizations", "purge_at")
    op.drop_column("organizations", "deleted_at")
