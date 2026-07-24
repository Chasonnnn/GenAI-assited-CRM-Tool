from __future__ import annotations

import uuid

import pytest

from app.db.models import EmailDelivery, EmailLog, EmailTemplate
from app.services import (
    email_service,
    resend_settings_service,
    resend_transport,
)


@pytest.mark.asyncio
async def test_test_send_renders_the_saved_draft_without_publishing_it(
    authed_client,
    db,
    test_org,
    test_user,
    monkeypatch,
):
    resend_settings_service.update_resend_settings(
        db,
        test_org.id,
        test_user.id,
        email_provider="resend",
        api_key="re_test_key",
        from_email="no-reply@example.com",
        from_name="Test Org",
    )
    template = email_service.create_template(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Draft test",
        subject="Published subject",
        body="<p>Published body</p>",
        scope="org",
    )
    draft_response = await authed_client.post(
        f"/email-template-drafts/from-template/{template.id}"
    )
    draft = draft_response.json()
    update_response = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={
            "subject": "Draft subject for {{full_name}}",
            "body": "<p>Draft body for {{full_name}}</p>",
            "expected_revision": 1,
        },
    )
    assert update_response.status_code == 200

    async def fail_provider_io(**_kwargs):
        raise AssertionError("draft test send must only enqueue")

    monkeypatch.setattr(resend_transport, "send_email", fail_provider_io)

    test_response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/test",
        json={
            "to_email": "draft-recipient@example.com",
            "variables": {"full_name": "Avery"},
            "idempotency_key": f"template-draft-test/{uuid.uuid4()}",
            "expected_revision": 2,
        },
    )
    assert test_response.status_code == 200
    result = test_response.json()
    assert result["success"] is True
    assert result["queued"] is True
    assert result["provider_used"] == "resend"
    assert result["tested_revision"] == 2

    log = db.get(EmailLog, uuid.UUID(result["email_log_id"]))
    assert log is not None
    assert log.template_id == template.id
    assert log.subject == "Draft subject for Avery"
    assert "Draft body for Avery" in log.body
    assert "Published body" not in log.body
    delivery = db.query(EmailDelivery).filter(EmailDelivery.email_log_id == log.id).one()
    assert delivery.status == "pending"

    db.expire_all()
    still_published = db.get(EmailTemplate, template.id)
    assert still_published is not None
    assert still_published.subject == "Published subject"
    assert still_published.body == "<p>Published body</p>"

    tested_draft = await authed_client.get(f"/email-template-drafts/{draft['id']}")
    assert tested_draft.status_code == 200
    assert tested_draft.json()["revision"] == 2
    assert tested_draft.json()["last_tested_revision"] == 2
    assert tested_draft.json()["last_tested_at"] is not None

    changed_after_test = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={
            "subject": "Changed after test",
            "expected_revision": 2,
        },
    )
    assert changed_after_test.status_code == 200
    assert changed_after_test.json()["revision"] == 3
    assert changed_after_test.json()["last_tested_revision"] == 2

    log_count_before_stale_test = db.query(EmailLog).count()
    stale_test_response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/test",
        json={
            "to_email": "draft-recipient@example.com",
            "idempotency_key": f"template-draft-test/{uuid.uuid4()}",
            "expected_revision": 2,
        },
    )
    assert stale_test_response.status_code == 409
    assert db.query(EmailLog).count() == log_count_before_stale_test
