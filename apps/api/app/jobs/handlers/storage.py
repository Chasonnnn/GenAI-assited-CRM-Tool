"""Durable external-storage cleanup jobs."""

from __future__ import annotations

from app.services import attachment_service


async def process_storage_delete(db, job) -> None:
    """Delete an organization-scoped batch of storage objects idempotently."""
    del db
    if job.organization_id is None:
        raise ValueError("Storage deletion requires an organization-scoped job")

    storage_keys = (job.payload or {}).get("storage_keys")
    if not isinstance(storage_keys, list) or not storage_keys or len(storage_keys) > 100:
        raise ValueError("Storage deletion requires 1 to 100 storage keys")

    org_id = str(job.organization_id)
    allowed_prefixes = (f"{org_id}/", f"messaging/{org_id}/")
    for storage_key in storage_keys:
        if not isinstance(storage_key, str) or not storage_key.startswith(allowed_prefixes):
            raise ValueError("Storage key is outside the job organization")

    for storage_key in storage_keys:
        attachment_service.delete_file(storage_key)
