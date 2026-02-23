"""add dual-mode intake links, leads, and submission matching

Revision ID: 20260222_1800
Revises: 20260222_1705
Create Date: 2026-02-22 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260222_1800"
down_revision: str | Sequence[str] | None = "20260222_1705"
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


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_foreign_key(table_name: str, foreign_key_name: str) -> bool:
    if not _has_table(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(
        foreign_key.get("name") == foreign_key_name
        for foreign_key in inspector.get_foreign_keys(table_name)
    )


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    if not _has_table(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _create_foreign_key_if_missing(
    constraint_name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str | None = None,
) -> None:
    if not _has_foreign_key(source_table, constraint_name):
        op.create_foreign_key(
            constraint_name,
            source_table,
            referent_table,
            local_cols,
            remote_cols,
            ondelete=ondelete,
        )


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
    postgresql_where: sa.TextClause | None = None,
) -> None:
    if not _has_index(table_name, index_name):
        op.create_index(
            index_name,
            table_name,
            columns,
            unique=unique,
            postgresql_where=postgresql_where,
        )


def _drop_unique_constraint_if_exists(table_name: str, constraint_name: str) -> None:
    if _has_unique_constraint(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_="unique")


def upgrade() -> None:
    _add_column_if_missing(
        "forms",
        sa.Column(
            "default_application_email_template_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    _create_foreign_key_if_missing(
        "fk_forms_default_application_email_template",
        "forms",
        "email_templates",
        ["default_application_email_template_id"],
        ["id"],
        ondelete="SET NULL",
    )

    _add_column_if_missing(
        "form_submission_tokens",
        sa.Column("locked_recipient_email", sa.String(length=255), nullable=True),
    )
    _add_column_if_missing(
        "form_submission_tokens",
        sa.Column("locked_recipient_phone", sa.String(length=50), nullable=True),
    )
    _add_column_if_missing(
        "form_submission_tokens",
        sa.Column("last_sent_at", sa.TIMESTAMP(), nullable=True),
    )
    _add_column_if_missing(
        "form_submission_tokens",
        sa.Column("last_sent_template_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    _create_foreign_key_if_missing(
        "fk_form_submission_tokens_last_sent_template",
        "form_submission_tokens",
        "email_templates",
        ["last_sent_template_id"],
        ["id"],
        ondelete="SET NULL",
    )

    if not _has_table("form_intake_links"):
        op.create_table(
            "form_intake_links",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("form_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("slug", sa.String(length=120), nullable=False),
            sa.Column("campaign_name", sa.String(length=255), nullable=True),
            sa.Column("event_name", sa.String(length=255), nullable=True),
            sa.Column("utm_defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
            sa.Column("expires_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("max_submissions", sa.Integer(), nullable=True),
            sa.Column(
                "submissions_count", sa.Integer(), server_default=sa.text("0"), nullable=False
            ),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug", name="uq_form_intake_link_slug"),
        )
    _create_index_if_missing("idx_form_intake_links_org", "form_intake_links", ["organization_id"])
    _create_index_if_missing("idx_form_intake_links_form", "form_intake_links", ["form_id"])
    _create_index_if_missing("idx_form_intake_links_slug", "form_intake_links", ["slug"])
    _create_index_if_missing(
        "idx_form_intake_links_active",
        "form_intake_links",
        ["organization_id", "is_active"],
    )

    if not _has_table("intake_leads"):
        op.create_table(
            "intake_leads",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("form_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("intake_link_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("full_name_normalized", sa.String(length=255), nullable=True),
            sa.Column("email", sa.Text(), nullable=True),
            sa.Column("email_hash", sa.String(length=64), nullable=True),
            sa.Column("phone", sa.Text(), nullable=True),
            sa.Column("phone_hash", sa.String(length=64), nullable=True),
            sa.Column("date_of_birth", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default=sa.text("'pending_review'"),
            ),
            sa.Column("promoted_surrogate_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("promoted_at", sa.TIMESTAMP(), nullable=True),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["intake_link_id"], ["form_intake_links.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["promoted_surrogate_id"], ["surrogates.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("idx_intake_leads_org", "intake_leads", ["organization_id"])
    _create_index_if_missing("idx_intake_leads_form", "intake_leads", ["form_id"])
    _create_index_if_missing(
        "idx_intake_leads_status", "intake_leads", ["organization_id", "status"]
    )
    _create_index_if_missing(
        "idx_intake_leads_email_hash", "intake_leads", ["organization_id", "email_hash"]
    )
    _create_index_if_missing(
        "idx_intake_leads_phone_hash", "intake_leads", ["organization_id", "phone_hash"]
    )

    _add_column_if_missing(
        "form_submissions",
        sa.Column("intake_link_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    _add_column_if_missing(
        "form_submissions",
        sa.Column("intake_lead_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    _add_column_if_missing(
        "form_submissions",
        sa.Column(
            "source_mode",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'dedicated'"),
        ),
    )
    _add_column_if_missing(
        "form_submissions",
        sa.Column(
            "match_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'linked'"),
        ),
    )
    _add_column_if_missing(
        "form_submissions",
        sa.Column("match_reason", sa.String(length=255), nullable=True),
    )
    _add_column_if_missing(
        "form_submissions",
        sa.Column("matched_at", sa.TIMESTAMP(), nullable=True),
    )
    _create_foreign_key_if_missing(
        "fk_form_submissions_intake_link",
        "form_submissions",
        "form_intake_links",
        ["intake_link_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_foreign_key_if_missing(
        "fk_form_submissions_intake_lead",
        "form_submissions",
        "intake_leads",
        ["intake_lead_id"],
        ["id"],
        ondelete="SET NULL",
    )
    if _has_column("form_submissions", "surrogate_id"):
        op.alter_column(
            "form_submissions",
            "surrogate_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=True,
        )
    if _has_column("form_submissions", "source_mode"):
        op.execute(
            "UPDATE form_submissions SET source_mode = 'dedicated' WHERE source_mode IS NULL"
        )
    if _has_column("form_submissions", "match_status"):
        op.execute("UPDATE form_submissions SET match_status = 'linked' WHERE match_status IS NULL")
    _drop_unique_constraint_if_exists("form_submissions", "uq_form_submission_surrogate")
    _create_index_if_missing(
        "uq_form_submission_surrogate_non_null",
        "form_submissions",
        ["form_id", "surrogate_id"],
        unique=True,
        postgresql_where=sa.text("surrogate_id IS NOT NULL"),
    )
    _create_index_if_missing(
        "idx_form_submissions_match_status", "form_submissions", ["match_status"]
    )

    if not _has_table("form_submission_match_candidates"):
        op.create_table(
            "form_submission_match_candidates",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("surrogate_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("reason", sa.String(length=120), nullable=False),
            sa.Column(
                "created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["submission_id"], ["form_submissions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["surrogate_id"], ["surrogates.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "submission_id",
                "surrogate_id",
                name="uq_form_submission_match_candidate_pair",
            ),
        )
    _create_index_if_missing(
        "idx_form_submission_match_candidates_org",
        "form_submission_match_candidates",
        ["organization_id"],
    )
    _create_index_if_missing(
        "idx_form_submission_match_candidates_submission",
        "form_submission_match_candidates",
        ["submission_id"],
    )

    if not _has_table("form_intake_drafts"):
        op.create_table(
            "form_intake_drafts",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("intake_link_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("form_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("draft_session_id", sa.String(length=120), nullable=False),
            sa.Column(
                "answers_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
            sa.Column(
                "created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["intake_link_id"], ["form_intake_links.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "intake_link_id",
                "draft_session_id",
                name="uq_form_intake_draft_session",
            ),
        )
    _create_index_if_missing(
        "idx_form_intake_drafts_org", "form_intake_drafts", ["organization_id"]
    )
    _create_index_if_missing(
        "idx_form_intake_drafts_link", "form_intake_drafts", ["intake_link_id"]
    )
    _create_index_if_missing("idx_form_intake_drafts_form", "form_intake_drafts", ["form_id"])


def downgrade() -> None:
    op.drop_index("idx_form_intake_drafts_form", table_name="form_intake_drafts")
    op.drop_index("idx_form_intake_drafts_link", table_name="form_intake_drafts")
    op.drop_index("idx_form_intake_drafts_org", table_name="form_intake_drafts")
    op.drop_table("form_intake_drafts")

    op.drop_index(
        "idx_form_submission_match_candidates_submission",
        table_name="form_submission_match_candidates",
    )
    op.drop_index(
        "idx_form_submission_match_candidates_org",
        table_name="form_submission_match_candidates",
    )
    op.drop_table("form_submission_match_candidates")

    op.drop_index("idx_form_submissions_match_status", table_name="form_submissions")
    op.drop_index("uq_form_submission_surrogate_non_null", table_name="form_submissions")
    op.create_unique_constraint(
        "uq_form_submission_surrogate",
        "form_submissions",
        ["form_id", "surrogate_id"],
    )
    op.drop_constraint("fk_form_submissions_intake_lead", "form_submissions", type_="foreignkey")
    op.drop_constraint("fk_form_submissions_intake_link", "form_submissions", type_="foreignkey")
    op.drop_column("form_submissions", "matched_at")
    op.drop_column("form_submissions", "match_reason")
    op.drop_column("form_submissions", "match_status")
    op.drop_column("form_submissions", "source_mode")
    op.drop_column("form_submissions", "intake_lead_id")
    op.drop_column("form_submissions", "intake_link_id")
    op.alter_column(
        "form_submissions",
        "surrogate_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    op.drop_index("idx_intake_leads_phone_hash", table_name="intake_leads")
    op.drop_index("idx_intake_leads_email_hash", table_name="intake_leads")
    op.drop_index("idx_intake_leads_status", table_name="intake_leads")
    op.drop_index("idx_intake_leads_form", table_name="intake_leads")
    op.drop_index("idx_intake_leads_org", table_name="intake_leads")
    op.drop_table("intake_leads")

    op.drop_index("idx_form_intake_links_active", table_name="form_intake_links")
    op.drop_index("idx_form_intake_links_slug", table_name="form_intake_links")
    op.drop_index("idx_form_intake_links_form", table_name="form_intake_links")
    op.drop_index("idx_form_intake_links_org", table_name="form_intake_links")
    op.drop_table("form_intake_links")

    op.drop_constraint(
        "fk_form_submission_tokens_last_sent_template",
        "form_submission_tokens",
        type_="foreignkey",
    )
    op.drop_column("form_submission_tokens", "last_sent_template_id")
    op.drop_column("form_submission_tokens", "last_sent_at")
    op.drop_column("form_submission_tokens", "locked_recipient_phone")
    op.drop_column("form_submission_tokens", "locked_recipient_email")

    op.drop_constraint(
        "fk_forms_default_application_email_template",
        "forms",
        type_="foreignkey",
    )
    op.drop_column("forms", "default_application_email_template_id")
