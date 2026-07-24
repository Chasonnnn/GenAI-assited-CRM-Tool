"""Test-send endpoint for isolated email template drafts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.routers.email_template_drafts import _require_draft_editor
from app.schemas.email_template_drafts import (
    EmailTemplateDraftTestSendRequest,
    EmailTemplateDraftTestSendResponse,
)
from app.services import email_template_draft_service


router = APIRouter(
    prefix="/email-template-drafts",
    tags=["Email Template Drafts"],
    dependencies=[Depends(require_permission(POLICIES["email_templates"].default))],
)


@router.post(
    "/{draft_id}/test",
    response_model=EmailTemplateDraftTestSendResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def send_email_template_draft_test(
    draft_id: UUID,
    body: EmailTemplateDraftTestSendRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
) -> EmailTemplateDraftTestSendResponse:
    draft = email_template_draft_service.get_draft(
        db,
        org_id=session.org_id,
        draft_id=draft_id,
        for_update=True,
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    _require_draft_editor(db, session, draft)
    if draft.revision != body.expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Draft revision mismatch: "
                f"expected {body.expected_revision}, got {draft.revision}"
            ),
        )

    if draft.template is not None and draft.template.system_key:
        from app.services import system_email_template_service

        if (
            draft.template.system_key
            in system_email_template_service.DEFAULT_SYSTEM_TEMPLATES
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Platform system template '{draft.template.system_key}' "
                    "cannot be test-sent from organization Studio"
                ),
            )

    from app.services import email_test_send_service

    tested_revision = draft.revision
    result = await email_test_send_service.send_template_content_test(
        db=db,
        org_id=session.org_id,
        actor_user_id=session.user_id,
        actor_display_name=session.display_name,
        scope=draft.scope,
        subject_template=draft.subject,
        body_template=draft.body,
        template_from_email=draft.from_email,
        template_id=draft.template_id,
        to_email=str(body.to_email),
        variables=body.variables,
        idempotency_key=body.idempotency_key,
        ignore_opt_out=body.ignore_opt_out,
    )
    if result.get("success"):
        email_template_draft_service.record_successful_test(
            db,
            org_id=session.org_id,
            draft_id=draft.id,
            tested_revision=tested_revision,
        )
    return EmailTemplateDraftTestSendResponse(
        **result,
        tested_revision=tested_revision,
    )
