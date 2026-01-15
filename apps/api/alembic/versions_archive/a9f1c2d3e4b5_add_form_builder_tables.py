"""add_form_builder_tables

Revision ID: a9f1c2d3e4b5
Revises: f8b3c2d1e4a5
Create Date: 2025-02-15 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a9f1c2d3e4b5"
down_revision: Union[str, Sequence[str], None] = "f8b3c2d1e4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "forms",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "published_schema_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "max_file_size_bytes",
            sa.Integer(),
            server_default=sa.text("10485760"),
            nullable=False,
        ),
        sa.Column("max_file_count", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("allowed_mime_types", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_forms_org", "forms", ["organization_id"], unique=False)
    op.create_index("idx_forms_org_status", "forms", ["organization_id", "status"], unique=False)

    op.create_table(
        "form_field_mappings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("form_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_key", sa.String(length=100), nullable=False),
        sa.Column("case_field", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("form_id", "case_field", name="uq_form_case_field"),
        sa.UniqueConstraint("form_id", "field_key", name="uq_form_field_key"),
    )
    op.create_index("idx_form_mappings_form", "form_field_mappings", ["form_id"], unique=False)

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
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("max_submissions", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "used_submissions",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_form_submission_token"),
    )
    op.create_index("idx_form_tokens_case", "form_submission_tokens", ["case_id"], unique=False)
    op.create_index("idx_form_tokens_form", "form_submission_tokens", ["form_id"], unique=False)
    op.create_index(
        "idx_form_tokens_org",
        "form_submission_tokens",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "form_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("form_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending_review'"),
            nullable=False,
        ),
        sa.Column("answers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("schema_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["token_id"], ["form_submission_tokens.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("form_id", "case_id", name="uq_form_submission_case"),
    )
    op.create_index("idx_form_submissions_case", "form_submissions", ["case_id"], unique=False)
    op.create_index("idx_form_submissions_form", "form_submissions", ["form_id"], unique=False)
    op.create_index(
        "idx_form_submissions_org",
        "form_submissions",
        ["organization_id"],
        unique=False,
    )
    op.create_index("idx_form_submissions_status", "form_submissions", ["status"], unique=False)

    op.create_table(
        "form_submission_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "scan_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("quarantined", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["form_submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_form_files_org", "form_submission_files", ["organization_id"], unique=False
    )
    op.create_index(
        "idx_form_files_submission",
        "form_submission_files",
        ["submission_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_form_files_submission", table_name="form_submission_files")
    op.drop_index("idx_form_files_org", table_name="form_submission_files")
    op.drop_table("form_submission_files")

    op.drop_index("idx_form_submissions_status", table_name="form_submissions")
    op.drop_index("idx_form_submissions_org", table_name="form_submissions")
    op.drop_index("idx_form_submissions_form", table_name="form_submissions")
    op.drop_index("idx_form_submissions_case", table_name="form_submissions")
    op.drop_table("form_submissions")

    op.drop_index("idx_form_tokens_org", table_name="form_submission_tokens")
    op.drop_index("idx_form_tokens_form", table_name="form_submission_tokens")
    op.drop_index("idx_form_tokens_case", table_name="form_submission_tokens")
    op.drop_table("form_submission_tokens")

    op.drop_index("idx_form_mappings_form", table_name="form_field_mappings")
    op.drop_table("form_field_mappings")

    op.drop_index("idx_forms_org_status", table_name="forms")
    op.drop_index("idx_forms_org", table_name="forms")
    op.drop_table("forms")
