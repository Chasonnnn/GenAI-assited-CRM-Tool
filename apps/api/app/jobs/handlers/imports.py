"""Import job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_csv_import(db, job) -> None:
    """
    Process CSV import job in background.

    Payload:
        - import_id: UUID of the SurrogateImport record
        - dedupe_action: "skip" (default) or other action
    """
    from app.services import import_service
    from app.db.models import SurrogateImport

    payload = job.payload or {}
    import_id = payload.get("import_id")
    dedupe_action = payload.get("dedupe_action", "skip")

    if not import_id:
        raise Exception("Missing import_id in payload")

    # Get import record
    import_record = db.query(SurrogateImport).filter(SurrogateImport.id == UUID(import_id)).first()

    if not import_record:
        raise Exception(f"Import record {import_id} not found")

    if import_record.status == "cancelled":
        logger.info("CSV import cancelled for %s; skipping job", import_id)
        return

    if not import_record.file_content:
        raise Exception(f"Import record {import_id} missing file content")

    logger.info("Starting CSV import job: %s, rows=%s", import_id, import_record.total_rows)

    try:
        import_service.run_import_execution(
            db=db,
            org_id=job.organization_id,
            import_record=import_record,
            use_mappings=bool(payload.get("use_mappings")),
            dedupe_action=dedupe_action,
            unknown_column_behavior=payload.get("unknown_column_behavior"),
        )
        logger.info("CSV import completed: %s", import_id)
    except Exception as e:
        logger.error("CSV import failed: %s - %s", import_id, e)
        raise
