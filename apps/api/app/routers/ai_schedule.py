"""AI schedule parsing routes."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_ai_enabled, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.core.rate_limit import limiter
from app.core.surrogate_access import check_surrogate_access
from app.schemas.auth import UserSession

router = APIRouter()
logger = logging.getLogger(__name__)


class ParseScheduleRequest(BaseModel):
    """Request to parse a schedule text."""

    text: str = Field(..., min_length=1, max_length=10000)
    # At least one entity ID must be provided
    surrogate_id: uuid.UUID | None = None
    intended_parent_id: uuid.UUID | None = None
    match_id: uuid.UUID | None = None
    user_timezone: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_case_id(cls, values):
        if isinstance(values, dict) and not values.get("surrogate_id") and values.get("case_id"):
            values["surrogate_id"] = values["case_id"]
        return values

    @model_validator(mode="after")
    def _validate_entity_ids(self):
        if not any([self.surrogate_id, self.intended_parent_id, self.match_id]):
            raise ValueError(
                "At least one of surrogate_id, intended_parent_id, or match_id must be provided"
            )
        return self


class ParseScheduleResponse(BaseModel):
    """Response with proposed tasks."""

    proposed_tasks: list[dict]
    warnings: list[str]
    assumed_timezone: str
    assumed_reference_date: str


@router.post(
    "/parse-schedule",
    response_model=ParseScheduleResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("10/minute")
async def parse_schedule(
    request: Request,
    body: ParseScheduleRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> ParseScheduleResponse:
    """
    Parse schedule text using AI and extract task proposals.

    At least one of surrogate_id, intended_parent_id, or match_id must be provided.
    User reviews and approves before tasks are created.
    """
    from app.services import ai_settings_service, ip_service, match_service, surrogate_service
    from app.services.schedule_parser import parse_schedule_text

    # Enforce AI consent (consistent with /chat)
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if settings and ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted. An admin must accept the data processing consent before using AI.",
        )

    # Verify entity exists and belongs to org
    entity_type = None
    entity_id = None
    known_names: list[str] = []

    surrogate_id = body.surrogate_id
    if surrogate_id:
        surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
        if not surrogate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
        # Enforce surrogate access (owner/role-based)
        check_surrogate_access(
            surrogate=surrogate,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )
        if surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())
        entity_type = "case"
        entity_id = surrogate_id
    elif body.intended_parent_id:
        parent = ip_service.get_intended_parent(db, body.intended_parent_id, session.org_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intended parent not found",
            )
        if parent.full_name:
            known_names.append(parent.full_name)
            known_names.extend(parent.full_name.split())
        entity_type = "intended_parent"
        entity_id = body.intended_parent_id
    elif body.match_id:
        match = match_service.get_match(db, body.match_id, session.org_id)
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        # Enforce access to the associated surrogate
        if match.surrogate_id:
            surrogate = surrogate_service.get_surrogate(db, session.org_id, match.surrogate_id)
            if surrogate:
                check_surrogate_access(
                    surrogate=surrogate,
                    user_role=session.role,
                    user_id=session.user_id,
                    db=db,
                    org_id=session.org_id,
                )
                if surrogate.full_name:
                    known_names.append(surrogate.full_name)
                    known_names.extend(surrogate.full_name.split())
        entity_type = "match"
        entity_id = body.match_id

    # Log metadata only (no PII from schedule text)
    logger.info(
        f"Parse schedule request: user={session.user_id}, "
        f"entity_type={entity_type}, entity_id={entity_id}, text_len={len(body.text)}"
    )

    # Parse using AI
    result = await parse_schedule_text(
        db=db,
        org_id=session.org_id,
        text=body.text,
        user_timezone=body.user_timezone,
        known_names=known_names or None,
    )

    return ParseScheduleResponse(
        proposed_tasks=[task.model_dump() for task in result.proposed_tasks],
        warnings=result.warnings,
        assumed_timezone=result.assumed_timezone,
        assumed_reference_date=result.assumed_reference_date.isoformat(),
    )
