"""Jobs router - view background jobs (developer only)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.db.enums import Role, JobStatus, JobType
from app.schemas.job import JobRead, JobListItem
from app.services import job_service

router = APIRouter(tags=["Jobs"])


@router.get("", response_model=list[JobListItem])
def list_jobs(
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    session: dict = Depends(require_role(Role.DEVELOPER)),
):
    """List recent jobs for the organization (developer only)."""
    jobs = job_service.list_jobs(
        db,
        org_id=session["org_id"],
        status=status,
        job_type=job_type,
        limit=min(limit, 100),
    )
    return jobs


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(require_role(Role.DEVELOPER)),
):
    """Get a job by ID (developer only)."""
    job = job_service.get_job(db, job_id, org_id=session["org_id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
