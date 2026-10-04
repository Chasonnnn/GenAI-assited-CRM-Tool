"""Durable external-storage cleanup jobs."""

from __future__ import annotations

import os

from app.core.config import settings
from app.services import attachment_service, org_logo_service, storage_url_service


async def process_storage_delete(db, job) -> None:
    """Delete an organization-scoped batch of storage objects idempotently."""
    del db
    if job.organization_id is None:
        raise ValueError("Storage deletion requires an organization-scoped job")

    storage_keys = (job.payload or {}).get("storage_keys")
    if not isinstance(storage_keys, list) or not storage_keys or len(storage_keys) > 100:
        raise ValueError("Storage deletion requires 1 to 100 storage keys")

    org_id = str(job.organization_id)
    allowed_prefixes = (f"{org_id}/", f"messaging/{org_id}/", f"logos/{org_id}/")
    for storage_key in storage_keys:
        if not isinstance(storage_key, str) or not storage_key.startswith(allowed_prefixes):
            raise ValueError("Storage key is outside the job organization")
        if (
            storage_key.startswith(f"logos/{org_id}/")
            and os.path.normpath(storage_key) != storage_key
        ):
            raise ValueError("Invalid logo storage key")

    for storage_key in storage_keys:
        if storage_key.startswith(f"logos/{org_id}/"):
            # Logos have a separate local fallback directory from attachments.
            logo_url = (
                storage_url_service.build_public_url(settings.S3_BUCKET, storage_key)
                if settings.STORAGE_BACKEND == "s3"
                else org_logo_service.build_local_logo_url(storage_key)
            )
            org_logo_service.delete_logo_from_storage(logo_url)
        else:
            attachment_service.delete_file(storage_key)
