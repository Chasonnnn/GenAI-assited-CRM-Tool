"""Transactional scheduling for retryable external-storage deletion."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import JobType
from app.services import job_service

STORAGE_DELETE_BATCH_SIZE = 100


def enqueue_storage_deletions(
    db: Session,
    *,
    org_id: UUID,
    storage_keys: list[str],
) -> None:
    """Persist cleanup jobs in the caller's current database transaction."""
    allowed_prefixes = (f"{org_id}/", f"messaging/{org_id}/")
    unique_keys = list(dict.fromkeys(storage_keys))
    if any(not key.startswith(allowed_prefixes) for key in unique_keys):
        raise ValueError("Storage key is outside the cleanup organization")
    for offset in range(0, len(unique_keys), STORAGE_DELETE_BATCH_SIZE):
        job_service.enqueue_job(
            db=db,
            org_id=org_id,
            job_type=JobType.STORAGE_DELETE,
            payload={"storage_keys": unique_keys[offset : offset + STORAGE_DELETE_BATCH_SIZE]},
            commit=False,
        )
