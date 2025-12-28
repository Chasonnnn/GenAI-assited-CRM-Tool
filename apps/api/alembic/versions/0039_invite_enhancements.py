"""Add OrgInvite resend and revocation fields.

Revision ID: 0039_invite_enhancements
Revises: 0038_attachments
Create Date: 2025-12-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "0039_invite_enhancements"
down_revision = "0038_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add resend throttling columns
    op.add_column(
        "org_invites",
        sa.Column(
            "resend_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
    )
    op.add_column(
        "org_invites",
        sa.Column("last_resent_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Add revocation columns
    op.add_column(
        "org_invites",
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "org_invites",
        sa.Column("revoked_by_user_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_org_invites_revoked_by",
        "org_invites",
        "users",
        ["revoked_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Update unique index to exclude revoked invites
    op.drop_index("uq_pending_invite_email", table_name="org_invites")
    op.create_index(
        "uq_pending_invite_email",
        "org_invites",
        ["email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )


def downgrade() -> None:
    # Revert unique index
    op.drop_index("uq_pending_invite_email", table_name="org_invites")
    op.create_index(
        "uq_pending_invite_email",
        "org_invites",
        ["email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL"),
    )

    # Drop revocation columns
    op.drop_constraint("fk_org_invites_revoked_by", "org_invites", type_="foreignkey")
    op.drop_column("org_invites", "revoked_by_user_id")
    op.drop_column("org_invites", "revoked_at")

    # Drop resend columns
    op.drop_column("org_invites", "last_resent_at")
    op.drop_column("org_invites", "resend_count")
