"""Email layouts stored on templates and drafts, snapshotted for delayed sends."""

from __future__ import annotations

import uuid

import pytest

from app.core.email_layout import EmailLayout
from app.db.models import EmailTemplate, Organization
from app.services import email_service, media_service, version_service
from app.services.email_template_snapshot import (
    EmailTemplateSnapshotError,
    build_snapshot,
    parse_snapshot,
)

LETTERHEAD = {
    "kind": "letterhead",
    "show_logo": True,
    "logo_position": "left",
    "accent_color": "#0f766e",
    "page_background": "#f4f4f5",
}
S3_LOGO = "https://crm-attachments.s3.amazonaws.com/logos/org/logo.png"


def _payload(db, template: EmailTemplate, version: int) -> dict:
    row = version_service.get_version(
        db, template.organization_id, email_service.ENTITY_TYPE, template.id, version
    )
    assert row is not None
    return version_service.decrypt_payload(row.payload_encrypted)


def _template(db, org, user, *, name="Layout template", layout=None) -> EmailTemplate:
    return email_service.create_template(
        db,
        org_id=org.id,
        user_id=user.id,
        name=name,
        subject="Subject",
        body="<p>Hi</p>",
        layout=layout,
    )


@pytest.mark.asyncio
async def test_create_and_read_return_the_layout(authed_client, db):
    response = await authed_client.post(
        "/email-templates",
        json={
            "name": "Letterhead welcome",
            "subject": "Welcome",
            "body": "<p>Hi</p>",
            "layout": {"kind": "letterhead", "logo_position": "left", "accent_color": "#0f766e"},
            "scope": "org",
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["layout"] == LETTERHEAD

    read = await authed_client.get(f"/email-templates/{created['id']}")
    assert read.json()["layout"] == LETTERHEAD
    assert _payload(db, db.get(EmailTemplate, created["id"]), 1)["layout"] == LETTERHEAD


@pytest.mark.asyncio
async def test_templates_without_a_layout_keep_null_and_the_old_version_shape(
    authed_client, db, test_org, test_user
):
    template = _template(db, test_org, test_user)

    read = await authed_client.get(f"/email-templates/{template.id}")
    assert read.json()["layout"] is None
    assert "layout" not in _payload(db, template, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "layout",
    [
        {"kind": "banner"},
        {"kind": "card", "page_background": "grey"},
        {"kind": "letterhead", "accent_color": "#12345"},
        {"kind": "card", "logo_position": "right"},
        {"kind": "card", "script": "<x>"},
        "card",
    ],
)
async def test_invalid_layouts_are_rejected(authed_client, db, test_org, test_user, layout):
    template = _template(db, test_org, test_user, name="Rejects bad layouts")

    response = await authed_client.patch(
        f"/email-templates/{template.id}",
        json={"layout": layout, "expected_version": template.current_version},
    )
    assert response.status_code == 422
    db.expire_all()
    assert db.get(EmailTemplate, template.id).layout is None


@pytest.mark.asyncio
async def test_draft_layout_publishes_and_restores_with_history(
    authed_client, db, test_org, test_user
):
    template = _template(db, test_org, test_user, name="Draft layout")
    draft = (await authed_client.post(f"/email-template-drafts/from-template/{template.id}")).json()
    assert draft["layout"] is None

    update = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={"layout": LETTERHEAD, "expected_revision": 1},
    )
    assert update.status_code == 200, update.text
    assert update.json()["layout"] == LETTERHEAD

    publish = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={"expected_revision": 2, "expected_published_version": 1},
    )
    assert publish.status_code == 200, publish.text
    assert publish.json()["layout"] == LETTERHEAD
    assert publish.json()["current_version"] == 2

    db.expire_all()
    stored = db.get(EmailTemplate, template.id)
    assert _payload(db, stored, 2)["layout"] == LETTERHEAD

    # Version 1 predates the layout, so restoring it brings back the scope default.
    reopened = (
        await authed_client.post(f"/email-template-drafts/from-template/{template.id}")
    ).json()
    assert reopened["layout"] == LETTERHEAD
    restored = await authed_client.post(
        f"/email-template-drafts/{reopened['id']}/restore-version",
        json={"target_version": 1, "expected_revision": 1},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["layout"] is None


@pytest.mark.asyncio
async def test_rollback_and_copy_carry_the_layout(authed_client, db, test_org, test_user):
    template = _template(db, test_org, test_user, name="Rollback layout", layout=LETTERHEAD)
    email_service.update_template(db, template, test_user.id, layout=None)
    db.refresh(template)
    assert template.layout is None

    rollback = await authed_client.post(
        f"/email-templates/{template.id}/rollback", json={"target_version": 1}
    )
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["layout"] == LETTERHEAD

    copy = await authed_client.post(
        f"/email-templates/{template.id}/copy", json={"name": "My letterhead"}
    )
    assert copy.status_code in (200, 201), copy.text
    assert copy.json()["layout"] == LETTERHEAD


def test_snapshots_pin_the_layout(db, test_org, test_user):
    template = _template(db, test_org, test_user, name="Snapshot layout", layout=LETTERHEAD)

    payload = build_snapshot(template, effective_from_email=None)

    assert payload["layout"] == LETTERHEAD
    assert parse_snapshot(payload).layout == EmailLayout(**LETTERHEAD)


def test_snapshots_from_before_layouts_use_the_scope_default(db, test_org, test_user):
    template = _template(db, test_org, test_user, name="Old snapshot")
    payload = build_snapshot(template, effective_from_email=None)
    payload.pop("layout")

    assert parse_snapshot(payload).layout is None


def test_snapshots_with_a_malformed_layout_are_rejected(db, test_org, test_user):
    template = _template(db, test_org, test_user, name="Bad snapshot")
    payload = build_snapshot(template, effective_from_email=None)
    payload["layout"] = {"kind": "banner"}

    with pytest.raises(EmailTemplateSnapshotError):
        parse_snapshot(payload)


@pytest.mark.asyncio
async def test_preview_renders_the_requested_layout(authed_client):
    response = await authed_client.post(
        "/email-templates/preview",
        json={
            "subject": "Hi",
            "body": "<p>Hello</p>",
            "scope": "org",
            "layout": {"kind": "card", "page_background": "#e0f2fe"},
        },
    )
    assert response.status_code == 200, response.text
    assert 'bgcolor="#e0f2fe"' in response.json()["html"]

    plain = await authed_client.post(
        "/email-templates/preview",
        json={"subject": "Hi", "body": "<p>Hello</p>", "scope": "org", "layout": {"kind": "plain"}},
    )
    assert "#f4f4f5" not in plain.json()["html"]


@pytest.mark.asyncio
async def test_layout_frame_uses_the_session_org_and_scope_defaults(
    authed_client, db, test_org, test_user, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "S3_BUCKET", "crm-attachments", raising=False)
    test_org.signature_logo_url = S3_LOGO
    test_org.signature_company_name = "Smith & Co"
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other org",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
        signature_logo_url="https://crm-attachments.s3.amazonaws.com/logos/other/logo.png",
    )
    db.add(other_org)
    db.commit()

    org_frame = await authed_client.post("/email-templates/layout-frame", json={"scope": "org"})
    assert org_frame.status_code == 200, org_frame.text
    data = org_frame.json()
    assert data["layout"]["kind"] == "card"
    assert data["logo_url"] == media_service.email_logo_url(test_org)
    assert data["logo_alt"] == "Smith & Co"
    assert str(other_org.id) not in org_frame.text
    # The layout shows the logo, so the org signature leaves it out.
    assert data["logo_url"] not in data["signature_html"]
    assert 'href="#unsubscribe"' in data["footer_html"]

    personal = await authed_client.post("/email-templates/layout-frame", json={"scope": "personal"})
    data = personal.json()
    assert data["layout"]["kind"] == "plain"
    assert data["logo_url"] is None
    assert test_user.email in data["signature_html"]
    assert str(other_org.id) not in personal.text


@pytest.mark.asyncio
async def test_layout_frame_requires_csrf(authed_client):
    from app.core.csrf import CSRF_HEADER

    response = await authed_client.post(
        "/email-templates/layout-frame",
        json={"scope": "org"},
        headers={CSRF_HEADER: "wrong-token"},
    )
    assert response.status_code == 403
