"""add public intake embed contracts

Revision ID: 20260508_1330
Revises: 20260508_1200
Create Date: 2026-05-08 13:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260508_1330"
down_revision: str | Sequence[str] | None = "20260508_1200"
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


def upgrade() -> None:
    if not _has_table("published_intake_versions"):
        op.create_table(
            "published_intake_versions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("intake_link_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("form_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("form_version_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "form_schema_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
            ),
            sa.Column(
                "field_policy_snapshot_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
            ),
            sa.Column(
                "mapping_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
            ),
            sa.Column("consent_text_snapshot", sa.Text(), nullable=True),
            sa.Column("consent_text_hash", sa.String(length=64), nullable=True),
            sa.Column(
                "thank_you_config_snapshot_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
            ),
            sa.Column("tracking_mode_snapshot", sa.String(length=30), nullable=False),
            sa.Column("tracking_policy_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "embed_theme_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
            ),
            sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "published_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["intake_link_id"], ["form_intake_links.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_published_intake_versions_org", "published_intake_versions", ["organization_id"]
        )
        op.create_index(
            "idx_published_intake_versions_link", "published_intake_versions", ["intake_link_id"]
        )
        op.create_index(
            "idx_published_intake_versions_form", "published_intake_versions", ["form_id"]
        )

    if _has_table("form_intake_links"):
        if not _has_column("form_intake_links", "embed_enabled"):
            op.add_column(
                "form_intake_links",
                sa.Column(
                    "embed_enabled", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False
                ),
            )
        if not _has_column("form_intake_links", "allowed_embed_origins"):
            op.add_column(
                "form_intake_links",
                sa.Column(
                    "allowed_embed_origins",
                    postgresql.JSONB(astext_type=sa.Text()),
                    server_default=sa.text("'[]'::jsonb"),
                    nullable=False,
                ),
            )
        if not _has_column("form_intake_links", "tracking_mode"):
            op.add_column(
                "form_intake_links",
                sa.Column(
                    "tracking_mode",
                    sa.String(length=30),
                    server_default=sa.text("'internal_only'"),
                    nullable=False,
                ),
            )
        if not _has_column("form_intake_links", "consent_text"):
            op.add_column("form_intake_links", sa.Column("consent_text", sa.Text(), nullable=True))
        if not _has_column("form_intake_links", "privacy_policy_url"):
            op.add_column(
                "form_intake_links",
                sa.Column("privacy_policy_url", sa.String(length=1000), nullable=True),
            )
        if not _has_column("form_intake_links", "thank_you_config"):
            op.add_column(
                "form_intake_links",
                sa.Column(
                    "thank_you_config",
                    postgresql.JSONB(astext_type=sa.Text()),
                    server_default=sa.text("'{}'::jsonb"),
                    nullable=False,
                ),
            )
        if not _has_column("form_intake_links", "embed_theme_json"):
            op.add_column(
                "form_intake_links",
                sa.Column(
                    "embed_theme_json",
                    postgresql.JSONB(astext_type=sa.Text()),
                    server_default=sa.text("'{}'::jsonb"),
                    nullable=False,
                ),
            )
        if not _has_column("form_intake_links", "published_version_id"):
            op.add_column(
                "form_intake_links",
                sa.Column("published_version_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
            op.create_foreign_key(
                "fk_form_intake_links_published_version",
                "form_intake_links",
                "published_intake_versions",
                ["published_version_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if _has_table("form_submissions"):
        for name in (
            "published_version_id",
            "idempotency_key",
            "form_schema_hash",
            "consent_text_hash",
            "tracking_policy_hash",
        ):
            if _has_column("form_submissions", name):
                continue
            if name == "published_version_id":
                op.add_column(
                    "form_submissions",
                    sa.Column(name, postgresql.UUID(as_uuid=True), nullable=True),
                )
                op.create_foreign_key(
                    "fk_form_submissions_published_version",
                    "form_submissions",
                    "published_intake_versions",
                    [name],
                    ["id"],
                    ondelete="SET NULL",
                )
            elif name == "idempotency_key":
                op.add_column(
                    "form_submissions", sa.Column(name, sa.String(length=128), nullable=True)
                )
            else:
                op.add_column(
                    "form_submissions", sa.Column(name, sa.String(length=64), nullable=True)
                )
        op.create_index(
            "uq_form_submission_intake_idempotency",
            "form_submissions",
            ["organization_id", "intake_link_id", "idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        )

    if _has_table("intake_leads"):
        if not _has_column("intake_leads", "form_submission_id"):
            op.add_column(
                "intake_leads",
                sa.Column("form_submission_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
            op.create_foreign_key(
                "fk_intake_leads_form_submission",
                "intake_leads",
                "form_submissions",
                ["form_submission_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if not _has_column("intake_leads", "source"):
            op.add_column(
                "intake_leads",
                sa.Column(
                    "source",
                    sa.String(length=30),
                    server_default=sa.text("'shared_intake'"),
                    nullable=False,
                ),
            )
        if not _has_column("intake_leads", "lead_type"):
            op.add_column(
                "intake_leads",
                sa.Column(
                    "lead_type",
                    sa.String(length=40),
                    server_default=sa.text("'surrogate'"),
                    nullable=False,
                ),
            )

    if not _has_table("lead_attribution"):
        op.create_table(
            "lead_attribution",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("form_submission_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("intake_link_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("source_surface", sa.String(length=30), nullable=False),
            sa.Column("source", sa.String(length=255), nullable=True),
            sa.Column("medium", sa.String(length=255), nullable=True),
            sa.Column("campaign", sa.String(length=255), nullable=True),
            sa.Column("ad_id", sa.String(length=255), nullable=True),
            sa.Column("adset_id", sa.String(length=255), nullable=True),
            sa.Column("campaign_id", sa.String(length=255), nullable=True),
            sa.Column("fbclid", sa.String(length=500), nullable=True),
            sa.Column("fbc", sa.String(length=500), nullable=True),
            sa.Column("fbp", sa.String(length=500), nullable=True),
            sa.Column("referrer", sa.String(length=1000), nullable=True),
            sa.Column("parent_origin", sa.String(length=500), nullable=True),
            sa.Column("landing_url", sa.String(length=1000), nullable=True),
            sa.Column("first_touch_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("last_touch_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["form_submission_id"], ["form_submissions.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["intake_link_id"], ["form_intake_links.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_lead_attribution_org", "lead_attribution", ["organization_id"])
        op.create_index(
            "idx_lead_attribution_submission", "lead_attribution", ["form_submission_id"]
        )
        op.create_index("idx_lead_attribution_link", "lead_attribution", ["intake_link_id"])

    if not _has_table("consent_records"):
        op.create_table(
            "consent_records",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("intake_link_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("form_submission_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("consent_type", sa.String(length=40), nullable=False),
            sa.Column("consent_text_snapshot", sa.Text(), nullable=True),
            sa.Column("consent_text_hash", sa.String(length=64), nullable=True),
            sa.Column("accepted", sa.Boolean(), nullable=False),
            sa.Column(
                "accepted_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.Column("ip_hash", sa.String(length=64), nullable=True),
            sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
            sa.Column("parent_origin", sa.String(length=500), nullable=True),
            sa.Column("privacy_policy_url_snapshot", sa.String(length=1000), nullable=True),
            sa.ForeignKeyConstraint(
                ["form_submission_id"], ["form_submissions.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["intake_link_id"], ["form_intake_links.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_consent_records_org", "consent_records", ["organization_id"])
        op.create_index("idx_consent_records_submission", "consent_records", ["form_submission_id"])
        op.create_index("idx_consent_records_link", "consent_records", ["intake_link_id"])

    if not _has_table("embed_sessions"):
        op.create_table(
            "embed_sessions",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("intake_link_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("public_session_token_hash", sa.String(length=64), nullable=False),
            sa.Column("parent_origin", sa.String(length=500), nullable=False),
            sa.Column(
                "attribution_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column("ip_hash", sa.String(length=64), nullable=True),
            sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
            sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
            sa.Column("consumed_at", sa.TIMESTAMP(), nullable=True),
            sa.Column(
                "created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["intake_link_id"], ["form_intake_links.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("public_session_token_hash", name="uq_embed_session_token_hash"),
        )
        op.create_index("idx_embed_sessions_org", "embed_sessions", ["organization_id"])
        op.create_index("idx_embed_sessions_link", "embed_sessions", ["intake_link_id"])

    if not _has_table("tracking_event_logs"):
        op.create_table(
            "tracking_event_logs",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("intake_link_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("form_submission_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("event_name", sa.String(length=80), nullable=False),
            sa.Column("destination", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False
            ),
            sa.ForeignKeyConstraint(
                ["form_submission_id"], ["form_submissions.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["intake_link_id"], ["form_intake_links.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_tracking_event_logs_org", "tracking_event_logs", ["organization_id"])
        op.create_index(
            "idx_tracking_event_logs_submission", "tracking_event_logs", ["form_submission_id"]
        )
        op.create_index(
            "idx_tracking_event_logs_destination",
            "tracking_event_logs",
            ["organization_id", "destination", "status"],
        )


def downgrade() -> None:
    if _has_table("tracking_event_logs"):
        op.drop_table("tracking_event_logs")
    if _has_table("embed_sessions"):
        op.drop_table("embed_sessions")
    if _has_table("consent_records"):
        op.drop_table("consent_records")
    if _has_table("lead_attribution"):
        op.drop_table("lead_attribution")

    if _has_column("intake_leads", "lead_type"):
        op.drop_column("intake_leads", "lead_type")
    if _has_column("intake_leads", "source"):
        op.drop_column("intake_leads", "source")
    if _has_column("intake_leads", "form_submission_id"):
        op.drop_constraint("fk_intake_leads_form_submission", "intake_leads", type_="foreignkey")
        op.drop_column("intake_leads", "form_submission_id")

    if _has_column("form_submissions", "idempotency_key"):
        op.drop_index("uq_form_submission_intake_idempotency", table_name="form_submissions")
    for name in (
        "tracking_policy_hash",
        "consent_text_hash",
        "form_schema_hash",
        "idempotency_key",
    ):
        if _has_column("form_submissions", name):
            op.drop_column("form_submissions", name)
    if _has_column("form_submissions", "published_version_id"):
        op.drop_constraint(
            "fk_form_submissions_published_version", "form_submissions", type_="foreignkey"
        )
        op.drop_column("form_submissions", "published_version_id")

    if _has_column("form_intake_links", "published_version_id"):
        op.drop_constraint(
            "fk_form_intake_links_published_version", "form_intake_links", type_="foreignkey"
        )
        op.drop_column("form_intake_links", "published_version_id")
    for name in (
        "embed_theme_json",
        "thank_you_config",
        "privacy_policy_url",
        "consent_text",
        "tracking_mode",
        "allowed_embed_origins",
        "embed_enabled",
    ):
        if _has_column("form_intake_links", name):
            op.drop_column("form_intake_links", name)

    if _has_table("published_intake_versions"):
        op.drop_table("published_intake_versions")
