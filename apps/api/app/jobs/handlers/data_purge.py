"""Data purge job handlers."""

from __future__ import annotations

from uuid import UUID


async def process_data_purge(db, job) -> None:
    """Process data purge job based on retention policies."""
    from app.services import compliance_service

    payload = job.payload or {}
    org_id = payload.get("org_id")
    user_id = payload.get("user_id")
    if not org_id:
        raise Exception("Missing org_id in job payload")

    compliance_service.execute_purge(
        db=db,
        org_id=UUID(org_id),
        user_id=UUID(user_id) if user_id else None,
    )
