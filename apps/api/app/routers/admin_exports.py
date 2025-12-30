"""Developer-only exports for cases, configuration, and analytics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.core.rate_limit import limiter
from app.db.enums import AuditEventType, Role
from app.schemas.auth import UserSession
from app.services import admin_export_service, audit_service, analytics_service


router = APIRouter(prefix="/admin/exports", tags=["Admin - Exports"])


@router.get("/cases", response_class=StreamingResponse)
@limiter.limit("5/minute")
def export_cases(
    request: Request,
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export all cases (CSV)."""
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_EXPORT_CASES,
        actor_user_id=session.user_id,
        details={"export": "cases_csv"},
    )
    db.commit()

    filename = (
        f"cases_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        admin_export_service.stream_cases_csv(db, session.org_id),
        media_type="text/csv",
        headers=headers,
    )


@router.get("/config")
@limiter.limit("5/minute")
def export_config(
    request: Request,
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
    db: Session = Depends(get_db),
) -> Response:
    """Export organization configuration bundle (ZIP)."""
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_EXPORT_CONFIG,
        actor_user_id=session.user_id,
        details={"export": "org_config_zip"},
    )
    db.commit()

    payload = admin_export_service.build_org_config_zip(db, session.org_id)
    filename = (
        f"org_config_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type="application/zip", headers=headers)


@router.get("/analytics")
@limiter.limit("5/minute")
async def export_analytics(
    request: Request,
    from_date: Optional[str] = Query(None, description="ISO date string"),
    to_date: Optional[str] = Query(None, description="ISO date string"),
    ad_id: Optional[str] = Query(None, description="Optional campaign filter"),
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
    db: Session = Depends(get_db),
) -> Response:
    """Export analytics datasets used by the Reports page (ZIP)."""
    start, end = analytics_service.parse_date_range(from_date, to_date)
    meta_spend = await analytics_service.get_meta_spend_summary(start, end)
    payload = admin_export_service.build_analytics_zip(
        db=db,
        org_id=session.org_id,
        start=start,
        end=end,
        ad_id=ad_id,
        meta_spend=meta_spend,
    )

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_EXPORT_ANALYTICS,
        actor_user_id=session.user_id,
        details={
            "export": "analytics_zip",
            "from_date": from_date,
            "to_date": to_date,
            "ad_id": ad_id,
        },
    )
    db.commit()

    filename = (
        f"analytics_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type="application/zip", headers=headers)
