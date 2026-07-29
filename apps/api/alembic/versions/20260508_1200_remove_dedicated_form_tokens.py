"""remove dedicated form submission tokens

Revision ID: 20260508_1200
Revises: 20260506_2035
Create Date: 2026-05-08 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260508_1200"
down_revision: str | Sequence[str] | None = "20260506_2035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _drop_foreign_keys_for_column(table_name: str, column_name: str) -> None:
    if not _has_table(table_name):
        return
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get("constrained_columns") == [column_name] and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], table_name, type_="foreignkey")


def upgrade() -> None:
    if _has_column("form_submissions", "token_id"):
        _drop_foreign_keys_for_column("form_submissions", "token_id")
        op.drop_column("form_submissions", "token_id")

    if _has_column("form_submissions", "source_mode"):
        op.execute(
            "UPDATE form_submissions SET source_mode = 'shared' WHERE source_mode = 'dedicated'"
        )
        op.alter_column(
            "form_submissions",
            "source_mode",
            server_default=sa.text("'shared'"),
            existing_type=sa.String(length=20),
            existing_nullable=False,
        )

    if _has_table("form_submission_tokens"):
        op.drop_table("form_submission_tokens")


def downgrade() -> None:
    if not _has_table("form_submission_tokens"):
        op.create_table(
            "form_submission_tokens",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("form_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("surrogate_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("token", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
            sa.Column("max_submissions", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.Column(
                "used_submissions", sa.Integer(), server_default=sa.text("0"), nullable=False
            ),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("revoked_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("locked_recipient_email", sa.String(length=255), nullable=True),
            sa.Column("locked_recipient_phone", sa.String(length=50), nullable=True),
            sa.Column("last_sent_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("last_sent_template_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["surrogate_id"], ["surrogates.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["last_sent_template_id"], ["email_templates.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token", name="uq_form_submission_token"),
        )
        op.create_index("idx_form_tokens_org", "form_submission_tokens", ["organization_id"])
        op.create_index("idx_form_tokens_form", "form_submission_tokens", ["form_id"])
        op.create_index("idx_form_tokens_surrogate", "form_submission_tokens", ["surrogate_id"])

    if not _has_column("form_submissions", "token_id"):
        op.add_column(
            "form_submissions",
            sa.Column("token_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_form_submissions_token",
            "form_submissions",
            "form_submission_tokens",
            ["token_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if _has_column("form_submissions", "source_mode"):
        op.alter_column(
            "form_submissions",
            "source_mode",
            server_default=sa.text("'dedicated'"),
            existing_type=sa.String(length=20),
            existing_nullable=False,
        )
