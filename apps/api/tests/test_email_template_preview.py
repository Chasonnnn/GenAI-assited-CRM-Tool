"""Email template previews render through the send composition (ADR 0006)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.db.enums import SurrogateSource
from app.db.models import Organization, UnsubscribeToken
from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service


def _token_count(db) -> int:
    return db.scalar(select(func.count()).select_from(UnsubscribeToken))


def _surrogate(db, org_id, user_id, *, name="Ashley Nicole Harden", email="ashley@example.com"):
    return surrogate_service.create_surrogate(
        db,
        org_id,
        user_id,
        SurrogateCreate(full_name=name, email=email, source=SurrogateSource.MANUAL),
    )


@pytest.mark.asyncio
async def test_sample_preview_composes_footer_without_writing_tokens(authed_client, db):
    before = _token_count(db)

    response = await authed_client.post(
        "/email-templates/preview",
        json={
            "subject": "Hi {{first_name}}",
            "body": (
                "<p>Hello {{first_name}} from {{org_name}} {{mystery}}</p>"
                '<p><a href="{{unsubscribe_url}}">Old unsubscribe</a></p>'
                "<script>alert(1)</script>"
            ),
            "scope": "org",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subject"] == "Hi Jordan"
    assert data["unresolved_variables"] == ["mystery"]
    html = data["html"]
    assert html.startswith("<!doctype html>")
    assert "Content-Security-Policy" in html
    assert "default-src &#x27;none&#x27;" not in html
    assert "default-src 'none'" in html
    assert "Hello Jordan from" in html
    assert "TEST_MYSTERY" in html
    assert "Old unsubscribe" not in html
    assert "<script" not in html
    assert 'href="#unsubscribe"' in html
    assert _token_count(db) == before


@pytest.mark.asyncio
async def test_names_preview_keeps_variable_names(authed_client):
    response = await authed_client.post(
        "/email-templates/preview",
        json={
            "subject": "Hi {{first_name}}",
            "body": "<p>{{first_name}} {{mystery}}</p>",
            "scope": "personal",
            "variable_mode": "names",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subject"] == "Hi {{first_name}}"
    assert "<p>{{first_name}} {{mystery}}</p>" in data["html"]
    assert data["unresolved_variables"] == ["mystery"]


@pytest.mark.asyncio
async def test_record_preview_uses_the_surrogate_variables(authed_client, db, test_org, test_user):
    surrogate = _surrogate(db, test_org.id, test_user.id)
    before = _token_count(db)

    response = await authed_client.post(
        "/email-templates/preview",
        json={
            "subject": "Hi {{first_name}}",
            "body": "<p>{{full_name}} {{email}}</p>",
            "variable_mode": "record",
            "surrogate_id": str(surrogate.id),
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subject"] == "Hi Ashley"
    assert "Ashley Nicole Harden ashley@example.com" in data["html"]
    assert data["unresolved_variables"] == []
    assert _token_count(db) == before


@pytest.mark.asyncio
async def test_record_preview_requires_a_surrogate(authed_client):
    response = await authed_client.post(
        "/email-templates/preview",
        json={"subject": "Hi", "body": "<p>x</p>", "variable_mode": "record"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_record_preview_rejects_other_org_surrogates(authed_client, db, test_user):
    other_org = Organization(
        id=uuid.uuid4(), name="Other preview org", slug=f"other-{uuid.uuid4().hex}"
    )
    db.add(other_org)
    db.flush()
    other = _surrogate(
        db, other_org.id, test_user.id, name="Other Person", email="other@example.com"
    )

    response = await authed_client.post(
        "/email-templates/preview",
        json={
            "subject": "Hi {{first_name}}",
            "body": "<p>{{full_name}}</p>",
            "variable_mode": "record",
            "surrogate_id": str(other.id),
        },
    )

    assert response.status_code == 404
    assert "Other Person" not in response.text


@pytest.mark.asyncio
async def test_preview_requires_csrf(authed_client):
    response = await authed_client.post(
        "/email-templates/preview",
        json={"subject": "Hi", "body": "<p>x</p>"},
        headers={"X-CSRF-Token": ""},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_platform_previews_require_platform_admin(authed_client):
    for path in ("/platform/templates/email/preview", "/platform/email/system-templates/preview"):
        response = await authed_client.post(path, json={"subject": "Hi", "body": "<p>x</p>"})
        assert response.status_code == 403, path


@pytest.mark.asyncio
async def test_platform_library_preview_renders_without_footer(authed_client, db, test_user):
    test_user.is_platform_admin = True
    db.commit()
    before = _token_count(db)

    response = await authed_client.post(
        "/platform/templates/email/preview",
        json={"subject": "Welcome to {{org_name}}", "body": "<p>Hello {{full_name}}</p>"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subject"] == "Welcome to Example Agency"
    assert "Hello Jordan Smith" in data["html"]
    assert "Unsubscribe" not in data["html"]
    assert _token_count(db) == before


@pytest.mark.asyncio
async def test_system_preview_renders_html_blocks_for_an_org(
    authed_client, db, test_org, test_user
):
    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.post(
        "/platform/email/system-templates/preview",
        json={
            "subject": "Join {{org_name}}",
            "body": "<div>{{expires_block}}</div><p>{{role_title}}</p><div>{{body_block}}{{link_block}}</div>",
            "org_id": str(test_org.id),
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subject"] == f"Join {test_org.name}"
    assert "<div><p>This is a test email." in data["html"]
    assert "<p>Admin</p>" in data["html"]
    assert "<div><p>This is a test email. Notification details" in data["html"]
    assert "Open in Surrogacy Force</a>" in data["html"]

    missing = await authed_client.post(
        "/platform/email/system-templates/preview",
        json={"subject": "Hi", "body": "<p>x</p>", "org_id": str(uuid.uuid4())},
    )
    assert missing.status_code == 404
