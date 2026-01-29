"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization, Task, User


class AutomationWorkflow(Base):
    """
    Automation workflow definition.

    Workflows are triggered by events (case created, status changed, etc.)
    and execute actions (send email, create task, etc.) when conditions match.
    """

    __tablename__ = "automation_workflows"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_workflow_name"),
        Index("idx_wf_org_enabled", "organization_id", "is_enabled"),
        # Scope/owner integrity: org workflows have no owner, personal workflows require owner
        CheckConstraint(
            "(scope = 'org' AND owner_user_id IS NULL) OR "
            "(scope = 'personal' AND owner_user_id IS NOT NULL)",
            name="chk_workflow_scope_owner",
        ),
        # Optimized index for matching workflows at trigger time
        Index(
            "idx_wf_matching",
            "organization_id",
            "scope",
            "owner_user_id",
            "trigger_type",
            "is_enabled",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="workflow")
    schema_version: Mapped[int] = mapped_column(default=1)

    # Trigger
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # Conditions
    conditions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    condition_logic: Mapped[str] = mapped_column(String(10), default="AND")

    # Actions
    actions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # State
    is_enabled: Mapped[bool] = mapped_column(default=True)
    run_count: Mapped[int] = mapped_column(default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Recurrence settings
    recurrence_mode: Mapped[str] = mapped_column(
        String(20), server_default=text("'one_time'"), nullable=False
    )  # 'one_time' | 'recurring'
    recurrence_interval_hours: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 24 = daily, 168 = weekly
    recurrence_stop_on_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # Stop when entity reaches this status

    # Rate limiting (None = unlimited)
    rate_limit_per_hour: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Max executions per hour globally
    rate_limit_per_entity_per_day: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Max times can run on same entity per 24h

    # System workflow fields
    is_system_workflow: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    system_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Unique key for system workflows

    # Workflow scope: 'org' (org-wide) or 'personal' (user-specific)
    scope: Mapped[str] = mapped_column(
        String(20), server_default=text("'org'"), nullable=False
    )  # 'org' | 'personal'
    # Owner for personal workflows (NULL for org workflows)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )

    # First-run review tracking
    requires_review: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Audit
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_user_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_user_id])
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    user_preferences: Mapped[list["UserWorkflowPreference"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowExecution(Base):
    """
    Audit log of workflow executions.

    Every time a workflow runs (or is skipped due to conditions),
    an execution record is created for debugging and analytics.
    """

    __tablename__ = "workflow_executions"
    __table_args__ = (
        Index("idx_exec_workflow", "workflow_id", "executed_at"),
        Index("idx_exec_event", "event_id"),
        Index("idx_exec_entity", "entity_type", "entity_id"),
        Index(
            "idx_exec_paused",
            "organization_id",
            "status",
            postgresql_where=text("status = 'paused'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automation_workflows.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Loop protection
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    depth: Mapped[int] = mapped_column(default=0)
    event_source: Mapped[str] = mapped_column(String(20), nullable=False)

    # Context
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trigger_event: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Dedupe (for scheduled/sweep triggers)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Execution
    matched_conditions: Mapped[bool] = mapped_column(default=True)
    actions_executed: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # Result
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    executed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # ==========================================================================
    # Workflow Approval Pause State
    # ==========================================================================

    # When paused for approval, track which action and task
    paused_at_action_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paused_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "tasks.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_workflow_executions_paused_task_id",
        ),
        nullable=True,
    )

    # Relationships
    workflow: Mapped["AutomationWorkflow"] = relationship(back_populates="executions")
    paused_task: Mapped["Task | None"] = relationship(foreign_keys=[paused_task_id])


class UserWorkflowPreference(Base):
    """
    Per-user workflow opt-out preferences.

    Allows individual users to opt out of specific workflows
    (e.g., disable notification workflows they don't want).
    """

    __tablename__ = "user_workflow_preferences"
    __table_args__ = (UniqueConstraint("user_id", "workflow_id", name="uq_user_workflow"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automation_workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_opted_out: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship()
    workflow: Mapped["AutomationWorkflow"] = relationship(back_populates="user_preferences")


class WorkflowResumeJob(Base):
    """
    Idempotency table for workflow resume jobs.

    Prevents duplicate resume processing when the same approval
    is resolved multiple times (e.g., race conditions, retries).
    """

    __tablename__ = "workflow_resume_jobs"
    __table_args__ = (
        Index(
            "idx_resume_jobs_pending",
            "status",
            "created_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship()
    task: Mapped["Task"] = relationship()


# =============================================================================
# Workflow Templates (Marketplace)
# =============================================================================


class WorkflowTemplate(Base):
    """
    Reusable workflow templates for the template marketplace.

    Templates can be global (system-provided) or organization-specific.
    Users can create workflows from templates via "Use Template".
    """

    __tablename__ = "workflow_templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_template_name"),
        Index("idx_template_org", "organization_id"),
        Index("idx_template_category", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="template")
    category: Mapped[str] = mapped_column(
        String(50), default="general"
    )  # "onboarding", "follow-up", "notifications", "compliance", "general"

    # Workflow configuration (template content)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    conditions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    condition_logic: Mapped[str] = mapped_column(String(10), default="AND")
    actions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # Scope
    is_global: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )  # True = system template, False = org-specific
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,  # Null for global templates
    )

    # Usage tracking
    usage_count: Mapped[int] = mapped_column(default=0)

    # Audit
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization | None"] = relationship()
    created_by: Mapped["User | None"] = relationship()


# =============================================================================
# Zoom Meetings
# =============================================================================
