"""AI consent routes."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession

router = APIRouter()

CONSENT_TEXT = """
By enabling the AI Assistant, you acknowledge that:

1. Surrogate data (names, contact info, notes) will be sent to a third-party AI provider 
   (OpenAI or Google Gemini) for processing.

2. If "Anonymize PII" is enabled (default), personal identifiers will be stripped 
   before sending to the AI and restored in responses.

3. Data sent to AI providers is subject to their data processing policies. 
   OpenAI and Google do not train on API data.

4. AI responses are suggestions only. Staff must verify accuracy before acting.

5. A usage log tracks all AI interactions for compliance and auditing.
""".strip()


class ConsentResponse(BaseModel):
    """Consent info."""

    consent_text: str
    consent_accepted_at: str | None
    consent_accepted_by: str | None


@router.get("/consent", response_model=ConsentResponse)
def get_consent(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> ConsentResponse:
    """Get consent text and status."""
    from app.services import ai_settings_service

    settings = ai_settings_service.get_or_create_ai_settings(db, session.org_id, session.user_id)

    return ConsentResponse(
        consent_text=CONSENT_TEXT,
        consent_accepted_at=settings.consent_accepted_at.isoformat()
        if settings.consent_accepted_at
        else None,
        consent_accepted_by=str(settings.consent_accepted_by)
        if settings.consent_accepted_by
        else None,
    )


@router.post("/consent/accept", dependencies=[Depends(require_csrf_header)])
def accept_consent(
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> dict[str, str | bool | None]:
    """Accept the AI data processing consent."""
    from app.services import ai_settings_service, audit_service

    settings = ai_settings_service.accept_consent(db, session.org_id, session.user_id)
    audit_service.log_consent_accepted(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        request=request,
    )
    db.commit()

    return {
        "accepted": True,
        "accepted_at": settings.consent_accepted_at.isoformat()
        if settings.consent_accepted_at
        else None,
        "accepted_by": str(settings.consent_accepted_by) if settings.consent_accepted_by else None,
    }
