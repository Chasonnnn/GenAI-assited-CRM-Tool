"""AI schedule parsing routes."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_ai_enabled, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.core.rate_limit import limiter
from app.core.surrogate_access import check_surrogate_access
from app.schemas.auth import UserSession
from app.services.ai_prompt_registry import get_prompt
from app.services.ai_response_validation import parse_json_array
from app.services.ai_provider import ChatMessage
from app.utils.sse import format_sse, sse_preamble, STREAM_HEADERS

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


@router.post(
    "/parse-schedule/stream",
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("10/minute")
async def parse_schedule_stream(
    request: Request,
    body: ParseScheduleRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> StreamingResponse:
    """Stream schedule parsing via SSE."""
    from app.services import ai_settings_service, ip_service, match_service, surrogate_service
    from app.services.schedule_parser import ProposedTask
    from app.db.enums import TaskType
    from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_text

    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if settings and ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted. An admin must accept the data processing consent before using AI.",
        )

    entity_type = None
    entity_id = None
    known_names: list[str] = []

    surrogate_id = body.surrogate_id
    if surrogate_id:
        surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
        if not surrogate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
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

    logger.info(
        f"Parse schedule request: user={session.user_id}, "
        f"entity_type={entity_type}, entity_id={entity_id}, text_len={len(body.text)}"
    )

    # Compute timezone and reference date
    org = None
    if settings:
        from app.services import org_service

        org = org_service.get_org_by_id(db, session.org_id)

    timezone = body.user_timezone or (org.timezone if org else "UTC")
    warnings: list[str] = []
    try:
        tzinfo = ZoneInfo(timezone)
    except Exception:
        warnings.append(f"Invalid timezone '{timezone}', using UTC")
        timezone = "UTC"
        tzinfo = ZoneInfo("UTC")
    reference_date = datetime.now(tzinfo).date()

    # AI settings check
    if not settings or not settings.is_enabled:
        async def _disabled_events() -> AsyncIterator[str]:
            yield sse_preamble()
            yield format_sse("start", {"status": "thinking"})
            response = ParseScheduleResponse(
                proposed_tasks=[],
                warnings=warnings + ["AI is not enabled for this organization"],
                assumed_timezone=timezone,
                assumed_reference_date=reference_date.isoformat(),
            )
            yield format_sse("done", response.model_dump())

        return StreamingResponse(
            _disabled_events(),
            media_type="text/event-stream",
            headers=STREAM_HEADERS,
        )

    provider = ai_settings_service.get_ai_provider_for_settings(settings, session.org_id)
    if not provider:
        missing_message = (
            "Vertex AI configuration is incomplete"
            if settings.provider == "vertex_wif"
            else "AI API key is not configured"
        )

        async def _missing_events() -> AsyncIterator[str]:
            yield sse_preamble()
            yield format_sse("start", {"status": "thinking"})
            response = ParseScheduleResponse(
                proposed_tasks=[],
                warnings=warnings + [missing_message],
                assumed_timezone=timezone,
                assumed_reference_date=reference_date.isoformat(),
            )
            yield format_sse("done", response.model_dump())

        return StreamingResponse(
            _missing_events(),
            media_type="text/event-stream",
            headers=STREAM_HEADERS,
        )

    text = body.text[:10000]
    pii_mapping = PIIMapping() if settings.anonymize_pii else None
    prompt_text = text
    if settings.anonymize_pii and pii_mapping:
        prompt_text = anonymize_text(text, pii_mapping, known_names or None)

    prompt = get_prompt("schedule_parse")
    user_prompt = prompt.render_user(reference_date=reference_date.isoformat(), text=prompt_text)

    messages = [
        ChatMessage(role="system", content=prompt.system),
        ChatMessage(role="user", content=user_prompt),
    ]

    async def event_generator() -> AsyncIterator[str]:
        yield sse_preamble()
        yield format_sse("start", {"status": "thinking"})
        content = ""

        try:
            async for chunk in provider.stream_chat(messages=messages, temperature=0.3, max_tokens=2000):
                if chunk.text:
                    content += chunk.text
                    yield format_sse("delta", {"text": chunk.text})
        except asyncio.CancelledError:
            return
        except Exception as exc:
            response = ParseScheduleResponse(
                proposed_tasks=[],
                warnings=warnings + [f"Parsing error: {str(exc)}"],
                assumed_timezone=timezone,
                assumed_reference_date=reference_date.isoformat(),
            )
            yield format_sse("done", response.model_dump())
            return

        raw_tasks = parse_json_array(content)
        if not raw_tasks:
            response = ParseScheduleResponse(
                proposed_tasks=[],
                warnings=warnings + ["AI did not return valid JSON. Please try rephrasing."],
                assumed_timezone=timezone,
                assumed_reference_date=reference_date.isoformat(),
            )
            yield format_sse("done", response.model_dump())
            return

        proposed_tasks: list[ProposedTask] = []
        for raw_task in raw_tasks:
            if not isinstance(raw_task, dict):
                warnings.append("Invalid task item skipped")
                continue
            try:
                due_date = None
                if raw_task.get("due_date"):
                    try:
                        due_date = date.fromisoformat(raw_task["due_date"])
                    except ValueError:
                        warnings.append(
                            f"Invalid date format for '{raw_task.get('title', 'unknown')}': {raw_task.get('due_date')}"
                        )

                due_time = None
                if raw_task.get("due_time"):
                    try:
                        due_time = time.fromisoformat(raw_task["due_time"])
                    except ValueError:
                        warnings.append(
                            f"Invalid time format for '{raw_task.get('title', 'unknown')}': {raw_task.get('due_time')}"
                        )

                task_type_str = raw_task.get("task_type", "other").lower()
                try:
                    task_type = TaskType(task_type_str)
                except ValueError:
                    task_type = TaskType.OTHER
                    warnings.append(f"Unknown task type '{task_type_str}', using 'other'")

                proposed_task = ProposedTask(
                    title=raw_task.get("title", "Untitled Task")[:255],
                    description=raw_task.get("description"),
                    due_date=due_date,
                    due_time=due_time,
                    task_type=task_type,
                    confidence=float(raw_task.get("confidence", 0.8)),
                )
                if settings.anonymize_pii and pii_mapping:
                    proposed_task.title = rehydrate_text(proposed_task.title, pii_mapping)
                    if proposed_task.description:
                        proposed_task.description = rehydrate_text(
                            proposed_task.description, pii_mapping
                        )
                proposed_tasks.append(proposed_task)

            except Exception as exc:
                logger.warning(f"Failed to parse task: {exc}")
                warnings.append(f"Failed to parse one task: {str(exc)}")

        response = ParseScheduleResponse(
            proposed_tasks=[task.model_dump() for task in proposed_tasks],
            warnings=warnings,
            assumed_timezone=timezone,
            assumed_reference_date=reference_date.isoformat(),
        )
        yield format_sse("done", response.model_dump())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )
