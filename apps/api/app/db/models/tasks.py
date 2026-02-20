"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    TaskType,
)

if TYPE_CHECKING:
    from app.db.models import Surrogate, User


class Task(Base):
    """
    To-do items optionally linked to cases.

    Permissions:
    - Creator: edit/delete
    - Assignee: edit/complete
    - Manager+: all
    """

    __tablename__ = "tasks"
    __table_args__ = (
        Index(
            "idx_tasks_org_owner",
            "organization_id",
            "owner_type",
            "owner_id",
            "is_completed",
        ),
        Index("idx_tasks_org_status", "organization_id", "is_completed"),
        Index("idx_tasks_org_created", "organization_id", "created_at"),
        Index("idx_tasks_org_updated", "organization_id", "updated_at"),
        Index(
            "idx_tasks_google_task_lookup",
            "organization_id",
            "owner_type",
            "owner_id",
            "google_task_list_id",
            "google_task_id",
        ),
        Index(
            "idx_tasks_due",
            "organization_id",
            "due_date",
            postgresql_where=text("is_completed = FALSE"),
        ),
        Index("idx_tasks_intended_parent", "intended_parent_id"),
        Index(
            "idx_task_wf_approval_unique",
            "workflow_execution_id",
            "workflow_action_index",
            unique=True,
            postgresql_where=text("task_type = 'workflow_approval'"),
        ),
        Index(
            "idx_tasks_pending_approvals",
            "organization_id",
            "status",
            "due_at",
            postgresql_where=text(
                "task_type = 'workflow_approval' AND status IN ('pending', 'in_progress')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=True
    )
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Ownership (Salesforce-style single owner model)
    # owner_type="user" + owner_id=user_id, or owner_type="queue" + owner_id=queue_id
    owner_type: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(
        String(50), server_default=text(f"'{TaskType.OTHER.value}'"), nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_completed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    google_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_task_list_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_task_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # ==========================================================================
    # Workflow Approval Fields (for task_type='workflow_approval')
    # ==========================================================================

    # Workflow execution reference
    workflow_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Action context
    workflow_action_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workflow_action_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workflow_action_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_action_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Internal only - never exposed via API"
    )

    # Audit context
    workflow_triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Resolution
    workflow_denial_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status for workflow approvals (richer than is_completed boolean)
    status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="For workflow approvals: pending, completed, denied, expired",
    )

    # Due datetime with time precision (for approval deadlines)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    surrogate: Mapped["Surrogate | None"] = relationship()
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])
    completed_by: Mapped["User | None"] = relationship(foreign_keys=[completed_by_user_id])
    workflow_triggered_by: Mapped["User | None"] = relationship(
        foreign_keys=[workflow_triggered_by_user_id]
    )

    @property
    def is_workflow_approval(self) -> bool:
        """Check if this is a workflow approval task."""
        return self.task_type == "workflow_approval"


class EntityNote(Base):
    """
    Polymorphic notes for any entity (case, intended_parent, etc.).

    Uses entity_type + entity_id pattern instead of separate FK columns.
    Author or admin+ can delete.
    """

    __tablename__ = "entity_notes"
    __table_args__ = (
        Index("idx_entity_notes_lookup", "entity_type", "entity_id", "created_at"),
        Index("idx_entity_notes_org", "organization_id", "created_at"),
        # GIN index for full-text search
        Index(
            "ix_entity_notes_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Polymorphic reference
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'case', 'intended_parent'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Note content
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)  # HTML allowed, sanitized

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    author: Mapped["User"] = relationship()


# =============================================================================
# Notifications
# =============================================================================
