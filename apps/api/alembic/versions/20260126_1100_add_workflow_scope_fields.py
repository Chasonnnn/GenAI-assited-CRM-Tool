"""Add workflow scope and owner_user_id fields.

Supports org-level and personal workflows:
- org workflows: scope='org', owner_user_id=NULL
- personal workflows: scope='personal', owner_user_id=<user_id>

Revision ID: 20260126_1100
Revises: 20260126_1030
Create Date: 2026-01-26

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260126_1100"
down_revision = "20260126_1030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add scope column with default 'org'
    op.add_column(
        "automation_workflows",
        sa.Column(
            "scope",
            sa.String(20),
            server_default=sa.text("'org'"),
            nullable=False,
        ),
    )

    # Add owner_user_id column (nullable, only for personal workflows)
    op.add_column(
        "automation_workflows",
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # Add CHECK constraint for scope/owner integrity
    op.create_check_constraint(
        "chk_workflow_scope_owner",
        "automation_workflows",
        "(scope = 'org' AND owner_user_id IS NULL) OR "
        "(scope = 'personal' AND owner_user_id IS NOT NULL)",
    )

    # Add optimized index for matching workflows at trigger time
    op.create_index(
        "idx_wf_matching",
        "automation_workflows",
        ["organization_id", "scope", "owner_user_id", "trigger_type", "is_enabled"],
    )


def downgrade() -> None:
    # Remove index
    op.drop_index("idx_wf_matching", table_name="automation_workflows")

    # Remove CHECK constraint
    op.drop_constraint("chk_workflow_scope_owner", "automation_workflows", type_="check")

    # Remove columns
    op.drop_column("automation_workflows", "owner_user_id")
    op.drop_column("automation_workflows", "scope")
