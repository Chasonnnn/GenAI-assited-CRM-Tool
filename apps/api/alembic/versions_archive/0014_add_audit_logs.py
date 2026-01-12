"""Add audit_logs table

Revision ID: 0014_add_audit_logs
Revises: 0013_migrate_casenotes
Create Date: 2025-12-17

Enterprise audit trail for security and compliance.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0014_add_audit_logs"
down_revision: Union[str, Sequence[str], None] = "0013_migrate_casenotes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit_logs table with indexes."""
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
    )

    # Create indexes for efficient querying
    op.create_index(
        "idx_audit_org_created", "audit_logs", ["organization_id", "created_at"]
    )
    op.create_index(
        "idx_audit_org_event_created",
        "audit_logs",
        ["organization_id", "event_type", "created_at"],
    )
    op.create_index(
        "idx_audit_org_actor_created",
        "audit_logs",
        ["organization_id", "actor_user_id", "created_at"],
    )


def downgrade() -> None:
    """Drop audit_logs table."""
    op.drop_index("idx_audit_org_actor_created", "audit_logs")
    op.drop_index("idx_audit_org_event_created", "audit_logs")
    op.drop_index("idx_audit_org_created", "audit_logs")
    op.drop_table("audit_logs")
