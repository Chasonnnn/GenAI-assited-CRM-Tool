"""React Email editor documents stored beside template bodies (ADR 0006)."""

from __future__ import annotations

import pytest

from app.db.models import EmailTemplate, PlatformEmailTemplate
from app.services import email_service, version_service

DESIGN = {
    "type": "doc",
    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hi {{first_name}}"}]}],
}
OTHER_DESIGN = {
    "type": "doc",
    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Updated"}]}],
}


def _payload(db, template: EmailTemplate, version: int) -> dict:
    row = version_service.get_version(
        db, template.organization_id, email_service.ENTITY_TYPE, template.id, version
    )
    assert row is not None
    return version_service.decrypt_payload(row.payload_encrypted)


@pytest.mark.asyncio
async def test_create_and_read_return_the_design_with_its_body(authed_client, db):
    response = await authed_client.post(
        "/email-templates",
        json={
            "name": "Designed welcome",
            "subject": "Welcome",
            "body": "<p>Hi {{first_name}}</p>",
            "body_design": DESIGN,
            "scope": "org",
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["body_design"] == DESIGN

    read = await authed_client.get(f"/email-templates/{created['id']}")
    assert read.status_code == 200
    assert read.json()["body_design"] == DESIGN

    template = db.get(EmailTemplate, created["id"])
    assert _payload(db, template, 1)["body_design"] == DESIGN


@pytest.mark.asyncio
async def test_body_without_design_clears_the_stored_design(authed_client, db, test_org, test_user):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Designed update",
        subject="Subject",
        body="<p>Hi {{first_name}}</p>",
        body_design=DESIGN,
    )

    response = await authed_client.patch(
        f"/email-templates/{template.id}",
        json={"body": "<p>Raw HTML edit</p>", "expected_version": template.current_version},
    )
    assert response.status_code == 200, response.text
    assert response.json()["body_design"] is None
    db.expire_all()
    stored = db.get(EmailTemplate, template.id)
    assert stored.body_design is None
    assert "body_design" not in _payload(db, stored, stored.current_version)


@pytest.mark.asyncio
async def test_subject_only_update_keeps_the_design(authed_client, db, test_org, test_user):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Designed subject",
        subject="Subject",
        body="<p>Hi</p>",
        body_design=DESIGN,
    )

    response = await authed_client.patch(
        f"/email-templates/{template.id}",
        json={"subject": "New subject", "expected_version": template.current_version},
    )
    assert response.status_code == 200, response.text
    assert response.json()["body_design"] == DESIGN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"body_design": DESIGN},
        {"body": "<p>x</p>", "body_design": {"type": "paragraph"}},
        {"body": "<p>x</p>", "body_design": {"type": "doc", "content": "not a list"}},
        {
            "body": "<p>x</p>",
            "body_design": {
                "type": "doc",
                "content": [{"type": "text", "text": "x" * 500_001}],
            },
        },
    ],
)
async def test_invalid_design_updates_are_rejected(authed_client, db, test_org, test_user, payload):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Rejects bad designs",
        subject="Subject",
        body="<p>Hi</p>",
    )

    response = await authed_client.patch(
        f"/email-templates/{template.id}",
        json={**payload, "expected_version": template.current_version},
    )
    assert response.status_code == 422
    db.expire_all()
    assert db.get(EmailTemplate, template.id).body_design is None


@pytest.mark.asyncio
async def test_legacy_template_publishes_a_design_through_a_draft(
    authed_client, db, test_org, test_user
):
    # Legacy rows have no design and history recorded before ADR 0006.
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Legacy welcome",
        subject="Subject",
        body="<p>Legacy body</p>",
    )
    legacy_payload = _payload(db, template, 1)
    assert "body_design" not in legacy_payload

    draft = (await authed_client.post(f"/email-template-drafts/from-template/{template.id}")).json()
    assert draft["body_design"] is None

    update = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={"body": "<p>Converted body</p>", "body_design": DESIGN, "expected_revision": 1},
    )
    assert update.status_code == 200, update.text
    assert update.json()["body_design"] == DESIGN

    publish = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={"expected_revision": 2, "expected_published_version": 1},
    )
    assert publish.status_code == 200, publish.text
    assert publish.json()["body_design"] == DESIGN

    db.expire_all()
    stored = db.get(EmailTemplate, template.id)
    assert stored.current_version == 2
    assert _payload(db, stored, 2)["body_design"] == DESIGN

    # Restoring the legacy version brings back the original body without a design.
    reopened = (
        await authed_client.post(f"/email-template-drafts/from-template/{template.id}")
    ).json()
    restored = await authed_client.post(
        f"/email-template-drafts/{reopened['id']}/restore-version",
        json={"target_version": 1, "expected_revision": 1},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["body"] == "<p>Legacy body</p>"
    assert restored.json()["body_design"] is None


@pytest.mark.asyncio
async def test_design_only_change_publishes_with_its_body(authed_client, db, test_org, test_user):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Design only",
        subject="Subject",
        body="<p>Same body</p>",
        body_design=DESIGN,
    )
    draft = (await authed_client.post(f"/email-template-drafts/from-template/{template.id}")).json()
    assert draft["body_design"] == DESIGN

    await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={"body": "<p>Same body</p>", "body_design": OTHER_DESIGN, "expected_revision": 1},
    )
    publish = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/publish",
        json={"expected_revision": 2, "expected_published_version": 1},
    )
    assert publish.status_code == 200, publish.text
    assert publish.json()["body_design"] == OTHER_DESIGN
    assert publish.json()["current_version"] == 2


@pytest.mark.asyncio
async def test_rollback_restores_the_versioned_design(authed_client, db, test_org, test_user):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Rollback design",
        subject="Subject",
        body="<p>First</p>",
        body_design=DESIGN,
    )
    email_service.update_template(db, template, test_user.id, body="<p>Raw</p>")
    db.refresh(template)
    assert template.body_design is None

    response = await authed_client.post(
        f"/email-templates/{template.id}/rollback", json={"target_version": 1}
    )
    assert response.status_code == 200, response.text
    assert response.json()["body_design"] == DESIGN


@pytest.mark.asyncio
async def test_copy_to_personal_carries_the_design(authed_client, db, test_org, test_user):
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Shared design",
        subject="Subject",
        body="<p>Hi</p>",
        body_design=DESIGN,
    )

    response = await authed_client.post(
        f"/email-templates/{template.id}/copy", json={"name": "My shared design"}
    )
    assert response.status_code in (200, 201), response.text
    assert response.json()["body_design"] == DESIGN


@pytest.mark.asyncio
async def test_platform_email_patch_with_body_only_clears_design(authed_client, db, test_user):
    test_user.is_platform_admin = True
    db.commit()

    created = await authed_client.post(
        "/platform/templates/email",
        json={
            "name": "Ops designed",
            "subject": "Welcome to {{org_name}}",
            "body": "<p>Hello {{full_name}}</p>",
            "body_design": DESIGN,
            "category": "invite",
        },
    )
    assert created.status_code == 201, created.text
    template = created.json()
    assert template["draft"]["body_design"] == DESIGN

    subject_only = await authed_client.patch(
        f"/platform/templates/email/{template['id']}",
        json={"subject": "Hello {{org_name}}", "expected_version": template["current_version"]},
    )
    assert subject_only.status_code == 200, subject_only.text
    assert subject_only.json()["draft"]["body_design"] == DESIGN

    body_only = await authed_client.patch(
        f"/platform/templates/email/{template['id']}",
        json={
            "body": "<p>Raw {{full_name}}</p>",
            "expected_version": subject_only.json()["current_version"],
        },
    )
    assert body_only.status_code == 200, body_only.text
    assert body_only.json()["draft"]["body_design"] is None
    db.expire_all()
    assert db.get(PlatformEmailTemplate, template["id"]).body_design is None


@pytest.mark.asyncio
async def test_system_template_update_stores_or_clears_design(authed_client, db, test_user):
    from app.services import system_email_template_service

    test_user.is_platform_admin = True
    db.commit()
    tpl = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )
    db.commit()

    designed = await authed_client.put(
        "/platform/email/system-templates/org_invite",
        json={
            "subject": "Invite: {{org_name}}",
            "body": "<p>Hello {{org_name}}</p>",
            "body_design": DESIGN,
            "is_active": True,
            "expected_version": tpl.current_version,
        },
    )
    assert designed.status_code == 200, designed.text
    assert designed.json()["body_design"] == DESIGN

    raw = await authed_client.put(
        "/platform/email/system-templates/org_invite",
        json={
            "subject": "Invite: {{org_name}}",
            "body": "<p>Raw {{org_name}}</p>",
            "is_active": True,
            "expected_version": designed.json()["current_version"],
        },
    )
    assert raw.status_code == 200, raw.text
    assert raw.json()["body_design"] is None
