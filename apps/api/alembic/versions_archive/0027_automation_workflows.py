"""Add automation workflows system.

Revision ID: 0027_automation_workflows
Revises: f3bc6a65a816
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "0027_automation_workflows"
down_revision = "f3bc6a65a816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Automation Workflows table
    op.create_table(
        "automation_workflows",
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
        # Metadata
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("icon", sa.String(50), server_default="workflow"),
        sa.Column("schema_version", sa.Integer, server_default="1"),
        # Trigger
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_config", postgresql.JSONB, nullable=False, server_default="{}"),
        # Conditions
        sa.Column("conditions", postgresql.JSONB, server_default="[]"),
        sa.Column("condition_logic", sa.String(10), server_default="AND"),
        sa.Column("condition_field_list", postgresql.ARRAY(sa.Text), nullable=True),
        # Actions
        sa.Column("actions", postgresql.JSONB, nullable=False, server_default="[]"),
        # State
        sa.Column("is_enabled", sa.Boolean, server_default="true"),
        sa.Column("run_count", sa.Integer, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        # Audit
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
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
        # Constraints
        sa.UniqueConstraint("organization_id", "name", name="uq_workflow_name"),
    )

    # Indexes for workflow lookup
    op.create_index(
        "idx_wf_org_enabled",
        "automation_workflows",
        ["organization_id", "is_enabled"],
    )
    op.create_index(
        "idx_wf_trigger",
        "automation_workflows",
        ["organization_id", "trigger_type"],
        postgresql_where=sa.text("is_enabled = true"),
    )

    # Workflow Executions table (audit log)
    op.create_table(
        "workflow_executions",
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
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Loop protection
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depth", sa.Integer, server_default="0"),
        sa.Column("event_source", sa.String(20), nullable=False),
        # Context
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_event", postgresql.JSONB, nullable=False),
        # Dedupe
        sa.Column("dedupe_key", sa.String(200), nullable=True),
        # Execution
        sa.Column("matched_conditions", sa.Boolean, server_default="true"),
        sa.Column("actions_executed", postgresql.JSONB, server_default="[]"),
        # Result
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Indexes for execution lookup
    op.create_index(
        "idx_exec_workflow",
        "workflow_executions",
        ["workflow_id", "executed_at"],
        postgresql_ops={"executed_at": "DESC"},
    )
    op.create_index(
        "idx_exec_event",
        "workflow_executions",
        ["event_id"],
    )
    op.create_index(
        "idx_exec_entity",
        "workflow_executions",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "idx_exec_status",
        "workflow_executions",
        ["organization_id", "status", "executed_at"],
        postgresql_ops={"executed_at": "DESC"},
    )

    # Unique constraint for dedupe (partial - only where dedupe_key is not null)
    op.create_index(
        "uq_exec_dedupe",
        "workflow_executions",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )

    # User Workflow Preferences table (per-user opt-out)
    op.create_table(
        "user_workflow_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_opted_out", sa.Boolean, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "workflow_id", name="uq_user_workflow"),
    )

    # Add WORKFLOW_SWEEP and WORKFLOW_EMAIL to job types (handled in enums.py)


def downgrade() -> None:
    op.drop_table("user_workflow_preferences")
    op.drop_index("uq_exec_dedupe", table_name="workflow_executions")
    op.drop_index("idx_exec_status", table_name="workflow_executions")
    op.drop_index("idx_exec_entity", table_name="workflow_executions")
    op.drop_index("idx_exec_event", table_name="workflow_executions")
    op.drop_index("idx_exec_workflow", table_name="workflow_executions")
    op.drop_table("workflow_executions")
    op.drop_index("idx_wf_trigger", table_name="automation_workflows")
    op.drop_index("idx_wf_org_enabled", table_name="automation_workflows")
    op.drop_table("automation_workflows")
