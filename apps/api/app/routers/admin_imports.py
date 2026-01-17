"""Developer-only imports for org restore."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.rate_limit import limiter
from app.core.permissions import PermissionKey as P
from app.db.enums import AuditEventType
from app.schemas.auth import UserSession
from app.services import admin_import_service, audit_service


router = APIRouter(prefix="/admin/imports", tags=["Admin - Imports"])


def _ensure_dev_env() -> None:
    if not settings.is_dev:
        raise HTTPException(status_code=403, detail="Admin imports are only available in dev mode.")


@router.post("/all")
@limiter.limit("2/minute")
async def import_all(
    request: Request,
    config_zip: UploadFile = File(..., description="Organization config ZIP"),
    surrogates_csv: UploadFile = File(..., description="Surrogates CSV"),
    session: UserSession = Depends(require_permission(P.ADMIN_IMPORTS_MANAGE)),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf_header),
):
    """Import org config + surrogates into an empty org."""
    _ensure_dev_env()

    if not config_zip.filename or not config_zip.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="config_zip must be a .zip file")
    if not surrogates_csv.filename or not surrogates_csv.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="surrogates_csv must be a .csv file")

    config_content = await config_zip.read()
    surrogates_content = await surrogates_csv.read()

    try:
        config_counts = admin_import_service.import_org_config_zip(
            db, session.org_id, config_content
        )
        surrogates_count = admin_import_service.import_surrogates_csv(
            db, session.org_id, surrogates_content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_IMPORT_COMPLETED,
        actor_user_id=session.user_id,
        details={
            "import": "org_config_and_surrogates",
            "surrogates": surrogates_count,
        },
    )
    db.commit()

    return {
        "status": "completed",
        "config": config_counts,
        "surrogates_imported": surrogates_count,
    }


@router.post("/config")
@limiter.limit("2/minute")
async def import_config(
    request: Request,
    config_zip: UploadFile = File(..., description="Organization config ZIP"),
    session: UserSession = Depends(require_permission(P.ADMIN_IMPORTS_MANAGE)),
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


@router.post("/surrogates")
@limiter.limit("2/minute")
async def import_surrogates(
    request: Request,
    surrogates_csv: UploadFile = File(..., description="Surrogates CSV"),
    session: UserSession = Depends(require_permission(P.ADMIN_IMPORTS_MANAGE)),
    db: Session = Depends(get_db),
    _csrf: None = Depends(require_csrf_header),
):
    """Import surrogates CSV into an empty org (requires config imported first)."""
    _ensure_dev_env()

    if not surrogates_csv.filename or not surrogates_csv.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="surrogates_csv must be a .csv file")

    surrogates_content = await surrogates_csv.read()

    try:
        surrogates_count = admin_import_service.import_surrogates_csv(
            db, session.org_id, surrogates_content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_IMPORT_COMPLETED,
        actor_user_id=session.user_id,
        details={"import": "surrogates_csv", "surrogates": surrogates_count},
    )
    db.commit()

    return {"status": "completed", "surrogates_imported": surrogates_count}
