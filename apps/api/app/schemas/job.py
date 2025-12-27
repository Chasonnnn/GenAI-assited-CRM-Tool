"""Pydantic schemas for background jobs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.enums import JobType


class JobBase(BaseModel):
    """Base job fields."""
    job_type: JobType
    payload: dict = {}
    run_at: datetime | None = None
    max_attempts: int = 3


class JobCreate(JobBase):
    """Create a new job."""
    pass


class JobRead(BaseModel):
    """Job response schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    organization_id: UUID
    job_type: str
    payload: dict
    run_at: datetime
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: datetime
    completed_at: datetime | None


class JobListItem(BaseModel):
    """Job list item (minimal)."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    job_type: str
    status: str
    run_at: datetime
    attempts: int
    created_at: datetime
    completed_at: datetime | None
