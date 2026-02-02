"""
AI Email Template Generation Service.

Generates reusable email templates from natural language descriptions.
"""

from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services import ai_settings_service
from app.services.ai_prompt_registry import get_prompt
from app.services.ai_response_validation import parse_json_object, validate_model

logger = logging.getLogger(__name__)

VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

ALLOWED_TEMPLATE_VARIABLES = {
    "first_name",
    "full_name",
    "email",
    "phone",
    "surrogate_number",
    "intended_parent_number",
    "status_label",
    "owner_name",
    "org_name",
    "org_logo_url",
    "appointment_date",
    "appointment_time",
    "appointment_location",
    "unsubscribe_url",
}

REQUIRED_TEMPLATE_VARIABLES = {"unsubscribe_url"}


class EmailTemplateGenerationRequest(BaseModel):
    """Request to generate an email template from natural language."""

    description: str = Field(..., min_length=10, max_length=2000)


class GeneratedEmailTemplate(BaseModel):
    """AI-generated email template."""

    name: str
    subject: str
    body_html: str
    variables_used: list[str] = Field(default_factory=list)


class EmailTemplateGenerationResponse(BaseModel):
    """Response from email template generation."""

    success: bool
    template: GeneratedEmailTemplate | None = None
    explanation: str | None = None
    validation_errors: list[str] = []
    warnings: list[str] = []


def _extract_variables(text: str) -> list[str]:
    if not text:
        return []
    return list({match.group(1) for match in VARIABLE_PATTERN.finditer(text)})


def _validate_template(template: GeneratedEmailTemplate) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not template.name.strip():
        errors.append("Template name is required")
    if not template.subject.strip():
        errors.append("Template subject is required")

    subject_vars = _extract_variables(template.subject)
    body_vars = _extract_variables(template.body_html)
    variables_used = sorted(set(subject_vars + body_vars))

    missing_required = REQUIRED_TEMPLATE_VARIABLES - set(variables_used)
    if missing_required:
        missing_list = ", ".join(sorted(missing_required))
        errors.append(f"Missing required variables: {missing_list}")

    unknown_vars = set(variables_used) - ALLOWED_TEMPLATE_VARIABLES
    if unknown_vars:
        unknown_list = ", ".join(sorted(unknown_vars))
        errors.append(f"Unknown template variables: {unknown_list}")

    if not template.body_html.strip():
        errors.append("Template body_html is required")

    return errors, warnings, variables_used


def generate_email_template(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    description: str,
) -> EmailTemplateGenerationResponse:
    """Generate an email template from natural language description."""
    from app.services.ai_provider import ChatMessage

    settings = ai_settings_service.get_ai_settings(db, org_id)
    if not settings or not settings.is_enabled:
        return EmailTemplateGenerationResponse(
            success=False,
            explanation="AI is not enabled for this organization",
        )

    if ai_settings_service.is_consent_required(settings):
        return EmailTemplateGenerationResponse(
            success=False,
            explanation="AI consent not accepted",
        )

    provider = ai_settings_service.get_ai_provider_for_settings(settings, org_id, user_id=user_id)
    if not provider:
        message = (
            "Vertex AI configuration is incomplete"
            if settings.provider == "vertex_wif"
            else "AI API key not configured"
        )
        return EmailTemplateGenerationResponse(success=False, explanation=message)

    prompt_template = get_prompt("email_template_generation")
    allowed_vars = ", ".join(sorted(ALLOWED_TEMPLATE_VARIABLES))
    prompt = prompt_template.render_user(
        user_input=description,
        allowed_variables=allowed_vars,
    )

    try:
        from app.core.async_utils import run_async

        async def _run_chat():
            return await provider.chat(
                [
                    ChatMessage(role="system", content=prompt_template.system),
                    ChatMessage(role="user", content=prompt),
                ],
                temperature=0.3,
            )

        response = run_async(_run_chat())
        template_data = parse_json_object(response.content)
        template_model = validate_model(GeneratedEmailTemplate, template_data)
        if not template_model:
            raise json.JSONDecodeError("Invalid email template JSON", response.content, 0)

        errors, warnings, variables_used = _validate_template(template_model)
        template_model.variables_used = variables_used

        if errors:
            return EmailTemplateGenerationResponse(
                success=False,
                template=template_model,
                explanation="Generated template has validation errors",
                validation_errors=errors,
                warnings=warnings,
            )

        return EmailTemplateGenerationResponse(
            success=True,
            template=template_model,
            explanation="Template generated successfully. Please review before saving.",
            warnings=warnings,
        )

    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse AI email template response: {exc}")
        return EmailTemplateGenerationResponse(
            success=False,
            explanation=f"Failed to parse AI response as JSON: {str(exc)}",
        )
    except Exception as exc:
        logger.error(f"Email template generation error: {exc}")
        return EmailTemplateGenerationResponse(
            success=False,
            explanation=f"Error generating email template: {str(exc)}",
        )
