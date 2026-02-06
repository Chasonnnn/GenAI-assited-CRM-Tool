"""
Tests for AI email template generation.
"""

import json
from datetime import datetime, timezone

from app.db.models import AISettings
from app.services import ai_settings_service
from app.services.ai_provider import ChatResponse


def _enable_ai(db, org_id, user_id) -> AISettings:
    settings = AISettings(
        organization_id=org_id,
        is_enabled=True,
        provider="gemini",
        model="gemini-3-flash-preview",
        current_version=1,
        anonymize_pii=False,
        consent_accepted_at=datetime.now(timezone.utc),
        consent_accepted_by=user_id,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
    )
    db.add(settings)
    db.flush()
    return settings


def test_generate_email_template_does_not_require_unsubscribe(db, test_org, test_user, monkeypatch):
    _enable_ai(db, test_org.id, test_user.id)

    payload = {
        "name": "Follow Up",
        "subject": "Hi {{first_name}}",
        "body_html": "<p>Just checking in.</p>",
        "variables_used": ["first_name"],
    }

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            return ChatResponse(
                content=json.dumps(payload),
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    from app.services import ai_email_template_service

    result = ai_email_template_service.generate_email_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        description="Draft a follow-up email",
    )

    assert result.success is True
    assert result.template is not None
    assert "first_name" in result.template.variables_used


def test_generate_email_template_errors_on_unknown_variables(db, test_org, test_user, monkeypatch):
    _enable_ai(db, test_org.id, test_user.id)

    payload = {
        "name": "Update",
        "subject": "Status update",
        "body_html": "<p>Hello {{full_name}}</p><p>{{unknown_var}}</p><p>{{unsubscribe_url}}</p>",
        "variables_used": ["full_name", "unknown_var", "unsubscribe_url"],
    }

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            return ChatResponse(
                content=json.dumps(payload),
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    from app.services import ai_email_template_service

    result = ai_email_template_service.generate_email_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        description="Status update email",
    )

    assert result.success is False
    assert any("unknown" in e.lower() for e in result.validation_errors)
    assert result.template is not None
    assert "unknown_var" in result.template.variables_used
    assert "unsubscribe_url" in result.template.variables_used


def test_generate_email_template_extracts_variables_from_body(db, test_org, test_user, monkeypatch):
    _enable_ai(db, test_org.id, test_user.id)

    payload = {
        "name": "Welcome",
        "subject": "Welcome {{first_name}}",
        "body_html": "<p>Hi {{first_name}}</p>",
        "variables_used": [],
    }

    class StubProvider:
        async def chat(self, messages, **kwargs):  # noqa: ARG002
            return ChatResponse(
                content=json.dumps(payload),
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                model="gemini-3-flash-preview",
            )

    monkeypatch.setattr(
        "app.services.ai_provider.get_provider",
        lambda *_args, **_kwargs: StubProvider(),
    )

    from app.services import ai_email_template_service

    result = ai_email_template_service.generate_email_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        description="Welcome email",
    )

    assert result.success is True
    assert result.template is not None
    assert "first_name" in result.template.variables_used
