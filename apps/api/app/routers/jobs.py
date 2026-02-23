"""Jobs router - view background jobs (developer only)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.db.enums import JobStatus, JobType
from app.schemas.job import (
    JobListItem,
    JobRead,
    JobReplayBulkRequest,
    JobReplayBulkResponse,
    JobReplayRequest,
)
from app.services import job_service

router = APIRouter(
    tags=["Jobs"],
    dependencies=[Depends(require_permission(POLICIES["jobs"].default))],
)


@router.get("", response_model=list[JobListItem])
def list_jobs(
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """List recent jobs for the organization (developer only)."""
    jobs = job_service.list_jobs(
        db,
        org_id=session.org_id,
        status=status,
        job_type=job_type,
        limit=min(limit, 100),
    )
    return jobs


@router.get("/dlq", response_model=list[JobRead])
def list_dead_letter_jobs(
    job_type: JobType | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """List failed jobs (dead-letter queue) for the organization."""
    return job_service.list_dead_letter_jobs(
        db,
        org_id=session.org_id,
        job_type=job_type,
        limit=limit,
    )


@router.post(
    "/dlq/replay",
    response_model=JobReplayBulkResponse,
    dependencies=[Depends(require_csrf_header)],
)
def replay_dead_letter_jobs(
    data: JobReplayBulkRequest,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """Replay failed jobs in bulk."""
    jobs = job_service.replay_failed_jobs(
        db,
        org_id=session.org_id,
        job_type=data.job_type,
        limit=data.limit,
        reason=data.reason,
    )
    return JobReplayBulkResponse(
        replayed=len(jobs),
        job_ids=[job.id for job in jobs],
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """Get a job by ID (developer only)."""
    job = job_service.get_job(db, job_id, org_id=session.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post(
    "/{job_id}/replay",
    response_model=JobRead,
    dependencies=[Depends(require_csrf_header)],
)
def replay_dead_letter_job(
    job_id: UUID,
    data: JobReplayRequest,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """Replay a single failed job."""
    try:
        return job_service.replay_failed_job(
            db,
            org_id=session.org_id,
            job_id=job_id,
            reason=data.reason,
        )
    except ValueError as exc:
        message = str(exc)
        if message == "Job not found":
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=422, detail=message) from exc
