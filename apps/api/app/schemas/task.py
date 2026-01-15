"""Pydantic schemas for tasks."""

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.db.enums import TaskType


class TaskCreate(BaseModel):
    """Request to create a task."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    task_type: TaskType = TaskType.OTHER
    surrogate_id: UUID | None = None
    intended_parent_id: UUID | None = None
    # New owner model
    owner_type: str | None = Field(None, description="'user' or 'queue'")
    owner_id: UUID | None = Field(None, description="User or Queue ID")
    due_date: date | None = None
    due_time: time | None = None
    duration_minutes: int | None = Field(None, ge=1, le=7 * 24 * 60)


class TaskUpdate(BaseModel):
    """Request to update a task (partial)."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    task_type: TaskType | None = None
    intended_parent_id: UUID | None = None
    # New owner model
    owner_type: str | None = Field(None, description="'user' or 'queue'")
    owner_id: UUID | None = Field(None, description="User or Queue ID")
    due_date: date | None = None
    due_time: time | None = None
    duration_minutes: int | None = Field(None, ge=1, le=7 * 24 * 60)


class TaskRead(BaseModel):
    """Full task response."""

    id: UUID
    surrogate_id: UUID | None
    surrogate_number: str | None = None
    # Owner (new model)
    owner_type: str
    owner_id: UUID
    owner_name: str | None = None  # Resolved user or queue name
    created_by_user_id: UUID
    created_by_name: str | None = None

    title: str
    description: str | None
    task_type: TaskType
    due_date: date | None
    due_time: time | None
    duration_minutes: int | None = None
    is_completed: bool
    completed_at: datetime | None
    completed_by_name: str | None = None

    # Workflow approval fields (null for non-approval tasks)
    # NOTE: workflow_action_payload is NEVER exposed via API (internal only)
    status: str | None = None
    workflow_execution_id: UUID | None = None
    workflow_action_type: str | None = None
    workflow_action_preview: str | None = None
    workflow_denial_reason: str | None = None
    workflow_triggered_by_user_id: UUID | None = None
    workflow_triggered_by_name: str | None = None
    due_at: datetime | None = None

    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_workflow_approval(self) -> bool:
        """Check if this is a workflow approval task."""
        return self.task_type == TaskType.WORKFLOW_APPROVAL

    model_config = {"from_attributes": True}


class TaskListItem(BaseModel):
    """Compact task for list views."""

    id: UUID
    surrogate_id: UUID | None
    surrogate_number: str | None = None
    title: str
    task_type: TaskType
    owner_type: str
    owner_id: UUID
    owner_name: str | None = None
    due_date: date | None
    due_time: time | None = None
    duration_minutes: int | None = None
    is_completed: bool
    created_at: datetime

    # Workflow approval fields for list views
    status: str | None = None
    workflow_action_type: str | None = None
    workflow_action_preview: str | None = None
    due_at: datetime | None = None

    @computed_field
    @property
    def is_workflow_approval(self) -> bool:
        """Check if this is a workflow approval task."""
        return self.task_type == TaskType.WORKFLOW_APPROVAL

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated task list."""

    items: list[TaskListItem]
    total: int
    page: int
    per_page: int
    pages: int


class BulkTaskComplete(BaseModel):
    """Request to complete multiple tasks."""

    task_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class BulkCompleteResponse(BaseModel):
    """Response for bulk task completion."""

    completed: int
    failed: list[dict]  # [{"task_id": str, "reason": str}]


class WorkflowApprovalResolve(BaseModel):
    """Request to approve or deny a workflow approval task."""

    decision: Literal["approve", "deny"]
    reason: str | None = Field(None, max_length=1000, description="Optional denial reason")
