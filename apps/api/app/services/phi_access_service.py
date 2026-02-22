"""Shared helpers for PHI-access audit logging."""

from __future__ import annotations

from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.types import JsonObject


def classify_query_type(query: str | None) -> str | None:
    """Classify query strings for PHI audit metadata."""
    if not query:
        return None
    if "@" in query:
        return "email"
    digit_count = sum(1 for ch in query if ch.isdigit())
    return "phone" if digit_count >= 7 else "text"


def log_phi_access(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID | None,
    target_type: str,
    target_id: UUID | None,
    request: Request | None = None,
    details: JsonObject | None = None,
    query: str | None = None,
    commit: bool = True,
) -> None:
    """Log PHI access with optional query classification and commit."""
    from app.services import audit_service

    payload: JsonObject = dict(details or {})
    if "q_type" not in payload:
        payload["q_type"] = classify_query_type(query)

    audit_service.log_phi_access(
        db=db,
        org_id=org_id,
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        request=request,
        details=payload,
    )
    if commit:
        db.commit()
