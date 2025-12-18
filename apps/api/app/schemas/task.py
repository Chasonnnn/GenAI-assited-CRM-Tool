"""Pydantic schemas for tasks."""

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import TaskType


class TaskCreate(BaseModel):
    """Request to create a task."""
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    task_type: TaskType = TaskType.OTHER
    case_id: UUID | None = None
    assigned_to_user_id: UUID | None = None
    due_date: date | None = None
    due_time: time | None = None
    duration_minutes: int | None = Field(None, ge=1, le=7 * 24 * 60)


class TaskUpdate(BaseModel):
    """Request to update a task (partial)."""
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    task_type: TaskType | None = None
    assigned_to_user_id: UUID | None = None
    due_date: date | None = None
    due_time: time | None = None
    duration_minutes: int | None = Field(None, ge=1, le=7 * 24 * 60)


class TaskRead(BaseModel):
    """Full task response."""
    id: UUID
    case_id: UUID | None
    case_number: str | None = None
    assigned_to_user_id: UUID | None
    assigned_to_name: str | None = None
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
    
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListItem(BaseModel):
    """Compact task for list views."""
    id: UUID
    case_id: UUID | None
    case_number: str | None = None
    title: str
    task_type: TaskType
    due_date: date | None
    due_time: time | None = None
    duration_minutes: int | None = None
    is_completed: bool
    assigned_to_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated task list."""
    items: list[TaskListItem]
    total: int
    page: int
    per_page: int
    pages: int
