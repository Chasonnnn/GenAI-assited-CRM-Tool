"""Add workflow approval columns to tasks and workflow_executions.

Revision ID: h1b2c3d4e5f6
Revises: b713579f03ec
Create Date: 2026-01-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "h1b2c3d4e5f6"
down_revision = "b713579f03ec"
branch_labels = None
depends_on = None

# System user constants
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"
SYSTEM_USER_EMAIL = "system@internal"
SYSTEM_USER_DISPLAY_NAME = "System"


def upgrade() -> None:
    # ==========================================================================
    # 1. Add workflow approval columns to tasks table
    # ==========================================================================

    # Workflow execution reference
    op.add_column(
        "tasks",
        sa.Column(
            "workflow_execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_executions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Action context
    op.add_column(
        "tasks",
        sa.Column("workflow_action_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("workflow_action_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("workflow_action_preview", sa.Text(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "workflow_action_payload",
            postgresql.JSONB(),
            nullable=True,
            comment="Internal only - never exposed via API",
        ),
    )

    # Audit context
    op.add_column(
        "tasks",
        sa.Column(
            "workflow_triggered_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Resolution
    op.add_column(
        "tasks",
        sa.Column("workflow_denial_reason", sa.Text(), nullable=True),
    )

    # Task status (for workflow approvals which need richer status than is_completed)
    op.add_column(
        "tasks",
        sa.Column(
            "status",
            sa.String(20),
            nullable=True,
            comment="For workflow approvals: pending, completed, denied, expired",
        ),
    )

    # Due datetime with time (more precise than due_date for approvals)
    op.add_column(
        "tasks",
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Unique index for idempotency: one approval per execution+action
    op.create_index(
        "idx_task_wf_approval_unique",
        "tasks",
        ["workflow_execution_id", "workflow_action_index"],
        unique=True,
        postgresql_where=sa.text("task_type = 'workflow_approval'"),
    )

    # Index for finding pending approvals
    op.create_index(
        "idx_tasks_pending_approvals",
        "tasks",
        ["organization_id", "status", "due_at"],
        postgresql_where=sa.text(
            "task_type = 'workflow_approval' AND status IN ('pending', 'in_progress')"
        ),
    )

    # ==========================================================================
    # 2. Add paused state columns to workflow_executions
    # ==========================================================================

    op.add_column(
        "workflow_executions",
        sa.Column("paused_at_action_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "workflow_executions",
        sa.Column(
            "paused_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Index for finding paused executions
    op.create_index(
        "idx_exec_paused",
        "workflow_executions",
        ["organization_id", "status"],
        postgresql_where=sa.text("status = 'paused'"),
    )

    # ==========================================================================
    # 3. Create system user (for workflow-created tasks)
    # ==========================================================================

    # Insert system user if not exists
    op.execute(
        f"""
        INSERT INTO users (id, email, display_name, is_active, created_at, updated_at)
        VALUES (
            '{SYSTEM_USER_ID}'::uuid,
            '{SYSTEM_USER_EMAIL}',
            '{SYSTEM_USER_DISPLAY_NAME}',
            false,
            now(),
            now()
        )
        ON CONFLICT (id) DO NOTHING
        """
    )

    # ==========================================================================
    # 4. Create workflow resume job idempotency table
    # ==========================================================================

    op.create_table(
        "workflow_resume_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_index(
        "idx_resume_jobs_pending",
        "workflow_resume_jobs",
        ["status", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    # Drop resume jobs table
    op.drop_index("idx_resume_jobs_pending", table_name="workflow_resume_jobs")
    op.drop_table("workflow_resume_jobs")

    # Remove system user (optional - may want to keep for data integrity)
    # op.execute(f"DELETE FROM users WHERE id = '{SYSTEM_USER_ID}'::uuid")

    # Remove workflow_executions columns
    op.drop_index("idx_exec_paused", table_name="workflow_executions")
    op.drop_column("workflow_executions", "paused_task_id")
    op.drop_column("workflow_executions", "paused_at_action_index")

    # Remove tasks columns
    op.drop_index("idx_tasks_pending_approvals", table_name="tasks")
    op.drop_index("idx_task_wf_approval_unique", table_name="tasks")
    op.drop_column("tasks", "due_at")
    op.drop_column("tasks", "status")
    op.drop_column("tasks", "workflow_denial_reason")
    op.drop_column("tasks", "workflow_triggered_by_user_id")
    op.drop_column("tasks", "workflow_action_payload")
    op.drop_column("tasks", "workflow_action_preview")
    op.drop_column("tasks", "workflow_action_type")
    op.drop_column("tasks", "workflow_action_index")
    op.drop_column("tasks", "workflow_execution_id")
