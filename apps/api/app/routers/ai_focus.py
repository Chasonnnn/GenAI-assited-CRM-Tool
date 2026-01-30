"""Focused AI endpoints (one-shot operations)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    require_ai_enabled,
    require_all_permissions,
    require_csrf_header,
    require_permission,
)
from app.core.permissions import PermissionKey as P
from app.core.rate_limit import limiter
from app.core.surrogate_access import check_surrogate_access
from app.schemas.auth import UserSession
from app.services.ai_prompt_registry import get_prompt
from app.services.ai_prompt_schemas import (
    AIDashboardAnalysisOutput,
    AIDraftEmailOutput,
    AISurrogateSummaryOutput,
)
from app.services.ai_response_validation import parse_json_object, validate_model
from app.services.ai_email_template_service import (
    EmailTemplateGenerationRequest,
    EmailTemplateGenerationResponse,
)

router = APIRouter()


class SummarizeSurrogateRequest(BaseModel):
    """Request to summarize a surrogate."""

    surrogate_id: uuid.UUID


class SummarizeSurrogateResponse(BaseModel):
    """Surrogate summary response."""

    surrogate_number: str
    full_name: str
    summary: str
    current_status: str
    key_dates: dict[str, Any]
    pending_tasks: list[dict[str, Any]]
    recent_activity: str
    suggested_next_steps: list[str]


class EmailType(str, Enum):
    """Types of emails that can be drafted."""

    FOLLOW_UP = "follow_up"
    STATUS_UPDATE = "status_update"
    MEETING_REQUEST = "meeting_request"
    DOCUMENT_REQUEST = "document_request"
    INTRODUCTION = "introduction"


class DraftEmailRequest(BaseModel):
    """Request to draft an email."""

    surrogate_id: uuid.UUID
    email_type: EmailType
    additional_context: str | None = None


class DraftEmailResponse(BaseModel):
    """Draft email response."""

    subject: str
    body: str
    recipient_email: str
    recipient_name: str
    email_type: str


class AnalyzeDashboardResponse(BaseModel):
    """Dashboard analytics response."""

    insights: list[str]
    surrogate_volume_trend: str
    bottlenecks: list[dict[str, Any]]
    recommendations: list[str]
    stats: dict[str, Any]


@router.post(
    "/email-templates/generate",
    response_model=EmailTemplateGenerationResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("10/minute")
def generate_email_template(
    request: Request,
    body: EmailTemplateGenerationRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> EmailTemplateGenerationResponse:
    """Generate a reusable email template using AI."""
    from app.services import ai_email_template_service

    return ai_email_template_service.generate_email_template(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        description=body.description,
    )


EMAIL_PROMPTS = {
    EmailType.FOLLOW_UP: """Draft a professional follow-up email to check in with the applicant. 
The tone should be warm and supportive. Ask how they're doing and if they have any questions.""",
    EmailType.STATUS_UPDATE: """Draft a status update email informing the applicant about their surrogate progress.
Be clear about current status, what's been completed, and what to expect next.""",
    EmailType.MEETING_REQUEST: """Draft an email requesting a meeting or phone call with the applicant.
Suggest a few time options and explain what you'd like to discuss.""",
    EmailType.DOCUMENT_REQUEST: """Draft an email requesting missing or additional documents from the applicant.
Be specific about what documents are needed and why they're important.""",
    EmailType.INTRODUCTION: """Draft an introduction email to share with intended parents about this surrogate candidate.
Highlight key qualifications and background while being professional and respectful of privacy.""",
}


@router.post(
    "/summarize-surrogate",
    response_model=SummarizeSurrogateResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("30/minute")
async def summarize_surrogate(
    request: Request,
    body: SummarizeSurrogateRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> SummarizeSurrogateResponse:
    """Generate a comprehensive summary of a surrogate using AI.

    Requires: use_ai_assistant permission
    """
    from app.services import ai_settings_service, note_service, surrogate_service, task_service
    from app.services.ai_provider import ChatMessage
    from app.services.ai_usage_service import log_usage
    from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_data

    # Check AI is enabled and consent accepted
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if not settings or not settings.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI is not enabled for this organization",
        )
    if ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted",
        )

    # Load surrogate with context
    surrogate = surrogate_service.get_surrogate(db, session.org_id, body.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
    check_surrogate_access(
        surrogate=surrogate,
        user_role=session.role,
        user_id=session.user_id,
        db=db,
        org_id=session.org_id,
    )

    # Load notes and tasks
    notes = note_service.list_notes_limited(
        db=db,
        org_id=session.org_id,
        entity_type="case",
        entity_id=surrogate.id,
        limit=10,
    )
    tasks = task_service.list_open_tasks_for_surrogate(
        db=db,
        surrogate_id=surrogate.id,
        org_id=session.org_id,
        limit=10,
    )

    # Build context
    notes_text = (
        "\n".join([f"- [{n.created_at.strftime('%Y-%m-%d')}] {n.content[:200]}" for n in notes])
        or "No notes yet"
    )
    tasks_text = (
        "\n".join([f"- {t.title} (due: {t.due_date or 'not set'})" for t in tasks])
        or "No pending tasks"
    )

    context = f"""Surrogate #{surrogate.surrogate_number}
Name: {surrogate.full_name}
Email: {surrogate.email}
Status: {surrogate.status_label}
Created: {surrogate.created_at.strftime("%Y-%m-%d")}

Recent Notes:
{notes_text}

Pending Tasks:
{tasks_text}"""

    pii_mapping = PIIMapping() if settings.anonymize_pii else None
    if settings.anonymize_pii and pii_mapping:
        known_names = []
        if surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())
        context = anonymize_text(context, pii_mapping, known_names)

    prompt = get_prompt("surrogate_summary").render_user(context=context)

    # Call AI
    provider = ai_settings_service.get_ai_provider_for_settings(
        settings, session.org_id, user_id=session.user_id
    )
    if not provider:
        missing_message = (
            "Vertex AI configuration is incomplete"
            if settings.provider == "vertex_wif"
            else "AI API key not configured"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=missing_message)

    response = await provider.chat(
        [
            ChatMessage(role="system", content=get_prompt("surrogate_summary").system),
            ChatMessage(role="user", content=prompt),
        ],
        temperature=0.3,
    )

    parsed_model = validate_model(AISurrogateSummaryOutput, parse_json_object(response.content))
    if parsed_model:
        parsed = parsed_model.model_dump()
    else:
        parsed = {
            "summary": response.content[:500],
            "recent_activity": "See notes above",
            "suggested_next_steps": ["Review case details", "Follow up with applicant"],
        }

    if settings.anonymize_pii and pii_mapping:
        parsed = rehydrate_data(parsed, pii_mapping)

    log_usage(
        db=db,
        organization_id=session.org_id,
        user_id=session.user_id,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        estimated_cost_usd=response.estimated_cost_usd,
    )

    # Build key dates
    key_dates = {
        "created": surrogate.created_at.isoformat() if surrogate.created_at else None,
        "updated": surrogate.updated_at.isoformat() if surrogate.updated_at else None,
    }

    # Build pending tasks list
    pending_tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        }
        for t in tasks
    ]

    return SummarizeSurrogateResponse(
        surrogate_number=surrogate.surrogate_number,
        full_name=surrogate.full_name,
        summary=parsed.get("summary", "Unable to generate summary"),
        current_status=surrogate.status_label,
        key_dates=key_dates,
        pending_tasks=pending_tasks,
        recent_activity=parsed.get("recent_activity", "No recent activity"),
        suggested_next_steps=parsed.get("suggested_next_steps", []),
    )


@router.post(
    "/draft-email",
    response_model=DraftEmailResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("30/minute")
async def draft_email(
    request: Request,
    body: DraftEmailRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> DraftEmailResponse:
    """Draft an email for a case using AI.

    Requires: use_ai_assistant permission
    """
    from app.services import ai_settings_service, surrogate_service, user_service
    from app.services.ai_provider import ChatMessage
    from app.services.ai_usage_service import log_usage
    from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_data

    # Check AI is enabled
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if not settings or not settings.is_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI is not enabled")
    if ai_settings_service.is_consent_required(settings):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI consent not accepted")

    # Load surrogate
    surrogate = surrogate_service.get_surrogate(db, session.org_id, body.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
    check_surrogate_access(
        surrogate=surrogate,
        user_role=session.role,
        user_id=session.user_id,
        db=db,
        org_id=session.org_id,
    )

    # Get user name for signature
    user = user_service.get_user_by_id(db, session.user_id)
    if user:
        sender_name = user.signature_name or user.display_name
    else:
        sender_name = "Your Case Manager"

    # Build email prompt
    email_instruction = EMAIL_PROMPTS[body.email_type]
    additional_context = body.additional_context or ""
    pii_mapping = PIIMapping() if settings.anonymize_pii else None
    recipient_name = surrogate.full_name
    recipient_email = surrogate.email
    if settings.anonymize_pii and pii_mapping:
        known_names = []
        if surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())
        if recipient_name:
            recipient_name = pii_mapping.add_name(recipient_name)
        if recipient_email:
            recipient_email = pii_mapping.add_email(recipient_email)
        if additional_context:
            additional_context = anonymize_text(additional_context, pii_mapping, known_names)

    additional = f"\nAdditional context: {additional_context}" if additional_context else ""

    prompt = get_prompt("email_draft").render_user(
        email_instruction=email_instruction,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        surrogate_status=surrogate.status_label,
        additional_context=additional,
        sender_name=sender_name,
    )

    # Call AI
    provider = ai_settings_service.get_ai_provider_for_settings(
        settings, session.org_id, user_id=session.user_id
    )
    if not provider:
        missing_message = (
            "Vertex AI configuration is incomplete"
            if settings.provider == "vertex_wif"
            else "AI API key not configured"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=missing_message)

    response = await provider.chat(
        [
            ChatMessage(role="system", content=get_prompt("email_draft").system),
            ChatMessage(role="user", content=prompt),
        ],
        temperature=0.5,
    )

    parsed_model = validate_model(AIDraftEmailOutput, parse_json_object(response.content))
    if parsed_model:
        parsed = parsed_model.model_dump()
    else:
        parsed = {
            "subject": "Following up on your application",
            "body": response.content,
        }

    if settings.anonymize_pii and pii_mapping:
        parsed = rehydrate_data(parsed, pii_mapping)

    log_usage(
        db=db,
        organization_id=session.org_id,
        user_id=session.user_id,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        estimated_cost_usd=response.estimated_cost_usd,
    )

    return DraftEmailResponse(
        subject=parsed.get("subject", "Following up"),
        body=parsed.get("body", ""),
        recipient_email=surrogate.email,
        recipient_name=surrogate.full_name,
        email_type=body.email_type.value,
    )


@router.post(
    "/analyze-dashboard",
    response_model=AnalyzeDashboardResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("10/minute")
async def analyze_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_all_permissions([P.AI_USE, P.REPORTS_VIEW])),
) -> AnalyzeDashboardResponse:
    """Analyze dashboard data and provide AI-powered insights."""
    from app.services import ai_settings_service, surrogate_service, task_service
    from app.services.ai_provider import ChatMessage
    from app.services.ai_usage_service import log_usage

    # Check AI is enabled
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if not settings or not settings.is_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI is not enabled")
    if ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted",
        )

    # Gather dashboard stats
    now = datetime.now(timezone.utc)

    surrogate_stats = surrogate_service.get_surrogate_stats(db, session.org_id)
    total_surrogates = surrogate_stats["total"]
    status_summary = surrogate_stats["by_status"]
    surrogates_this_week = surrogate_stats["this_week"]
    surrogates_last_week = surrogate_stats["last_week"]
    overdue_tasks = task_service.count_overdue_tasks(db, session.org_id, now.date())

    # Build stats summary
    stats = {
        "total_active_surrogates": total_surrogates,
        "surrogates_this_week": surrogates_this_week,
        "surrogates_last_week": surrogates_last_week,
        "overdue_tasks": overdue_tasks,
        "status_breakdown": status_summary,
    }

    # Determine trend
    if surrogates_this_week > surrogates_last_week:
        trend = f"Increasing ({surrogates_this_week} this week vs {surrogates_last_week} last week)"
    elif surrogates_this_week < surrogates_last_week:
        trend = f"Decreasing ({surrogates_this_week} this week vs {surrogates_last_week} last week)"
    else:
        trend = f"Stable ({surrogates_this_week} surrogates this week)"

    # Identify bottlenecks
    bottlenecks = []
    for status_name, count in status_summary.items():
        if count > total_surrogates * 0.3:  # More than 30% in one status
            bottlenecks.append(
                {
                    "status": status_name,
                    "count": count,
                    "percentage": round(count / total_surrogates * 100, 1)
                    if total_surrogates > 0
                    else 0,
                }
            )

    # Call AI for insights
    provider = ai_settings_service.get_ai_provider_for_settings(
        settings, session.org_id, user_id=session.user_id
    )
    if not provider:
        # Return basic analysis without AI
        return AnalyzeDashboardResponse(
            insights=[f"You have {total_surrogates} active surrogates"],
            surrogate_volume_trend=trend,
            bottlenecks=bottlenecks,
            recommendations=["Configure AI settings for detailed insights"],
            stats=stats,
        )

    prompt = get_prompt("dashboard_analysis").render_user(
        total_surrogates=total_surrogates,
        surrogates_this_week=surrogates_this_week,
        surrogates_last_week=surrogates_last_week,
        overdue_tasks=overdue_tasks,
        status_summary=status_summary,
    )

    response = await provider.chat(
        [
            ChatMessage(role="system", content=get_prompt("dashboard_analysis").system),
            ChatMessage(role="user", content=prompt),
        ],
        temperature=0.4,
    )

    parsed_model = validate_model(AIDashboardAnalysisOutput, parse_json_object(response.content))
    if parsed_model:
        parsed = parsed_model.model_dump()
    else:
        parsed = {
            "insights": [response.content[:200]],
            "recommendations": ["Review case statuses regularly"],
        }

    log_usage(
        db=db,
        organization_id=session.org_id,
        user_id=session.user_id,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        estimated_cost_usd=response.estimated_cost_usd,
    )

    return AnalyzeDashboardResponse(
        insights=parsed.get("insights", []),
        surrogate_volume_trend=trend,
        bottlenecks=bottlenecks,
        recommendations=parsed.get("recommendations", []),
        stats=stats,
    )
