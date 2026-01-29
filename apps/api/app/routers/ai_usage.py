"""AI usage analytics routes."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_permission
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession

router = APIRouter()


@router.get("/usage/summary")
def get_usage_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USAGE_VIEW)),
) -> dict[str, Any]:
    """Get organization usage summary."""
    from app.services import ai_usage_service

    return ai_usage_service.get_org_usage_summary(db, session.org_id, days)


@router.get("/usage/by-model")
def get_usage_by_model(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USAGE_VIEW)),
) -> dict[str, Any]:
    """Get usage breakdown by AI model."""
    from app.services import ai_usage_service

    return {"models": ai_usage_service.get_usage_by_model(db, session.org_id, days)}


@router.get("/usage/daily")
def get_daily_usage(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USAGE_VIEW)),
) -> dict[str, Any]:
    """Get daily usage breakdown."""
    from app.services import ai_usage_service

    return {"daily": ai_usage_service.get_daily_usage(db, session.org_id, days)}


@router.get("/usage/top-users")
def get_top_users(
    days: int = 30,
    limit: int = 10,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USAGE_VIEW)),
) -> dict[str, Any]:
    """Get top users by AI usage."""
    from app.services import ai_usage_service

    return {"users": ai_usage_service.get_top_users(db, session.org_id, days, limit)}


@router.get("/usage/me")
def get_my_usage(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Get current user's AI usage."""
    from app.services import ai_usage_service

    return ai_usage_service.get_user_usage_summary(db, session.user_id, days)
