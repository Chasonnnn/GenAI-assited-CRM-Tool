"""Add zoom_meetings table.

Revision ID: 0032_add_zoom_meetings
Revises: 0031_add_email_log_external_id
Create Date: 2025-12-19

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0032_add_zoom_meetings"
down_revision = "0031_add_email_log_external_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zoom_meetings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "intended_parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intended_parents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("zoom_meeting_id", sa.String(50), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        sa.Column("join_url", sa.String(500), nullable=False),
        sa.Column("start_url", sa.Text(), nullable=False),
        sa.Column("password", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indexes
    op.create_index("ix_zoom_meetings_user_id", "zoom_meetings", ["user_id"])
    op.create_index("ix_zoom_meetings_case_id", "zoom_meetings", ["case_id"])
    op.create_index(
        "ix_zoom_meetings_org_created",
        "zoom_meetings",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_zoom_meetings_org_created")
    op.drop_index("ix_zoom_meetings_case_id")
    op.drop_index("ix_zoom_meetings_user_id")
    op.drop_table("zoom_meetings")
