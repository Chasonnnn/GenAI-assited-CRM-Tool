"""Export job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_export_generation(db, job) -> None:
    """Process export generation job."""
    from app.services import compliance_service

    payload = dict(job.payload or {})
    export_job_id = payload.get("export_job_id")
    if not export_job_id:
        raise Exception("Missing export_job_id in job payload")

    compliance_service.process_export_job(db, UUID(export_job_id))


async def process_admin_export(db, job) -> None:
    """Process admin export job."""
    from app.services import admin_export_service, analytics_service

    payload = dict(job.payload or {})
    export_type = payload.get("export_type")

    if not export_type:
        raise Exception("Missing export_type in job payload")

    filename = payload.get("filename") or f"export-{job.id}.zip"

    if export_type == "surrogates_csv":
        file_path = admin_export_service.store_surrogates_csv(db, job.organization_id, filename)
        payload["file_path"] = file_path
        payload["filename"] = filename

    elif export_type == "org_config_zip":
        export_bytes = admin_export_service.build_org_config_zip(db, job.organization_id)
        file_path = admin_export_service.store_export_bytes(
            job.organization_id, filename, export_bytes
        )
        payload["file_path"] = file_path
        payload["filename"] = filename

    elif export_type == "analytics_zip":
        from_date = payload.get("from_date")
        to_date = payload.get("to_date")
        ad_id = payload.get("ad_id")

        start, end = analytics_service.parse_date_range(from_date, to_date)
        meta_spend = await analytics_service.get_meta_spend_summary(
            db=db,
            organization_id=job.organization_id,
            start=start,
            end=end,
        )

        export_bytes = admin_export_service.build_analytics_zip(
            db,
            job.organization_id,
            start,
            end,
            ad_id,
            meta_spend,
        )
        file_path = admin_export_service.store_export_bytes(
            job.organization_id, filename, export_bytes
        )
        payload["file_path"] = file_path
        payload["filename"] = filename

    else:
        raise Exception(f"Unknown export_type: {export_type}")

    # Store response data
    job.payload = payload
    db.commit()

    # Emit analytics export event (no-op if absent)
    try:
        analytics_service.track_admin_export(
            db=db,
            org_id=job.organization_id,
            export_type=export_type,
        )
    except Exception:
        logger.warning("Failed to track admin export")
