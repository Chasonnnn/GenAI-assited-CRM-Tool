"""Fence new match data until all application readers support it."""

from fastapi import HTTPException

from app.core.config import settings


def require_match_expansion() -> None:
    if not settings.MATCH_CASE_EXPANSION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="New match features are temporarily unavailable",
        )
