from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_workflow_email_appends_org_signature_for_org_scope(
    db, test_org, test_user, monkeypatch
):
    from app.db.enums import JobType
    from app.db.models import EmailLog, EmailTemplate, Job
    from app.services import workflow_email_provider
    from app.worker import process_workflow_email
    from app.services import resend_email_service, resend_settings_service

    test_org.signature_company_name = "Org Signature Co"
    test_org.signature_template = "classic"
    db.commit()

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Workflow Template",
        subject="Hello",
        body="<p>Body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(template)
    db.commit()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **kwargs: (
            "resend",
            {"api_key_encrypted": "fake", "from_email": "no-reply@test.com"},
        ),
    )
    monkeypatch.setattr(resend_settings_service, "decrypt_api_key", lambda _: "key")

    async def fake_send_email_direct(**_kwargs):
        return True, None, "msg-id"

    monkeypatch.setattr(resend_email_service, "send_email_direct", fake_send_email_direct)

    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "recipient@test.com",
            "variables": {},
            "workflow_scope": "org",
            "include_org_signature": True,
        },
    )
    db.add(job)
    db.commit()

    await process_workflow_email(db, job)

    email_log = (
        db.query(EmailLog)
        .filter(EmailLog.organization_id == test_org.id)
        .order_by(EmailLog.created_at.desc())
        .first()
    )
    assert email_log is not None
    assert "Org Signature Co" in (email_log.body or "")
    assert test_user.display_name not in (email_log.body or "")


@pytest.mark.asyncio
async def test_workflow_email_appends_personal_signature_for_personal_scope(
    db, test_org, test_user, monkeypatch
):
    from app.db.enums import JobType
    from app.db.models import EmailLog, EmailTemplate, Job
    from app.services import workflow_email_provider
    from app.worker import process_workflow_email
    from app.services import resend_email_service, resend_settings_service

    test_org.signature_company_name = "Org Signature Co"
    test_org.signature_template = "classic"
    db.commit()

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Workflow Template",
        subject="Hello",
        body="<p>Body</p>",
        scope="personal",
        owner_user_id=test_user.id,
        is_active=True,
    )
    db.add(template)
    db.commit()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **kwargs: (
            "resend",
            {"api_key_encrypted": "fake", "from_email": "no-reply@test.com"},
        ),
    )
    monkeypatch.setattr(resend_settings_service, "decrypt_api_key", lambda _: "key")

    async def fake_send_email_direct(**_kwargs):
        return True, None, "msg-id"

    monkeypatch.setattr(resend_email_service, "send_email_direct", fake_send_email_direct)

    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "recipient@test.com",
            "variables": {},
            "workflow_scope": "personal",
            "workflow_owner_id": str(test_user.id),
            "include_org_signature": True,
        },
    )
    db.add(job)
    db.commit()

    await process_workflow_email(db, job)

    email_log = (
        db.query(EmailLog)
        .filter(EmailLog.organization_id == test_org.id)
        .order_by(EmailLog.created_at.desc())
        .first()
    )
    assert email_log is not None
    assert "Org Signature Co" in (email_log.body or "")
    assert test_user.display_name in (email_log.body or "")
