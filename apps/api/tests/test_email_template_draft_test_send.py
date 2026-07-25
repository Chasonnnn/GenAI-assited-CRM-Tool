from __future__ import annotations

import uuid

import pytest

from app.db.models import EmailDelivery, EmailLog, EmailTemplate, EmailTemplateDraft
from app.services import (
    email_service,
    gmail_service,
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
    draft_response = await authed_client.post(f"/email-template-drafts/from-template/{template.id}")
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
    assert result["submitted_revision"] == 2
    assert result["tested_revision"] is None

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
    assert tested_draft.json()["last_tested_revision"] is None
    assert tested_draft.json()["last_tested_at"] is None

    changed_after_test = await authed_client.patch(
        f"/email-template-drafts/{draft['id']}",
        json={
            "subject": "Changed after test",
            "expected_revision": 2,
        },
    )
    assert changed_after_test.status_code == 200
    assert changed_after_test.json()["revision"] == 3
    assert changed_after_test.json()["last_tested_revision"] is None

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


@pytest.mark.asyncio
async def test_synchronous_test_send_does_not_claim_a_concurrently_edited_revision(
    authed_client,
    db,
    monkeypatch,
):
    draft_response = await authed_client.post(
        "/email-template-drafts",
        json={
            "name": "Concurrent personal draft",
            "subject": "Original draft subject",
            "body": "<p>Original draft body</p>",
            "scope": "personal",
        },
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()

    async def send_after_concurrent_edit(*, db, **_kwargs):
        changed_draft = db.get(EmailTemplateDraft, uuid.UUID(draft["id"]))
        assert changed_draft is not None
        changed_draft.subject = "Edited while Gmail was sending"
        changed_draft.revision += 1
        db.commit()
        return {
            "success": True,
            "message_id": "gmail_concurrent_success",
            "email_log_id": str(uuid.uuid4()),
        }

    monkeypatch.setattr(gmail_service, "send_email_logged", send_after_concurrent_edit)

    response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/test",
        json={
            "to_email": "draft-recipient@example.com",
            "idempotency_key": f"template-draft-test/{uuid.uuid4()}",
            "expected_revision": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["submitted_revision"] == 1
    assert response.json()["tested_revision"] is None

    db.expire_all()
    changed_draft = db.get(EmailTemplateDraft, uuid.UUID(draft["id"]))
    assert changed_draft is not None
    assert changed_draft.revision == 2
    assert changed_draft.last_tested_revision is None
    assert changed_draft.last_tested_at is None


@pytest.mark.asyncio
async def test_synchronous_test_send_records_and_reports_the_submitted_revision(
    authed_client,
    db,
    monkeypatch,
):
    draft_response = await authed_client.post(
        "/email-template-drafts",
        json={
            "name": "Successful personal draft",
            "subject": "Personal draft subject",
            "body": "<p>Personal draft body</p>",
            "scope": "personal",
        },
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()

    async def successful_send(**_kwargs):
        return {
            "success": True,
            "message_id": "gmail_sync_success",
            "email_log_id": str(uuid.uuid4()),
        }

    monkeypatch.setattr(gmail_service, "send_email_logged", successful_send)

    response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/test",
        json={
            "to_email": "draft-recipient@example.com",
            "idempotency_key": f"template-draft-test/{uuid.uuid4()}",
            "expected_revision": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["queued"] is False
    assert result["provider_used"] == "gmail"
    assert result["submitted_revision"] == 1
    assert result["tested_revision"] == 1

    db.expire_all()
    tested_draft = db.get(EmailTemplateDraft, uuid.UUID(draft["id"]))
    assert tested_draft is not None
    assert tested_draft.revision == 1
    assert tested_draft.last_tested_revision == 1
    assert tested_draft.last_tested_at is not None


@pytest.mark.asyncio
async def test_failed_synchronous_test_send_does_not_mark_the_revision_tested(
    authed_client,
    db,
    monkeypatch,
):
    draft_response = await authed_client.post(
        "/email-template-drafts",
        json={
            "name": "Failed personal draft",
            "subject": "Personal draft subject",
            "body": "<p>Personal draft body</p>",
            "scope": "personal",
        },
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()

    async def failed_send(**_kwargs):
        return {
            "success": False,
            "message_id": None,
            "email_log_id": None,
            "error": "Gmail rejected the test send",
        }

    monkeypatch.setattr(gmail_service, "send_email_logged", failed_send)

    response = await authed_client.post(
        f"/email-template-drafts/{draft['id']}/test",
        json={
            "to_email": "draft-recipient@example.com",
            "idempotency_key": f"template-draft-test/{uuid.uuid4()}",
            "expected_revision": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is False
    assert result["queued"] is False
    assert result["provider_used"] == "gmail"
    assert result["error"] == "Gmail rejected the test send"
    assert result["submitted_revision"] == 1
    assert result["tested_revision"] is None

    db.expire_all()
    untested_draft = db.get(EmailTemplateDraft, uuid.UUID(draft["id"]))
    assert untested_draft is not None
    assert untested_draft.revision == 1
    assert untested_draft.last_tested_revision is None
    assert untested_draft.last_tested_at is None
