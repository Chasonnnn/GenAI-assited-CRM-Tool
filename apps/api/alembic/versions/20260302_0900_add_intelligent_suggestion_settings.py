"""add intelligent suggestion settings

Revision ID: 20260302_0900
Revises: 20260225_1100
Create Date: 2026-03-02 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260302_0900"
down_revision: str | Sequence[str] | None = "20260225_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_table("org_intelligent_suggestion_settings"):
        op.create_table(
            "org_intelligent_suggestion_settings",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column(
                "new_unread_enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column(
                "new_unread_business_days",
                sa.Integer(),
                server_default=sa.text("1"),
                nullable=False,
            ),
            sa.Column(
                "meeting_outcome_enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column(
                "meeting_outcome_business_days",
                sa.Integer(),
                server_default=sa.text("1"),
                nullable=False,
            ),
            sa.Column(
                "stuck_enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column(
                "stuck_business_days",
                sa.Integer(),
                server_default=sa.text("5"),
                nullable=False,
            ),
            sa.Column(
                "daily_digest_enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column(
                "digest_hour_local",
                sa.Integer(),
                server_default=sa.text("9"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "new_unread_business_days BETWEEN 1 AND 30",
                name="ck_intel_new_unread_days",
            ),
            sa.CheckConstraint(
                "meeting_outcome_business_days BETWEEN 1 AND 30",
                name="ck_intel_meeting_outcome_days",
            ),
            sa.CheckConstraint(
                "stuck_business_days BETWEEN 1 AND 60",
                name="ck_intel_stuck_days",
            ),
            sa.CheckConstraint(
                "digest_hour_local BETWEEN 0 AND 23",
                name="ck_intel_digest_hour",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organizations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id"),
        )

    if not _has_column("user_notification_settings", "intelligent_suggestion_digest"):
        op.add_column(
            "user_notification_settings",
            sa.Column(
                "intelligent_suggestion_digest",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )

    if not _has_table("org_intelligent_suggestion_rules"):
        op.create_table(
            "org_intelligent_suggestion_rules",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("template_key", sa.String(length=100), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("rule_kind", sa.String(length=50), nullable=False),
            sa.Column("stage_slug", sa.String(length=100), nullable=True),
            sa.Column(
                "business_days",
                sa.Integer(),
                server_default=sa.text("1"),
                nullable=False,
            ),
            sa.Column(
                "enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column(
                "sort_order",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "business_days BETWEEN 1 AND 60",
                name="ck_intel_rule_business_days",
            ),
            sa.CheckConstraint(
                "rule_kind IN ('stage_inactivity', 'meeting_outcome_missing')",
                name="ck_intel_rule_kind",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organizations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_intel_rules_org_enabled",
            "org_intelligent_suggestion_rules",
            ["organization_id", "enabled"],
            unique=False,
        )


def downgrade() -> None:
    if _has_table("org_intelligent_suggestion_rules"):
        op.drop_index(
            "idx_intel_rules_org_enabled",
            table_name="org_intelligent_suggestion_rules",
        )
        op.drop_table("org_intelligent_suggestion_rules")

    if _has_column("user_notification_settings", "intelligent_suggestion_digest"):
        op.drop_column("user_notification_settings", "intelligent_suggestion_digest")

    if _has_table("org_intelligent_suggestion_settings"):
        op.drop_table("org_intelligent_suggestion_settings")
