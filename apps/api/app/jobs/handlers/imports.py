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

    if not import_record.file_content:
        raise Exception(f"Import record {import_id} missing file content")

    # Update status to running
    import_record.status = "running"
    db.commit()

    logger.info("Starting CSV import job: %s, rows=%s", import_id, import_record.total_rows)

    try:
        # Execute the import
        use_mappings = bool(payload.get("use_mappings"))
        mapping_snapshot = import_record.column_mapping_snapshot or []
        unknown_column_behavior = (
            import_record.unknown_column_behavior
            or payload.get("unknown_column_behavior")
            or "ignore"
        )

        if use_mappings and isinstance(mapping_snapshot, list) and mapping_snapshot:
            from app.services.import_service import ColumnMapping

            mappings: list[ColumnMapping] = []
            for item in mapping_snapshot:
                if not isinstance(item, dict):
                    continue
                action = item.get("action") or ("map" if item.get("surrogate_field") else "ignore")
                mappings.append(
                    ColumnMapping(
                        csv_column=item.get("csv_column", ""),
                        surrogate_field=item.get("surrogate_field"),
                        transformation=item.get("transformation"),
                        action=action,
                        custom_field_key=item.get("custom_field_key"),
                    )
                )

            import_service.execute_import_with_mappings(
                db=db,
                org_id=job.organization_id,
                user_id=import_record.created_by_user_id,
                import_id=import_record.id,
                file_content=import_record.file_content,
                column_mappings=mappings,
                unknown_column_behavior=unknown_column_behavior,
                backdate_created_at=bool(getattr(import_record, "backdate_created_at", False)),
            )
        else:
            import_service.execute_import(
                db=db,
                org_id=job.organization_id,
                user_id=import_record.created_by_user_id,
                import_id=import_record.id,
                file_content=import_record.file_content,
                dedupe_action=dedupe_action,
            )
        import_record.file_content = None
        db.commit()
        logger.info("CSV import completed: %s", import_id)
    except Exception as e:
        # Update import status to failed
        import_record.status = "failed"
        import_record.errors = import_record.errors or []
        import_record.errors.append({"message": str(e)})
        db.commit()
        logger.error("CSV import failed: %s - %s", import_id, e)
        raise
