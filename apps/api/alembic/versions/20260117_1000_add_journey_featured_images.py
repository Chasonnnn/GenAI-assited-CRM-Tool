"""Add journey_featured_images table for milestone image selection.

Revision ID: 20260117_1000
Revises: 20260117_0935
Create Date: 2026-01-17 10:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260117_1000"
down_revision = "20260117_0935"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journey_featured_images",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("surrogate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("milestone_slug", sa.String(100), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["surrogate_id"],
            ["surrogates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "surrogate_id",
            "milestone_slug",
            name="uq_journey_featured_image",
        ),
    )
    op.create_index(
        "ix_journey_featured_images_surrogate",
        "journey_featured_images",
        ["surrogate_id"],
    )
    op.create_index(
        "ix_journey_featured_images_org",
        "journey_featured_images",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_journey_featured_images_org", table_name="journey_featured_images")
    op.drop_index("ix_journey_featured_images_surrogate", table_name="journey_featured_images")
    op.drop_table("journey_featured_images")
