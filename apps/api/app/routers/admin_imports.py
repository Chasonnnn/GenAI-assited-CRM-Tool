"""Developer-only imports for org restore."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, require_csrf_header, require_roles
from app.core.rate_limit import limiter
from app.db.enums import AuditEventType, Role
from app.schemas.auth import UserSession
from app.services import admin_import_service, audit_service


router = APIRouter(prefix="/admin/imports", tags=["Admin - Imports"])


def _ensure_dev_env() -> None:
    if settings.ENV not in ("dev", "test"):
        raise HTTPException(
            status_code=403, detail="Admin imports are only available in dev mode."
        )


@router.post("/all")
@limiter.limit("2/minute")
async def import_all(
    request: Request,
    config_zip: UploadFile = File(..., description="Organization config ZIP"),
    cases_csv: UploadFile = File(..., description="Cases CSV"),
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf_header),
):
    """Import org config + cases into an empty org."""
    _ensure_dev_env()

    if not config_zip.filename or not config_zip.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="config_zip must be a .zip file")
    if not cases_csv.filename or not cases_csv.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="cases_csv must be a .csv file")

    config_content = await config_zip.read()
    cases_content = await cases_csv.read()

    try:
        config_counts = admin_import_service.import_org_config_zip(
            db, session.org_id, config_content
        )
        cases_count = admin_import_service.import_cases_csv(
            db, session.org_id, cases_content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_IMPORT_COMPLETED,
        actor_user_id=session.user_id,
        details={"import": "org_config_and_cases", "cases": cases_count},
    )
    db.commit()

    return {
        "status": "completed",
        "config": config_counts,
        "cases_imported": cases_count,
    }


@router.post("/config")
@limiter.limit("2/minute")
async def import_config(
    request: Request,
    config_zip: UploadFile = File(..., description="Organization config ZIP"),
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf_header),
):
    """Import org config into an empty org."""
    _ensure_dev_env()

    if not config_zip.filename or not config_zip.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="config_zip must be a .zip file")

    config_content = await config_zip.read()

    try:
        config_counts = admin_import_service.import_org_config_zip(
            db, session.org_id, config_content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_IMPORT_COMPLETED,
        actor_user_id=session.user_id,
        details={"import": "org_config"},
    )
    db.commit()

    return {"status": "completed", "config": config_counts}


@router.post("/cases")
@limiter.limit("2/minute")
async def import_cases(
    request: Request,
    cases_csv: UploadFile = File(..., description="Cases CSV"),
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf_header),
):
    """Import cases CSV into an empty org (requires config imported first)."""
    _ensure_dev_env()

    if not cases_csv.filename or not cases_csv.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="cases_csv must be a .csv file")

    cases_content = await cases_csv.read()

    try:
        cases_count = admin_import_service.import_cases_csv(
            db, session.org_id, cases_content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_IMPORT_COMPLETED,
        actor_user_id=session.user_id,
        details={"import": "cases_csv", "cases": cases_count},
    )
    db.commit()

    return {"status": "completed", "cases_imported": cases_count}
